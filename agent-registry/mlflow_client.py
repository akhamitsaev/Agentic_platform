import mlflow
import os
from contextlib import contextmanager
import time

mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000"))
mlflow.set_experiment("agent-platform")

def log_agent_registration(agent_id: str, agent_name: str, methods: list, description: str):
    """Логирование регистрации нового агента."""
    with mlflow.start_run(run_name=f"agent_reg_{agent_name}"):
        mlflow.log_param("agent_id", agent_id)
        mlflow.log_param("agent_name", agent_name)
        mlflow.log_param("methods", str(methods))
        mlflow.log_param("description", description[:200])
        mlflow.log_metric("registration_timestamp", time.time())


def log_agent_call(agent_id: str, agent_name: str, method: str, input_data: str, 
                   output_data: str, duration: float, status: str = "success"):
    """Логирование вызова агента."""
    with mlflow.start_run(run_name=f"agent_{agent_name}_{method}"):
        mlflow.log_param("agent_id", agent_id)
        mlflow.log_param("agent_name", agent_name)
        mlflow.log_param("method", method)
        mlflow.log_param("input_preview", input_data[:200])
        mlflow.log_param("status", status)
        mlflow.log_metric("duration_seconds", duration)
        if output_data:
            mlflow.log_text(output_data[:1000], "output.txt")


@contextmanager
def track_agent_call(agent_id: str, agent_name: str, method: str, input_data: str):
    """Контекстный менеджер для трассировки вызова агента."""
    start_time = time.time()
    output_data = ""
    status = "success"
    
    try:
        yield {
            "output_data": "",
            "status": "success"
        }
    except Exception as e:
        status = "error"
        output_data = str(e)
        raise
    finally:
        duration = time.time() - start_time
        log_agent_call(
            agent_id=agent_id,
            agent_name=agent_name,
            method=method,
            input_data=input_data,
            output_data=output_data,
            duration=duration,
            status=status
        )