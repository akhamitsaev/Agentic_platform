# AI Agent Platform

Домашнее задание.\
Трек №2. Проектирование, эксплуатация и сервинг LLM-систем (ИТМО, магистратура AI, 2025--2026)\



## Общая информация

-   **Задача:** Разработка агентной платформы\
-   **Автор:** \Хамицаев Александр\

------------------------------------------------------------------------

## 1. Описание

API-шлюз для LLM-запросов с:

-   интеллектуальной балансировкой нагрузки\
-   реестром A2A-агентов\
-   guardrails\
-   полной телеметрией

Платформа предоставляет OpenAI-совместимый эндпоинт:

/v1/chat/completions

За которым стоит пул LLM-провайдеров с динамической маршрутизацией.

------------------------------------------------------------------------

## 2. Возможности

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

## 3. Архитектура
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Внешние клиенты                                 │
│                    (Пользователи, Агенты, Нагрузочные тесты)                  │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           LLM Proxy (:8000)                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │   Auth Layer    │  │   Guardrails    │  │      Load Balancer          │  │
│  │ (Master/Agent   │  │ (Prompt Inject  │  │ (Round Robin / Weighted /    │  │
│  │    Tokens)      │  │  + Secret Leak) │  │  Latency / Health-Aware)     │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
│                                      │                                       │
│                              Circuit Breaker                                 │
│                                      │                                       │
└──────────────────────────────────────┼───────────────────────────────────────┘
                                       │
                       ┌───────────────┼───────────────┐
                       ▼               ▼               ▼
                ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
                │  Provider 1  │ │  Provider 2  │ │  Provider N  │
                │  (Mistral)   │ │   (OpenAI)   │ │   (Mock)     │
                └──────────────┘ └──────────────┘ └──────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           Внутренние сервисы                                 │
├─────────────────┬─────────────────┬─────────────────┬───────────────────────┤
│ Agent Registry  │Provider Registry│  Poet Agent     │ Literary Translator   │
│    (:8001)      │    (:8002)      │   (:8010)       │      (:8011)          │
├─────────────────┼─────────────────┼─────────────────┼───────────────────────┤
│                 │                 │ Orchestrator    │                       │
│                 │                 │   (:8012)       │                       │
└─────────────────┴─────────────────┴─────────────────┴───────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           Мониторинг и телеметрия                            │
├──────────────┬──────────────┬──────────────┬──────────────┬─────────────────┤
│  Prometheus  │   Grafana    │    MLflow    │OpenTelemetry │   cAdvisor      │
│   (:9090)    │   (:3000)    │   (:5000)    │   (:4317)    │   (:8080)       │
└──────────────┴──────────────┴──────────────┴──────────────┴─────────────────┘
```
------------------------------------------------------------------------

### Поток запросов к LLM

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

## 4. Быстрый старт

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

### Доступные сервисы

| Сервис | URL | Логин/Пароль |
|--------|-----|--------------|
| LLM Proxy (API) | http://localhost:8000 | - |
| Swagger UI | http://localhost:8000/docs | - |
| Agent Registry | http://localhost:8001/docs | - |
| Provider Registry | http://localhost:8002/docs | - |
| Poet Agent | http://localhost:8010 | - |
| Literary Translator | http://localhost:8011 | - |
| Orchestrator Agent | http://localhost:8012 | - |
| Prometheus | http://localhost:9090 | - |
| Grafana | http://localhost:3000 | admin / admin |
| MLflow | http://localhost:5000 | - |
| cAdvisor | http://localhost:8080 | - |

------------------------------------------------------------------------

## 5. Проверка работоспособности
Health-check
powershell
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8010/health
curl http://localhost:8011/health
curl http://localhost:8012/health
Добавление LLM-провайдера
powershell
$body = @{
    name = "mistral"
    base_url = "https://api.mistral.ai"
    api_key = "ВАШ_API_КЛЮЧ"
    models = @("mistral-small-latest", "mistral-medium-latest")
    price_per_input_token = 0.000002
    price_per_output_token = 0.000006
    priority = 10
} | ConvertTo-Json

$headers = @{
    "Authorization" = "Bearer master-secret-token-2026"
    "Content-Type" = "application/json"
}

Invoke-RestMethod -Uri "http://localhost:8002/providers" -Method POST -Body $body -Headers $headers
Тестовый запрос к LLM (через Swagger UI)
Откройте http://localhost:8000/docs

Нажмите Authorize (замок) и введите Bearer master-secret-token-2026

Выберите POST /v1/chat/completions → Try it out

Вставьте:

json
{
  "model": "mistral-small-latest",
  "messages": [{"role": "user", "content": "Привет!"}],
  "stream": false
}
Нажмите Execute

Тестовый запрос через PowerShell
powershell
$request = @{
    model = "mistral-small-latest"
    messages = @(@{role = "user"; content = "Привет!"})
    stream = $false
} | ConvertTo-Json

$headers = @{
    "Authorization" = "Bearer master-secret-token-2026"
    "Content-Type" = "application/json"
}

Invoke-RestMethod -Uri "http://localhost:8000/v1/chat/completions" -Method POST -Body $request -Headers $headers


## 6. API Reference
Авторизация
Все запросы (кроме /health, /metrics, /docs) требуют заголовок:

text
Authorization: Bearer <token>
Два типа токенов:

Тип	Доступ
Master-токен	Полный доступ ко всем эндпоинтам
Agent-токен	Только /v1/chat/completions
POST /v1/chat/completions
OpenAI-совместимый эндпоинт для генерации ответов LLM.

Параметры запроса:

Параметр	Тип	Обязательный	Описание
model	string	да	Идентификатор модели
messages	array	да	Массив сообщений {role, content}
stream	bool	нет	SSE-стриминг (по умолчанию: false)
temperature	float	нет	Температура генерации
max_tokens	int	нет	Максимум токенов в ответе
Пример (non-streaming):

powershell
$request = @{
    model = "mistral-small-latest"
    messages = @(@{role = "user"; content = "Что такое FastAPI?"})
    stream = $false
    max_tokens = 200
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/v1/chat/completions" -Method POST -Body $request -Headers $headers
Пример (streaming):

powershell
$request = @{
    model = "mistral-small-latest"
    messages = @(@{role = "user"; content = "Напиши стихотворение"})
    stream = $true
} | ConvertTo-Json

$response = Invoke-WebRequest -Uri "http://localhost:8000/v1/chat/completions" -Method POST -Body $request -Headers $headers
$response.Content
POST /agents
Регистрация нового агента. Возвращает agent-токен.

powershell
$agent = @{
    name = "my-agent"
    description = "My custom agent"
    methods = @("run", "execute")
    card = @{ version = "1.0" }
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8001/agents" -Method POST -Body $agent -Headers $headers
GET /agents
Список всех зарегистрированных агентов.

powershell
Invoke-RestMethod -Uri "http://localhost:8001/agents" -Method GET -Headers $headers
GET /agents/{id}
Получение агента по UUID.

powershell
Invoke-RestMethod -Uri "http://localhost:8001/agents/{id}" -Method GET -Headers $headers
DELETE /agents/{id}
Удаление агента.

powershell
Invoke-RestMethod -Uri "http://localhost:8001/agents/{id}" -Method DELETE -Headers $headers
POST /providers
Добавление LLM-провайдера.

powershell
$provider = @{
    name = "openai"
    base_url = "https://api.openai.com"
    api_key = "sk-..."
    models = @("gpt-3.5-turbo", "gpt-4")
    price_per_input_token = 0.0015
    price_per_output_token = 0.002
    priority = 5
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8002/providers" -Method POST -Body $provider -Headers $headers
GET /providers
Список всех провайдеров.

powershell
Invoke-RestMethod -Uri "http://localhost:8002/providers" -Method GET -Headers $headers
PUT /providers/{id}
Обновление провайдера.

powershell
$update = @{ priority = 20; health_status = "healthy" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8002/providers/{id}" -Method PUT -Body $update -Headers $headers
DELETE /providers/{id}
Удаление провайдера.

powershell
Invoke-RestMethod -Uri "http://localhost:8002/providers/{id}" -Method DELETE -Headers $headers
Служебные эндпоинты
Эндпоинт	Метод	Авторизация	Описание
/health	GET	нет	Проверка здоровья
/metrics	GET	нет	Prometheus метрики
/docs	GET	нет	Swagger UI
/openapi.json	GET	нет	OpenAPI-схема

------------------------------------------------------------------------

## 7.Демо-агенты

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

## 8.Балансировка нагрузки

Стратегии:

-   Round Robin
-   Weighted
-   Latency-based (EMA, α=0.3)
-   Health-aware

------------------------------------------------------------------------

## 9.Circuit Breaker

Состояния:

-   CLOSED
-   OPEN
-   HALF_OPEN

Параметры:

failure_threshold = 3\
recovery_timeout = 30

------------------------------------------------------------------------

## 10.Guardrails

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

## 11.Наблюдаемость

Используются:

-   OpenTelemetry
-   Prometheus
-   Grafana
-   MLflow

------------------------------------------------------------------------

## 12.Переменные окружения

-   MASTER_TOKEN
-   BALANCER_STRATEGY
-   OTEL_EXPORTER_OTLP_ENDPOINT
-   MLFLOW_TRACKING_URI
-   LLM_PROXY_URL
-   DATABASE_URL

------------------------------------------------------------------------

## 13.Стек технологий

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

## 14. Структура проекта
```
agent-platform/
├── llm-proxy/                # Балансировщик LLM
│   ├── main.py
│   ├── balancer.py
│   ├── circuit_breaker.py
│   ├── guardrails.py
│   ├── auth.py
│   └── metrics.py
├── agent-registry/           # Реестр агентов
│   ├── main.py
│   ├── models.py
│   └── auth.py
├── provider-registry/        # Реестр провайдеров
│   └── main.py
├── demo-agents/              # Демо-агенты
│   ├── poet_agent/
│   ├── literary_translator/
│   └── orchestrator_agent/
├── mlflow/                   # MLflow сервер
├── grafana/                  # Grafana provisioning
│   └── provisioning/
│       ├── dashboards/
│       └── datasources/
├── prometheus.yml            # Конфигурация Prometheus
├── otel-collector-config.yaml # OpenTelemetry Collector
├── docker-compose.yml
├── .env.example
└── .gitignore

```
