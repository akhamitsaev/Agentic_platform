from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, Depends, Header
from fastapi.responses import StreamingResponse, JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
import httpx
import json
import time
import asyncio
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from balancer import LoadBalancer, ProviderInfo
from metrics import record_request, meter
from mlflow_client import track_llm_call
from auth import verify_token
from guardrails import validate_request, sanitize_response
import os

app = FastAPI(title="LLM Proxy", version="1.0.0")

Instrumentator().instrument(app).expose(app)

strategy = os.getenv("BALANCER_STRATEGY", "latency")
balancer = LoadBalancer(strategy=strategy)

client = httpx.AsyncClient(timeout=60.0)

PROVIDER_REGISTRY_URL = os.getenv("PROVIDER_REGISTRY_URL", "http://localhost:8002")

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str
    messages: List[Message]
    stream: bool = False
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None

async def fetch_providers() -> List[ProviderInfo]:
    try:
        resp = await client.get(f"{PROVIDER_REGISTRY_URL}/providers")
        resp.raise_for_status()
        data = resp.json()
        providers = []
        for item in data:
            providers.append(ProviderInfo(
                id=item["id"],
                name=item["name"],
                base_url=item["base_url"],
                api_key=item.get("api_key"),
                models=item["models"],
                priority=item["priority"],
                health_status=item.get("health_status", "unknown"),
                price_per_input_token=item.get("price_per_input_token", 0.0),
                price_per_output_token=item.get("price_per_output_token", 0.0)
            ))
        return providers
    except Exception as e:
        print(f"Failed to fetch providers: {e}")
        return []

@app.on_event("startup")
async def startup():
    providers = await fetch_providers()
    balancer.update_providers(providers)
    asyncio.create_task(refresh_providers_periodically())

async def refresh_providers_periodically():
    while True:
        await asyncio.sleep(30)
        providers = await fetch_providers()
        balancer.update_providers(providers)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/v1/chat/completions")
async def chat_completions(
    request: ChatRequest, 
    background_tasks: BackgroundTasks,
    token_type: str = Depends(verify_token)
):
    is_valid, injection_error = validate_request([m.dict() for m in request.messages])
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Prompt injection detected: {injection_error}")
    
    provider = await balancer.select_provider(request.model)
    if not provider:
        raise HTTPException(status_code=503, detail="No available provider for model")

    headers = {"Content-Type": "application/json"}
    if provider.api_key:
        headers["Authorization"] = f"Bearer {provider.api_key}"

    payload = request.dict(exclude_none=True)

    start_time = time.time()
    first_token_time = None
    ttft = None
    tpot = 0.0
    tokens_in = sum(len(m.content.split()) for m in request.messages)
    tokens_out = 0
    cost = 0.0
    response_text = ""
    status = "success"

    try:
        if request.stream:
            async def stream_generator():
                nonlocal ttft, first_token_time, tokens_out, response_text, cost, tpot
                first_token = True
                token_count = 0
                async with client.stream(
                    "POST",
                    f"{provider.base_url}/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60.0
                ) as resp:
                    if resp.status_code >= 400:
                        error_text = await resp.aread()
                        raise HTTPException(status_code=resp.status_code, detail=error_text.decode())
                    async for chunk in resp.aiter_bytes():
                        if first_token:
                            first_token_time = time.time()
                            ttft = first_token_time - start_time
                            first_token = False
                        chunk_str = chunk.decode()
                        response_text += chunk_str
                        token_count += len(chunk_str.split())
                        yield chunk
                tokens_out = token_count
                if tokens_out > 0 and first_token_time:
                    tpot = (time.time() - first_token_time) / tokens_out
                cost = (tokens_in * provider.price_per_input_token + tokens_out * provider.price_per_output_token) / 1000

            response = StreamingResponse(stream_generator(), media_type="text/event-stream")
        else:
            resp = await client.post(
                f"{provider.base_url}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60.0
            )
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            data = resp.json()
            response_text = json.dumps(data)
            
            raw_content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            sanitized_content, secrets_masked = sanitize_response(raw_content)
            if secrets_masked > 0:
                data["choices"][0]["message"]["content"] = sanitized_content
                response_text = json.dumps(data)
            
            tokens_out = len(raw_content.split())
            cost = (tokens_in * provider.price_per_input_token + tokens_out * provider.price_per_output_token) / 1000
            response = JSONResponse(content=data)

        duration = time.time() - start_time
        balancer.record_success(provider.id, duration)
        record_request(request.model, provider.id, status, duration, ttft or duration, tokens_in, tokens_out, cost, tpot)
        
        background_tasks.add_task(
            log_to_mlflow,
            model=request.model,
            provider_id=provider.id,
            provider_name=provider.name,
            prompt=request.messages[0].content if request.messages else "",
            response=response_text[:500],
            duration=duration,
            ttft=ttft,
            tpot=tpot,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost
        )
        return response

    except Exception as e:
        status = "error"
        duration = time.time() - start_time
        balancer.record_failure(provider.id, str(e))
        record_request(request.model, provider.id, status, duration, 0, tokens_in, 0, 0.0)
        raise

async def log_to_mlflow(model, provider_id, provider_name, prompt, response, duration, ttft, tpot, tokens_in, tokens_out, cost):
    import mlflow
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000"))
    with mlflow.start_run(run_name=f"llm_{model}_{provider_name}_{provider_id}"):
        mlflow.log_param("model", model)
        mlflow.log_param("provider_id", provider_id)
        mlflow.log_param("provider_name", provider_name)
        mlflow.log_param("prompt", prompt[:200])
        mlflow.log_metric("duration_seconds", duration)
        if ttft:
            mlflow.log_metric("ttft_seconds", ttft)
        if tpot > 0:
            mlflow.log_metric("tpot_seconds", tpot)
        mlflow.log_metric("tokens_input", tokens_in)
        mlflow.log_metric("tokens_output", tokens_out)
        mlflow.log_metric("cost_usd", cost)
        mlflow.log_text(response, "response_sample.txt")