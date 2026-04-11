from fastapi import Header, HTTPException
from typing import Optional
import os
import secrets

MASTER_TOKEN = os.getenv("MASTER_TOKEN", "master-secret-token-2026")

def verify_master_token(authorization: Optional[str] = Header(None)) -> str:
    """Проверка ТОЛЬКО master-токена для админских операций."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    token = authorization.replace("Bearer ", "")
    
    if token != MASTER_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid master token")
    
    return token

def generate_agent_token() -> str:
    """Генерация токена для агента."""
    return f"agent_{secrets.token_urlsafe(32)}"