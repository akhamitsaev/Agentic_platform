from fastapi import Header, HTTPException, Depends
from typing import Optional
import os
import httpx

MASTER_TOKEN = os.getenv("MASTER_TOKEN", "master-secret-token-2026")
PROVIDER_REGISTRY_URL = os.getenv("PROVIDER_REGISTRY_URL", "http://provider-registry:8002")

async def verify_token(authorization: Optional[str] = Header(None)) -> str:
    """Проверка master-токена или agent-токена."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    token = authorization.replace("Bearer ", "")
    
    # Master-токен
    if token == MASTER_TOKEN:
        return "master"
    
    # Agent-токен (проверяем в agent-registry)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"http://agent-registry:8001/agents/validate",
                headers={"Authorization": f"Bearer {token}"}
            )
            if resp.status_code == 200:
                return "agent"
    except:
        pass
    
    raise HTTPException(status_code=403, detail="Invalid token")