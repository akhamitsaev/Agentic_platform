from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from typing import List, Optional

from datetime import datetime

from database import get_db, engine, Base
from models import Provider
from pydantic import BaseModel
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_fastapi_instrumentator import Instrumentator
import os

resource = Resource(attributes={SERVICE_NAME: "provider-registry"})
provider_telemetry = TracerProvider(resource=resource)
otlp_exporter = OTLPSpanExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"), insecure=True)
provider_telemetry.add_span_processor(BatchSpanProcessor(otlp_exporter))
trace.set_tracer_provider(provider_telemetry)

app = FastAPI(title="Provider Registry", version="1.0.0")
Instrumentator().instrument(app).expose(app)
FastAPIInstrumentor.instrument_app(app)

class ProviderCreate(BaseModel):
    id: Optional[str] = None
    name: str
    base_url: str
    api_key: Optional[str] = None
    models: List[str] = []
    price_per_input_token: float = 0.0
    price_per_output_token: float = 0.0
    rate_limit: int = 60
    priority: int = 1

class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    models: Optional[List[str]] = None
    price_per_input_token: Optional[float] = None
    price_per_output_token: Optional[float] = None
    rate_limit: Optional[int] = None
    priority: Optional[int] = None
    health_status: Optional[str] = None
    last_error: Optional[str] = None

class ProviderResponse(BaseModel):
    id: str
    name: str
    base_url: str
    api_key: Optional[str] = None
    models: List[str]
    price_per_input_token: float
    price_per_output_token: float
    rate_limit: int
    priority: int
    health_status: str
    last_error: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/providers", response_model=ProviderResponse)
async def create_provider(provider: ProviderCreate, db: AsyncSession = Depends(get_db)):
    provider_id = provider.id or str(uuid.uuid4())
    db_provider = Provider(
        id=provider_id,
        name=provider.name,
        base_url=provider.base_url,
        api_key=provider.api_key,
        models=provider.models,
        price_per_input_token=provider.price_per_input_token,
        price_per_output_token=provider.price_per_output_token,
        rate_limit=provider.rate_limit,
        priority=provider.priority,
        health_status="unknown"
    )
    db.add(db_provider)
    await db.commit()
    await db.refresh(db_provider)
    return db_provider

@app.get("/providers", response_model=List[ProviderResponse])
async def list_providers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Provider))
    providers = result.scalars().all()
    return providers

@app.get("/providers/{provider_id}", response_model=ProviderResponse)
async def get_provider(provider_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Provider).where(Provider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider

@app.put("/providers/{provider_id}", response_model=ProviderResponse)
async def update_provider(provider_id: str, update: ProviderUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Provider).where(Provider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    update_data = update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(provider, key, value)
    await db.commit()
    await db.refresh(provider)
    return provider

@app.delete("/providers/{provider_id}")
async def delete_provider(provider_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Provider).where(Provider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    await db.delete(provider)
    await db.commit()
    return {"status": "deleted"}