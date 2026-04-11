import asyncio
import time
import random
from typing import List, Dict, Any, Optional
from collections import defaultdict
import httpx
from pydantic import BaseModel

from circuit_breaker import CircuitBreaker


class ProviderInfo(BaseModel):
    id: str
    name: str
    base_url: str
    api_key: Optional[str] = None
    models: List[str]
    priority: int
    health_status: str = "healthy"
    last_error: Optional[str] = None
    avg_latency: float = 0.0
    consecutive_failures: int = 0
    last_checked: float = 0.0
    price_per_input_token: float = 0.0
    price_per_output_token: float = 0.0
    
    class Config:
        arbitrary_types_allowed = True


class BalancerStrategy:
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"
    LATENCY = "latency"
    HEALTH_AWARE = "health_aware"


class LoadBalancer:
    def __init__(self, strategy: str = BalancerStrategy.LATENCY):
        self.strategy = strategy
        self.providers: Dict[str, ProviderInfo] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.round_robin_index = 0
        self.lock = asyncio.Lock()
        self.failure_threshold = 3
        self.recovery_timeout = 30

    def update_providers(self, providers: List[ProviderInfo]):
        for p in providers:
            if p.id in self.providers:
                self.providers[p.id].name = p.name
                self.providers[p.id].base_url = p.base_url
                self.providers[p.id].api_key = p.api_key
                self.providers[p.id].models = p.models
                self.providers[p.id].priority = p.priority
                self.providers[p.id].price_per_input_token = p.price_per_input_token
                self.providers[p.id].price_per_output_token = p.price_per_output_token
            else:
                self.providers[p.id] = p
                self.circuit_breakers[p.id] = CircuitBreaker(
                    failure_threshold=self.failure_threshold,
                    recovery_timeout=self.recovery_timeout
                )

    async def select_provider(self, model: str) -> Optional[ProviderInfo]:
        async with self.lock:
            candidates = [
                p for p in self.providers.values()
                if model in p.models and self._is_healthy(p)
            ]
            if not candidates:
                return None

            if self.strategy == BalancerStrategy.ROUND_ROBIN:
                selected = candidates[self.round_robin_index % len(candidates)]
                self.round_robin_index = (self.round_robin_index + 1) % len(candidates)
                return selected

            elif self.strategy == BalancerStrategy.WEIGHTED:
                weights = [p.priority for p in candidates]
                selected = random.choices(candidates, weights=weights, k=1)[0]
                return selected

            elif self.strategy == BalancerStrategy.LATENCY:
                return min(candidates, key=lambda p: p.avg_latency or float('inf'))

            elif self.strategy == BalancerStrategy.HEALTH_AWARE:
                return min(candidates, key=lambda p: p.avg_latency or float('inf'))

            else:
                selected = candidates[self.round_robin_index % len(candidates)]
                self.round_robin_index = (self.round_robin_index + 1) % len(candidates)
                return selected

    def _is_healthy(self, provider: ProviderInfo) -> bool:
        if provider.id in self.circuit_breakers:
            cb = self.circuit_breakers[provider.id]
            if cb.state.value == "open":
                return False
        return True

    def record_success(self, provider_id: str, latency: float):
        if provider_id in self.providers:
            p = self.providers[provider_id]
            alpha = 0.3
            p.avg_latency = alpha * latency + (1 - alpha) * p.avg_latency
            p.consecutive_failures = 0
            p.health_status = "healthy"
            p.last_checked = time.time()
            
            if provider_id in self.circuit_breakers:
                self.circuit_breakers[provider_id]._on_success()

    def record_failure(self, provider_id: str, error: str = ""):
        if provider_id in self.providers:
            p = self.providers[provider_id]
            p.consecutive_failures += 1
            p.last_error = error
            p.last_checked = time.time()
            if p.consecutive_failures >= self.failure_threshold:
                p.health_status = "unhealthy"
            
            if provider_id in self.circuit_breakers:
                self.circuit_breakers[provider_id]._on_failure()

    def get_circuit_breaker(self, provider_id: str) -> Optional[CircuitBreaker]:
        return self.circuit_breakers.get(provider_id)