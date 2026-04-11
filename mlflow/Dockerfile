FROM python:3.11-slim

RUN pip install mlflow==2.8.1 psycopg2-binary

EXPOSE 5000

CMD mlflow server \
    --backend-store-uri postgresql://agent:agentpass@postgres:5432/agent_platform \
    --default-artifact-root /mlflow/artifacts \
    --host 0.0.0.0 \
    --port 5000