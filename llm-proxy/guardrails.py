import re
from typing import Tuple, Optional

# Prompt Injection паттерны
INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+)?(?:previous|above|the\s+above)\s+(?:instructions?|prompts?|messages?)",
    r"you\s+are\s+(?:now|no\s+longer)\s+(?:an?\s+)?(?:AI|assistant|language\s+model)",
    r"reveal\s+(?:your|the)\s+(?:instructions?|system\s+prompt|prompt)",
    r"disregard\s+(?:all\s+)?(?:previous\s+)?(?:instructions?|constraints?)",
    r"system\s*:\s*.*?(?:prompt|instruction)",
    r"<\|im_start\|>",
    r"\[INST\].*?\[/INST\]",
]

# Secret Leak паттерны
SECRET_PATTERNS = {
    r'sk-[A-Za-z0-9]{32,}': '[REDACTED_OPENAI_KEY]',
    r'sk-ant-[A-Za-z0-9]{32,}': '[REDACTED_ANTHROPIC_KEY]',
    r'AKIA[A-Z0-9]{16}': '[REDACTED_AWS_KEY]',
    r'Bearer\s+[A-Za-z0-9\-_\.]+': '[REDACTED_BEARER_TOKEN]',
    r'Authorization:\s*Bearer\s+[A-Za-z0-9\-_\.]+': 'Authorization: Bearer [REDACTED]',
    r'password["\s:=]+["\']?[^"\'\s]{8,}': 'password: [REDACTED]',
    r'api_key["\s:=]+["\']?[A-Za-z0-9\-_]{16,}': 'api_key: [REDACTED]',
    r'-----BEGIN\s+(?:RSA|DSA|EC|OPENSSH)\s+PRIVATE\s+KEY-----[\s\S]*?-----END\s+(?:RSA|DSA|EC|OPENSSH)\s+PRIVATE\s+KEY-----': '[REDACTED_PRIVATE_KEY]',
}


def detect_prompt_injection(text: str) -> Tuple[bool, Optional[str]]:
    """Проверка на prompt injection."""
    for pattern in INJECTION_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return True, f"Detected: {match.group(0)[:50]}"
    return False, None


def mask_secrets(text: str) -> Tuple[str, int]:
    """Маскирование секретов в тексте."""
    masked_count = 0
    for pattern, replacement in SECRET_PATTERNS.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        masked_count += len(matches)
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text, masked_count


def validate_request(messages: list) -> Tuple[bool, Optional[str]]:
    """Валидация запроса на prompt injection."""
    for msg in messages:
        if msg.get("role") == "user":
            is_injection, detected = detect_prompt_injection(msg.get("content", ""))
            if is_injection:
                return False, detected
    return True, None


def sanitize_response(text: str) -> Tuple[str, int]:
    """Санитизация ответа LLM."""
    return mask_secrets(text)