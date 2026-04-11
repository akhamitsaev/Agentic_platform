from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import os
import uuid

app = FastAPI(title="Poet Agent")

LLM_PROXY_URL = os.getenv("LLM_PROXY_URL", "http://llm-proxy:8000")
AGENT_TOKEN = os.getenv("AGENT_TOKEN", "")

class PoemRequest(BaseModel):
    theme: str = "любовь"
    style: str = "пушкин"
    lines: int = 4

class PoemResponse(BaseModel):
    poem: str
    theme: str
    style: str
    request_id: str

@app.post("/write", response_model=PoemResponse)
async def write_poem(request: PoemRequest):
    prompt = f"""Напиши стихотворение на русском языке.
Тема: {request.theme}
Стиль: {request.style}
Количество строк: {request.lines}

Только стихотворение, без пояснений."""

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{LLM_PROXY_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {AGENT_TOKEN}"},
            json={
                "model": "mistral-small-latest",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.9,
                "stream": False
            }
        )
        
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="LLM error")
        
        data = resp.json()
    
    return PoemResponse(
        poem=data["choices"][0]["message"]["content"].strip(),
        theme=request.theme,
        style=request.style,
        request_id=str(uuid.uuid4())[:8]
    )

@app.get("/health")
async def health():
    return {"status": "ok", "agent": "poet"}

@app.get("/")
async def root():
    return {
        "agent": "Poet Agent",
        "endpoints": {
            "write": "POST /write - написать стихотворение"
        }
    }