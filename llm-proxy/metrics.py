from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
import os

resource = Resource(attributes={SERVICE_NAME: "llm-proxy"})
reader = PeriodicExportingMetricReader(
    OTLPMetricExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"), insecure=True)
)
provider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(provider)

meter = metrics.get_meter("llm.proxy")

request_counter = meter.create_counter(
    "llm_requests_total",
    description="Total number of LLM requests",
)

request_duration = meter.create_histogram(
    "llm_request_duration_seconds",
    description="Request duration in seconds",
)

ttft_histogram = meter.create_histogram(
    "llm_ttft_seconds",
    description="Time to first token in seconds",
)

tpot_histogram = meter.create_histogram(
    "llm_tpot_seconds",
    description="Time per output token in seconds",
)

tokens_input_counter = meter.create_counter(
    "llm_tokens_input_total",
    description="Total input tokens processed",
)

tokens_output_counter = meter.create_counter(
    "llm_tokens_output_total",
    description="Total output tokens generated",
)

cost_counter = meter.create_counter(
    "llm_cost_total",
    description="Total cost in USD",
)

def record_request(model: str, provider_id: str, status: str, duration: float, ttft: float, tokens_in: int, tokens_out: int, cost: float, tpot: float = 0.0):
    attributes = {"model": model, "provider": provider_id, "status": status}
    request_counter.add(1, attributes)
    request_duration.record(duration, attributes)
    ttft_histogram.record(ttft, attributes)
    if tpot > 0:
        tpot_histogram.record(tpot, attributes)
    tokens_input_counter.add(tokens_in, attributes)
    tokens_output_counter.add(tokens_out, attributes)
    cost_counter.add(cost, attributes)