from fastapi import FastAPI, HTTPException, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
import httpx
import time
from typing import List, Optional
from datetime import datetime

from database import get_db, engine, Base, AsyncSessionLocal
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

from auth import verify_master_token, generate_agent_token

resource = Resource(attributes={SERVICE_NAME: "agent-registry"})
provider = TracerProvider(resource=resource)
otlp_exporter = OTLPSpanExporter(
    endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"), 
    insecure=True
)
provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
trace.set_tracer_provider(provider)

app = FastAPI(title="Agent Registry", version="1.0.0")
Instrumentator().instrument(app).expose(app)
FastAPIInstrumentor.instrument_app(app)

class AgentCreate(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    methods: List[str] = []
    card: Optional[dict] = None

class AgentResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    methods: List[str]
    card: Optional[dict]
    token: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class AgentCallRequest(BaseModel):
    agent_id: str
    method: str
    input_data: dict
    caller: Optional[str] = None

import mlflow

mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000"))
mlflow.set_experiment("agent-platform")


def log_agent_registration(agent_id: str, agent_name: str, methods: list, description: str):
    with mlflow.start_run(run_name=f"reg_{agent_name}"):
        mlflow.log_param("agent_id", agent_id)
        mlflow.log_param("agent_name", agent_name)
        mlflow.log_param("methods", str(methods))
        mlflow.log_param("description", description[:200])


def log_agent_call(agent_id: str, agent_name: str, method: str, caller: str, 
                   input_data: str, output_data: str, duration: float, status: str):
    with mlflow.start_run(run_name=f"call_{agent_name}_{method}"):
        mlflow.log_param("agent_id", agent_id)
        mlflow.log_param("agent_name", agent_name)
        mlflow.log_param("method", method)
        mlflow.log_param("caller", caller)
        mlflow.log_param("input", input_data[:200])
        mlflow.log_param("status", status)
        mlflow.log_metric("duration_seconds", duration)
        mlflow.log_text(output_data[:1000], "output.txt")


LLM_PROXY_URL = os.getenv("LLM_PROXY_URL", "http://llm-proxy:8000")
MASTER_TOKEN = os.getenv("MASTER_TOKEN", "master-secret-token-2026")


async def call_llm(prompt: str, model: str = "mistral-small-latest", agent_token: str = None) -> str:
    token = agent_token or MASTER_TOKEN
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{LLM_PROXY_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False
            }
        )
        data = resp.json()
        return data["choices"][0]["message"]["content"]


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/agents", response_model=AgentResponse)
async def create_agent(
    agent: AgentCreate, 
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_master_token)
):
    agent_id = agent.id or str(uuid.uuid4())
    agent_token = generate_agent_token()
    
    db_agent = Agent(
        id=agent_id,
        name=agent.name,
        description=agent.description,
        methods=agent.methods,
        card=agent.card or {},
        token=agent_token
    )
    db.add(db_agent)
    await db.commit()
    await db.refresh(db_agent)

    log_agent_registration(agent_id, agent.name, agent.methods, agent.description or "")
    
    response = AgentResponse(
        id=db_agent.id,
        name=db_agent.name,
        description=db_agent.description,
        methods=db_agent.methods,
        card=db_agent.card,
        token=agent_token,
        created_at=db_agent.created_at,
        updated_at=db_agent.updated_at
    )
    return response


@app.get("/agents", response_model=List[AgentResponse])
async def list_agents(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_master_token)
):
    result = await db.execute(select(Agent))
    return result.scalars().all()


@app.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str, 
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_master_token)
):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@app.delete("/agents/{agent_id}")
async def delete_agent(
    agent_id: str, 
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_master_token)
):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await db.delete(agent)
    await db.commit()
    return {"status": "deleted"}


@app.post("/agents/call")
async def call_agent(request: AgentCallRequest, db: AsyncSession = Depends(get_db)):
    start_time = time.time()
    
    result = await db.execute(select(Agent).where(Agent.id == request.agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if request.method not in agent.methods:
        raise HTTPException(status_code=400, detail=f"Method {request.method} not supported")
    
    llm_methods = ["translate", "summarize", "qa", "generate", "chat", "write", "poem"]
    caller = request.caller or "user"
    
    if request.method in llm_methods:
        prompt = f"Method: {request.method}\nInput: {request.input_data}"
        model = request.input_data.get("model", "mistral-small-latest")
        llm_result = await call_llm(prompt, model, agent.token)
        output = {"result": llm_result}
    else:
        output = {"result": f"Executed {request.method}"}
    
    duration = time.time() - start_time
    
    log_agent_call(
        agent_id=agent.id,
        agent_name=agent.name,
        method=request.method,
        caller=caller,
        input_data=str(request.input_data),
        output_data=str(output),
        duration=duration,
        status="success"
    )
    
    return output


@app.get("/agents/validate")
async def validate_agent_token(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    token = authorization.replace("Bearer ", "")
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Agent).where(Agent.token == token))
        agent = result.scalar_one_or_none()
        if agent:
            return {"valid": True, "agent_id": agent.id}
    
    raise HTTPException(status_code=403, detail="Invalid agent token")