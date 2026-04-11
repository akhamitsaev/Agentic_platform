from sqlalchemy import Column, String, Integer, Float, JSON, DateTime, Boolean
from sqlalchemy.sql import func
from database import Base

class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String)
    methods = Column(JSON, default=[])
    card = Column(JSON)
    token = Column(String, nullable=True, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Provider(Base):
    __tablename__ = "providers"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    base_url = Column(String, nullable=False)
    api_key = Column(String, nullable=True)
    models = Column(JSON, default=[])
    price_per_input_token = Column(Float, default=0.0)
    price_per_output_token = Column(Float, default=0.0)
    rate_limit = Column(Integer, default=60)
    priority = Column(Integer, default=1)
    health_status = Column(String, default="unknown")
    last_error = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())