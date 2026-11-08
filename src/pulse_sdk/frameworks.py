"""Request-scoped adapter for FastAPI, Django and Flask; no framework dependency."""

import re
from collections.abc import Mapping
from typing import Protocol

from .client import PulseClient


class RequestHeaders(Protocol):
    @property
    def headers(self) -> Mapping[str, str]: ...


def from_authorization(base_url: str, authorization: str | None) -> PulseClient:
    match = re.fullmatch(r"Bearer ([^\s]+)", authorization or "", re.IGNORECASE)
    if not match:
        raise ValueError("A user Bearer session is required")
    return PulseClient(base_url, match.group(1))


def from_request(base_url: str, request: RequestHeaders) -> PulseClient:
    return from_authorization(base_url, request.headers.get("authorization"))
