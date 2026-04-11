from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import os
import uuid

app = FastAPI(title="Literary Translator Agent")

LLM_PROXY_URL = os.getenv("LLM_PROXY_URL", "http://llm-proxy:8000")
AGENT_TOKEN = os.getenv("AGENT_TOKEN", "")

class TranslationRequest(BaseModel):
    text: str
    source_language: str = "auto"
    target_language: str = "Russian"
    style: str = "literary"

class TranslationResponse(BaseModel):
    original: str
    translated: str
    target_language: str
    style: str
    request_id: str

@app.post("/translate", response_model=TranslationResponse)
async def translate(request: TranslationRequest):
    prompt = f"""Переведи следующий текст на {request.target_language} язык.
Стиль перевода: литературный, сохраняющий образность и стиль оригинала.

Текст для перевода:
{request.text}

Только перевод, без пояснений."""

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{LLM_PROXY_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {AGENT_TOKEN}"},
            json={
                "model": "mistral-small-latest",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "stream": False
            }
        )
        
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="LLM error")
        
        data = resp.json()
    
    return TranslationResponse(
        original=request.text[:200] + "..." if len(request.text) > 200 else request.text,
        translated=data["choices"][0]["message"]["content"].strip(),
        target_language=request.target_language,
        style=request.style,
        request_id=str(uuid.uuid4())[:8]
    )

@app.post("/translate_poem")
async def translate_poem(request: dict):
    poem = request.get("poem", "")
    from_style = request.get("from_style", "пушкин")
    to_style = request.get("to_style", "байрон")
    
    prompt = f"""Переведи стихотворение с сохранением поэтического стиля.
Оригинал написан в стиле: {from_style}
Переведи в стиле: {to_style}

Стихотворение:
{poem}

Только литературный перевод стихотворения, без пояснений."""

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{LLM_PROXY_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {AGENT_TOKEN}"},
            json={
                "model": "mistral-small-latest",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.85,
                "stream": False
            }
        )
        
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="LLM error")
        
        data = resp.json()
    
    return {
        "original_poem": poem,
        "translated_poem": data["choices"][0]["message"]["content"].strip(),
        "from_style": from_style,
        "to_style": to_style
    }

@app.get("/health")
async def health():
    return {"status": "ok", "agent": "literary_translator"}

@app.get("/")
async def root():
    return {
        "agent": "Literary Translator Agent",
        "endpoints": {
            "translate": "POST /translate",
            "translate_poem": "POST /translate_poem"
        }
    }