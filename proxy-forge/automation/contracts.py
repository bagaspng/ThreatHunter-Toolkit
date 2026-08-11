from dataclasses import dataclass, field
from typing import Any

@dataclass
class PageProfile:
    is_spa: bool
    action_url: str
    method: str                        # "GET" or "POST"
    fields: list[str]                  # all input field names
    hidden_inputs: dict[str, str]      # name -> value
    honeypot_candidates: list[str]     # field names to never fill
    raw_html: str

@dataclass
class SubmissionResult:
    success: bool
    status_code: int | None
    response_text: str | None
    error: Exception | None = None

class ExhaustedProxyError(Exception):
    """Raised when all proxy retries fail for a target URL."""
    pass

class EmptyProxyPoolError(Exception):
    """Raised when no working proxies are available in ProxyPool."""
    pass
