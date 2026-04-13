# AI Agent Platform

Домашнее задание.\
Инфраструктурный трек. Проектирование, эксплуатация и сервинг LLM-систем (ИТМО, магистратура AI, 2025--2026)\

| Задача | Разработка Агентной платформы |
|------|--------------------------------------------------|
| Автор | Хамицаев Александр |

## 1. Описание

API-шлюз для LLM-запросов с интеллектуальной балансировкой нагрузки, реестром A2A-агентов, guardrails и полной телеметрией.

Платформа предоставляет OpenAI-совместимый эндпоинт `/v1/chat/completions`, за которым стоит пул LLM-провайдеров с динамической маршрутизацией.

### Возможности

- Проксирование запросов к LLM с поддержкой streaming (SSE)
- Балансировка нагрузки: round-robin, weighted, latency-based (EMA), health-aware фильтрация
- Circuit Breaker на уровне провайдера (Closed → Open → Half-Open)
- A2A Agent Registry с Agent Card и токенами авторизации
- Guardrails: детекция prompt injection, маскирование секретов в ответах
- Авторизация: master-токен (полный доступ) + agent-токены (только /v1/chat/completions)
- Телеметрия: OpenTelemetry tracing, Prometheus метрики, Grafana дашборды, MLflow трассировка
- Три демо-агента: Poet, Literary Translator, Orchestrator

## 2. Архитектура

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

### Поток запроса к LLM

1. Клиент отправляет запрос на `/v1/chat/completions` с токеном авторизации
2. Middleware проверяет токен (master или agent)
3. Guardrails проверяют запрос на prompt injection
4. Балансировщик выбирает провайдера по стратегии (latency/health)
5. Circuit Breaker проверяет доступность провайдера
6. Запрос проксируется к LLM-провайдеру
7. Ответ проверяется на утечку секретов
8. Метрики отправляются в OpenTelemetry → Prometheus → Grafana
9. Трейсы пишутся в MLflow

## 3. Быстрый старт

### Требования

- Docker + Docker Compose
- API-ключ Mistral (или другого провайдера)
- Windows 10/11 или Linux

### Запуск

```powershell
# 1. Клонировать репозиторий
git clone <URL_репозитория> agent-platform
cd agent-platform

# 2. Создать .env
copy .env.example .env
# Вписать MISTRAL_API_KEY и MASTER_TOKEN в .env

# 3. Запустить все сервисы
docker-compose up -d --build

# 4. Проверить статус
docker-compose ps
```

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

## 4. Проверка работоспособности

### Health-check

```powershell
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8010/health
curl http://localhost:8011/health
curl http://localhost:8012/health
```

### Добавление LLM-провайдера

```powershell
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
```

### Тестовый запрос к LLM (через Swagger UI)

1. Откройте http://localhost:8000/docs
2. Нажмите Authorize (замок) и введите `Bearer master-secret-token-2026`
3. Выберите POST /v1/chat/completions → Try it out
4. Вставьте:

```json
{
  "model": "mistral-small-latest",
  "messages": [{"role": "user", "content": "Привет!"}],
  "stream": false
}
```

5. Нажмите Execute

### Тестовый запрос через PowerShell

```powershell
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
```

## 5. API Reference

### Авторизация

Все запросы (кроме `/health`, `/metrics`, `/docs`) требуют заголовок:

```
Authorization: Bearer <token>
```

Два типа токенов:

| Тип | Доступ |
|-----|--------|
| Master-токен | Полный доступ ко всем эндпоинтам |
| Agent-токен | Только /v1/chat/completions |

### POST /v1/chat/completions

OpenAI-совместимый эндпоинт для генерации ответов LLM.

**Параметры запроса:**

| Параметр | Тип | Обязательный | Описание |
|----------|-----|--------------|----------|
| model | string | да | Идентификатор модели |
| messages | array | да | Массив сообщений {role, content} |
| stream | bool | нет | SSE-стриминг (по умолчанию: false) |
| temperature | float | нет | Температура генерации |
| max_tokens | int | нет | Максимум токенов в ответе |

**Пример (non-streaming):**

```powershell
$request = @{
    model = "mistral-small-latest"
    messages = @(@{role = "user"; content = "Что такое FastAPI?"})
    stream = $false
    max_tokens = 200
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/v1/chat/completions" -Method POST -Body $request -Headers $headers
```

**Пример (streaming):**

```powershell
$request = @{
    model = "mistral-small-latest"
    messages = @(@{role = "user"; content = "Напиши стихотворение"})
    stream = $true
} | ConvertTo-Json

$response = Invoke-WebRequest -Uri "http://localhost:8000/v1/chat/completions" -Method POST -Body $request -Headers $headers
$response.Content
```

### POST /agents

Регистрация нового агента. Возвращает agent-токен.

```powershell
$agent = @{
    name = "my-agent"
    description = "My custom agent"
    methods = @("run", "execute")
    card = @{ version = "1.0" }
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8001/agents" -Method POST -Body $agent -Headers $headers
```

### GET /agents

Список всех зарегистрированных агентов.

```powershell
Invoke-RestMethod -Uri "http://localhost:8001/agents" -Method GET -Headers $headers
```

### GET /agents/{id}

Получение агента по UUID.

```powershell
Invoke-RestMethod -Uri "http://localhost:8001/agents/{id}" -Method GET -Headers $headers
```

### DELETE /agents/{id}

Удаление агента.

```powershell
Invoke-RestMethod -Uri "http://localhost:8001/agents/{id}" -Method DELETE -Headers $headers
```

### POST /providers

Добавление LLM-провайдера.

```powershell
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
```

### GET /providers

Список всех провайдеров.

```powershell
Invoke-RestMethod -Uri "http://localhost:8002/providers" -Method GET -Headers $headers
```

### PUT /providers/{id}

Обновление провайдера.

```powershell
$update = @{ priority = 20; health_status = "healthy" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8002/providers/{id}" -Method PUT -Body $update -Headers $headers
```

### DELETE /providers/{id}

Удаление провайдера.

```powershell
Invoke-RestMethod -Uri "http://localhost:8002/providers/{id}" -Method DELETE -Headers $headers
```

### Служебные эндпоинты

| Эндпоинт | Метод | Авторизация | Описание |
|----------|-------|-------------|----------|
| /health | GET | нет | Проверка здоровья |
| /metrics | GET | нет | Prometheus метрики |
| /docs | GET | нет | Swagger UI |
| /openapi.json | GET | нет | OpenAPI-схема |

## 6. Демо-агенты

### Poet Agent (:8010)

Пишет стихи на русском языке в заданном стиле.

```powershell
$poem = @{
    theme = "осень"
    style = "есенин"
    lines = 4
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8010/write" -Method POST -Body $poem -ContentType "application/json"
```

### Literary Translator (:8011)

Переводит тексты с сохранением литературного стиля.

```powershell
$translate = @{
    poem = "Осень наступила, листья пожелтели"
    from_style = "есенин"
    to_style = "байрон"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8011/translate_poem" -Method POST -Body $translate -ContentType "application/json"
```

### Orchestrator Agent (:8012)

Координирует работу Poet и Translator. Генерирует стихи, оценивает качество (≥5/10), переводит.

```powershell
$task = @{
    theme = "осенняя природа"
    count = 2
    max_stanzas = 4
    russian_style = "есенин"
    english_style = "байрон"
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "http://localhost:8012/generate_poems" -Method POST -Body $task -ContentType "application/json"
$response.poems | Format-Table index, poet_score, translator_score, poet_attempts
```

## 7. Балансировка нагрузки

### Стратегии

| Стратегия | Описание |
|-----------|----------|
| Round Robin | Циклический перебор провайдеров |
| Weighted | Выбор с вероятностью, пропорциональной priority |
| Latency-based (EMA) | Выбор провайдера с наименьшей средней задержкой (α=0.3) |
| Health-aware | Исключение нездоровых провайдеров из пула |

### Circuit Breaker

Защита от каскадных отказов. Три состояния:

| Состояние | Поведение |
|-----------|-----------|
| CLOSED | Нормальная работа, подсчёт ошибок |
| OPEN | Все запросы отклоняются, ожидание recovery_timeout (30 сек) |
| HALF_OPEN | Один пробный запрос: успех → CLOSED, неуспех → OPEN |

**Параметры:**

- `failure_threshold = 3` — количество ошибок для перехода в OPEN
- `recovery_timeout = 30` — секунд до перехода в HALF_OPEN

## 8. Guardrails

### Prompt Injection Detection

Regex-детекция типичных паттернов:

- "ignore previous instructions"
- "you are now"
- "reveal your instructions"
- "system prompt"

Заблокированные запросы возвращают 400 Bad Request.

### Secret Leak Detection

Маскирование секретов в ответах LLM:

| Паттерн | Замена |
|---------|--------|
| `sk-[A-Za-z0-9]{32,}` | `[REDACTED_API_KEY]` |
| `AKIA[A-Z0-9]{16}` | `[REDACTED_AWS_KEY]` |
| `Bearer [A-Za-z0-9\-_\.]+` | `[REDACTED_TOKEN]` |
| `-----BEGIN PRIVATE KEY-----` | `[REDACTED_PRIVATE_KEY]` |

## 9. Наблюдаемость

### Метрики (Prometheus + Grafana)

Платформа экспортирует метрики через `/metrics`:

| Метрика | Тип | Описание |
|---------|-----|----------|
| `agent_platform_llm_requests_total` | Counter | Запросы по модели/провайдеру/статусу |
| `agent_platform_llm_request_duration_seconds` | Histogram | Латентность (end-to-end) |
| `agent_platform_llm_ttft_seconds` | Histogram | Time to First Token |
| `agent_platform_llm_tpot_seconds` | Histogram | Time per Output Token |
| `agent_platform_llm_tokens_input_total` | Counter | Входные токены |
| `agent_platform_llm_tokens_output_total` | Counter | Выходные токены |
| `agent_platform_llm_cost_total` | Counter | Стоимость в USD |
| `agent_platform_llm_circuit_breaker_state` | Gauge | Состояние CB (0=CLOSED, 1=OPEN, 2=HALF_OPEN) |
| `container_cpu_usage_seconds_total` | Counter | CPU контейнеров |

### Дашборд Grafana

Доступен на http://localhost:3000/d/llm-platform-dashboard (admin/admin).

**Панели:**

- Latency by Provider (p50/p95)
- Traffic Distribution (pie chart)
- Response Codes (bar chart)
- Request Rate (RPS)
- Cost per Model
- TTFT (p50/p95)
- TPOT (p50/p95)
- Circuit Breaker Status
- CPU Usage by Container
- Service Status

### Трассировка (MLflow)

Доступна на http://localhost:5000.

**Трейсы для:**

- LLM-вызовов: модель, провайдер, промпт, длительность, токены, стоимость
- Агентов: регистрация, вызовы методов, caller
- Оркестратора: генерация стихов, попытки, оценки качества

### OpenTelemetry

Распределённая трассировка через OpenTelemetry Collector. Все HTTP-запросы оборачиваются в спаны.

## 10. Нагрузочное тестирование

### Запуск теста

```powershell
# 10 параллельных запросов к оркестратору
1..10 | ForEach-Object -Parallel {
    $task = @{
        theme = "осень"
        count = 1
        russian_style = "есенин"
        english_style = "байрон"
    } | ConvertTo-Json
    
    try {
        Invoke-RestMethod -Uri "http://localhost:8012/generate_poems" -Method POST -Body $task -ContentType "application/json"
    } catch {
        Write-Host "Request failed: $_"
    }
} -ThrottleLimit 5
```

### Что проверяется

| Метрика | Где смотреть |
|---------|--------------|
| Throughput (RPS) | Grafana → Request Rate |
| Латентность (p95) | Grafana → Latency by Provider |
| TTFT | Grafana → TTFT |
| Переключение провайдеров | Grafana → Circuit Breaker Status |
| Трейсы вызовов | MLflow |

## 11. Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `MASTER_TOKEN` | `master-secret-token-2026` | Master-токен для авторизации |
| `BALANCER_STRATEGY` | `latency` | Стратегия балансировки |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector:4317` | Endpoint OpenTelemetry |
| `MLFLOW_TRACKING_URI` | `http://mlflow:5000` | URL MLflow |
| `LLM_PROXY_URL` | `http://llm-proxy:8000` | URL балансировщика |
| `DATABASE_URL` | `postgresql://agent:agentpass@postgres:5432/agent_platform` | Подключение к БД |

## 12. Стек технологий

| Компонент | Технология |
|-----------|------------|
| Язык | Python 3.11 |
| Web-фреймворк | FastAPI + Uvicorn |
| HTTP-клиент | httpx (async) |
| Валидация | Pydantic v2 |
| База данных | PostgreSQL + SQLAlchemy (async) |
| Контейнеризация | Docker + Docker Compose |
| Метрики | OpenTelemetry + Prometheus |
| Визуализация | Grafana |
| Трассировка | MLflow |
| Мониторинг контейнеров | cAdvisor |

## 13. Структура проекта

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
