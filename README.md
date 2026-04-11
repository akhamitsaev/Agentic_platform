# LLM Agent Platform

Домашнее задание по бонус-треку LLM (ИТМО, магистратура AI, 2025--2026)

## 📌 Общая информация

-   **Трек:** Инфраструктурный --- Разработка агентной платформы\
-   **Автор:** \[Ваше имя\]\
-   **Сроки:** 23.03.2026 -- 12.04.2026

------------------------------------------------------------------------

## 🧠 Описание

API-шлюз для LLM-запросов с:

-   интеллектуальной балансировкой нагрузки\
-   реестром A2A-агентов\
-   guardrails\
-   полной телеметрией

Платформа предоставляет OpenAI-совместимый эндпоинт:

/v1/chat/completions

За которым стоит пул LLM-провайдеров с динамической маршрутизацией.

------------------------------------------------------------------------

## ⚙️ Возможности

-   Проксирование запросов к LLM (с поддержкой streaming / SSE)
-   Балансировка нагрузки:
    -   Round-robin
    -   Weighted
    -   Latency-based (EMA)
    -   Health-aware
-   Circuit Breaker (Closed → Open → Half-Open)
-   A2A Agent Registry (Agent Card + токены)
-   Guardrails:
    -   Детекция prompt injection
    -   Маскирование секретов
-   Авторизация:
    -   Master-токен (полный доступ)
    -   Agent-токены (ограниченный доступ)
-   Телеметрия:
    -   OpenTelemetry
    -   Prometheus
    -   Grafana
    -   MLflow
-   Демо-агенты:
    -   Poet
    -   Literary Translator
    -   Orchestrator

------------------------------------------------------------------------

## 🏗 Архитектура

Внешние клиенты → LLM Proxy (:8000) → Providers

Внутренние сервисы:

-   Agent Registry (:8001)
-   Provider Registry (:8002)
-   Poet Agent (:8010)
-   Literary Translator (:8011)
-   Orchestrator (:8012)

Мониторинг:

-   Prometheus (:9090)
-   Grafana (:3000)
-   MLflow (:5000)
-   OpenTelemetry (:4317)
-   cAdvisor (:8080)

------------------------------------------------------------------------

## 🔄 Поток запроса

1.  Клиент отправляет запрос `/v1/chat/completions`
2.  Проверка токена (Auth Middleware)
3.  Guardrails (prompt injection)
4.  Выбор провайдера (Load Balancer)
5.  Проверка Circuit Breaker
6.  Проксирование запроса
7.  Проверка ответа (secret leak)
8.  Метрики → OpenTelemetry → Prometheus → Grafana
9.  Трейсы → MLflow

------------------------------------------------------------------------

## 🚀 Быстрый старт

### Требования

-   Docker + Docker Compose\
-   API-ключ Mistral (или другого провайдера)\
-   Windows 10/11 или Linux

### Запуск

``` powershell
git clone <URL_репозитория> agent-platform
cd agent-platform

copy .env.example .env
docker-compose up -d --build
docker-compose ps
```

------------------------------------------------------------------------

## 🌐 Доступные сервисы

  Сервис                URL
  --------------------- ----------------------------
  LLM Proxy             http://localhost:8000
  Swagger UI            http://localhost:8000/docs
  Agent Registry        http://localhost:8001/docs
  Provider Registry     http://localhost:8002/docs
  Poet Agent            http://localhost:8010
  Literary Translator   http://localhost:8011
  Orchestrator          http://localhost:8012
  Prometheus            http://localhost:9090
  Grafana               http://localhost:3000
  MLflow                http://localhost:5000
  cAdvisor              http://localhost:8080

------------------------------------------------------------------------

## 🔌 API Reference

### Авторизация

Authorization: Bearer `<token>`{=html}

Типы токенов:

-   Master --- полный доступ
-   Agent --- только `/v1/chat/completions`

------------------------------------------------------------------------

### POST `/v1/chat/completions`

OpenAI-совместимый endpoint генерации ответа LLM.

Параметры:

-   model (string, обязательный)
-   messages (array, обязательный)
-   stream (bool)
-   temperature (float)
-   max_tokens (int)

------------------------------------------------------------------------

## 🤖 Демо-агенты

### Poet Agent (:8010)

Пишет стихи на русском языке.

### Literary Translator (:8011)

Переводит тексты с сохранением литературного стиля.

### Orchestrator (:8012)

Координирует работу Poet и Translator:

-   генерирует стихи
-   оценивает качество (≥5/10)
-   переводит

------------------------------------------------------------------------

## ⚖️ Балансировка нагрузки

Стратегии:

-   Round Robin
-   Weighted
-   Latency-based (EMA, α=0.3)
-   Health-aware

------------------------------------------------------------------------

## 🔁 Circuit Breaker

Состояния:

-   CLOSED
-   OPEN
-   HALF_OPEN

Параметры:

failure_threshold = 3\
recovery_timeout = 30

------------------------------------------------------------------------

## 🛡 Guardrails

Prompt Injection Detection:

-   ignore previous instructions
-   you are now
-   reveal your instructions
-   system prompt

Secret Leak Detection:

-   API keys → \[REDACTED_API_KEY\]
-   AWS keys → \[REDACTED_AWS_KEY\]
-   Bearer tokens → \[REDACTED_TOKEN\]
-   Private keys → \[REDACTED_PRIVATE_KEY\]

------------------------------------------------------------------------

## 📊 Наблюдаемость

Используются:

-   OpenTelemetry
-   Prometheus
-   Grafana
-   MLflow

------------------------------------------------------------------------

## 🔧 Переменные окружения

-   MASTER_TOKEN
-   BALANCER_STRATEGY
-   OTEL_EXPORTER_OTLP_ENDPOINT
-   MLFLOW_TRACKING_URI
-   LLM_PROXY_URL
-   DATABASE_URL

------------------------------------------------------------------------

## 🧱 Стек технологий

-   Python 3.11
-   FastAPI + Uvicorn
-   httpx (async)
-   Pydantic v2
-   PostgreSQL + SQLAlchemy
-   Docker + Docker Compose
-   OpenTelemetry + Prometheus
-   Grafana
-   MLflow
-   cAdvisor

------------------------------------------------------------------------

## 📂 Структура проекта

agent-platform/ ├── llm-proxy/ ├── agent-registry/ ├──
provider-registry/ ├── demo-agents/ ├── mlflow/ ├── grafana/ ├──
prometheus.yml ├── otel-collector-config.yaml ├── docker-compose.yml ├──
.env.example └── .gitignore
