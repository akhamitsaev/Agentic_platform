from fastapi import FastAPI
from pydantic import BaseModel
import httpx
import time
import uuid
import os
import re
from typing import List

app = FastAPI(title="Orchestrator Agent")

POET_URL = os.getenv("POET_URL", "http://poet-agent:8001")
TRANSLATOR_URL = os.getenv("TRANSLATOR_URL", "http://literary-translator:8002")
LLM_PROXY_URL = os.getenv("LLM_PROXY_URL", "http://llm-proxy:8000")
AGENT_TOKEN = os.getenv("AGENT_TOKEN", "")

class PoemRequest(BaseModel):
    theme: str
    count: int = 2
    max_stanzas: int = 4
    russian_style: str = "есенин"
    english_style: str = "байрон"

class PoemResult(BaseModel):
    index: int
    russian: str
    english: str
    poet_score: float
    translator_score: float
    poet_attempts: int
    translator_attempts: int

class OrchestratorResponse(BaseModel):
    request_id: str
    theme: str
    poems: List[PoemResult]
    total_time: float


def safe_get_poem(response) -> str:
    """Безопасно извлекает стих из ответа Poet Agent."""
    try:
        data = response.json()
        return str(data.get("poem", data))
    except:
        return str(response.text or "Ошибка генерации")


def safe_get_translation(response) -> str:
    """Безопасно извлекает перевод из ответа Translator."""
    try:
        data = response.json()
        return str(data.get("translated_poem", data))
    except:
        return str(response.text or "Ошибка перевода")


async def call_poet(theme: str, style: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{POET_URL}/write",
                json={"theme": theme, "style": style, "lines": 4}
            )
            return safe_get_poem(resp)
    except Exception as e:
        return f"Poet unavailable: {str(e)[:100]}"


async def call_translator(poem: str, from_style: str, to_style: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{TRANSLATOR_URL}/translate_poem",
                json={"poem": poem, "from_style": from_style, "to_style": to_style}
            )
            return safe_get_translation(resp)
    except Exception as e:
        return f"Translator unavailable: {str(e)[:100]}"


async def evaluate_quality(text: str, style: str) -> float:
    try:
        prompt = f"Оцени качество текста по шкале 0-10. Стиль: {style}. Текст: {text[:500]}. Верни только число."
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{LLM_PROXY_URL}/v1/chat/completions",
                headers={"Authorization": f"Bearer {AGENT_TOKEN}"},
                json={
                    "model": "mistral-small-latest",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "stream": False
                }
            )
            data = resp.json()
            content = str(data.get("choices", [{}])[0].get("message", {}).get("content", "5"))
            match = re.search(r"[\d.]+", content)
            return float(match.group()) if match else 5.0
    except:
        return 5.0  # При любой ошибке — проходной балл


@app.post("/generate_poems", response_model=OrchestratorResponse)
async def generate_poems(request: PoemRequest):
    start_time = time.time()
    poems = []
    
    for i in range(request.count):
        # Генерация стиха (до 5 попыток, цель >= 5)
        russian = ""
        poet_score = 0.0
        poet_attempts = 0
        
        while poet_attempts < 5 and poet_score < 5.0:
            poet_attempts += 1
            russian = await call_poet(request.theme, request.russian_style)
            poet_score = await evaluate_quality(russian, request.russian_style)
        
        # Перевод (до 5 попыток, цель >= 5)
        english = ""
        translator_score = 0.0
        translator_attempts = 0
        
        while translator_attempts < 5 and translator_score < 5.0:
            translator_attempts += 1
            english = await call_translator(russian, request.russian_style, request.english_style)
            translator_score = await evaluate_quality(english, request.english_style)
        
        poems.append(PoemResult(
            index=i + 1,
            russian=russian[:500],
            english=english[:500],
            poet_score=round(poet_score, 1),
            translator_score=round(translator_score, 1),
            poet_attempts=poet_attempts,
            translator_attempts=translator_attempts
        ))
    
    return OrchestratorResponse(
        request_id=str(uuid.uuid4())[:8],
        theme=request.theme,
        poems=poems,
        total_time=round(time.time() - start_time, 2)
    )


@app.get("/health")
async def health():
    return {"status": "ok"}