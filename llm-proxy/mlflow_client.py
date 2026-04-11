import mlflow
import os
import time
from contextlib import contextmanager

# mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))

mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000"))

@contextmanager
def track_llm_call(model: str, provider_id: str, prompt: str):
    """Контекстный менеджер для логирования вызова LLM в MLflow."""
    start_time = time.time()
    ttft = None
    error = None
    response_text = ""
    tokens_in = 0
    tokens_out = 0
    cost = 0.0

    try:
        yield {
            "start_time": start_time,
            "ttft": None,
            "response_text": "",
            "tokens_in": 0,
            "tokens_out": 0,
            "cost": 0.0,
            "error": None
        }
    except Exception as e:
        error = str(e)
        raise
    finally:
        duration = time.time() - start_time
        with mlflow.start_run(run_name=f"llm_{model}_{provider_id}"):
            mlflow.log_param("model", model)
            mlflow.log_param("provider", provider_id)
            mlflow.log_param("prompt", prompt[:200])  # truncate
            mlflow.log_metric("duration_seconds", duration)
            if ttft is not None:
                mlflow.log_metric("ttft_seconds", ttft)
            if tokens_in:
                mlflow.log_metric("tokens_input", tokens_in)
            if tokens_out:
                mlflow.log_metric("tokens_output", tokens_out)
            if cost:
                mlflow.log_metric("cost_usd", cost)
            if error:
                mlflow.log_param("error", error)
            mlflow.log_text(response_text[:500], "response_sample.txt")