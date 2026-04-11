from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from typing import List

from database import get_db, engine, Base
from models import Agent
from pydantic import BaseModel
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_fastapi_instrumentator import Instrumentator
import os

# Setup OpenTelemetry
resource = Resource(attributes={SERVICE_NAME: "agent-registry"})
provider = TracerProvider(resource=resource)
otlp_exporter = OTLPSpanExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"), insecure=True)
provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
trace.set_tracer_provider(provider)

app = FastAPI(title="Agent Registry", version="1.0.0")
Instrumentator().instrument(app).expose(app)
FastAPIInstrumentor.instrument_app(app)

# Pydantic models
class AgentCreate(BaseModel):
    id: str | None = None
    name: str
    description: str | None = None
    methods: List[str] = []
    card: dict | None = None

class AgentResponse(BaseModel):
    id: str
    name: str
    description: str | None
    methods: List[str]
    card: dict | None
    created_at: str
    updated_at: str | None

    class Config:
        from_attributes = True

class AgentCallRequest(BaseModel):
    agent_id: str
    method: str
    input_data: dict


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/agents", response_model=AgentResponse)
async def create_agent(agent: AgentCreate, db: AsyncSession = Depends(get_db)):
    agent_id = agent.id or str(uuid.uuid4())
    db_agent = Agent(
        id=agent_id,
        name=agent.name,
        description=agent.description,
        methods=agent.methods,
        card=agent.card or {}
    )
    db.add(db_agent)
    await db.commit()
    await db.refresh(db_agent)

    # Логирование в MLflow
    log_agent_registration(
        agent_id=agent_id,
        agent_name=agent.name,
        methods=agent.methods,
        description=agent.description or ""
    )
    return db_agent

@app.get("/agents", response_model=List[AgentResponse])
async def list_agents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent))
    agents = result.scalars().all()
    return agents

@app.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@app.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await db.delete(agent)
    await db.commit()
    return {"status": "deleted"}

@app.post("/agents/call")
async def call_agent(request: AgentCallRequest, db: AsyncSession = Depends(get_db)):
    """Вызов метода агента с трассировкой в MLflow."""
    # Получить агента из БД
    result = await db.execute(select(Agent).where(Agent.id == request.agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Проверить, что метод поддерживается
    if request.method not in agent.methods:
        raise HTTPException(status_code=400, detail=f"Method {request.method} not supported")
    
    # Трассировка вызова
    with track_agent_call(
        agent_id=agent.id,
        agent_name=agent.name,
        method=request.method,
        input_data=str(request.input_data)
    ) as tracker:
        # Здесь должна быть логика вызова LLM через балансировщик
        # Для примера — эмуляция ответа
        output = {"result": f"Agent {agent.name} processed {request.method}"}
        tracker["output_data"] = str(output)
        tracker["status"] = "success"
    
    return output