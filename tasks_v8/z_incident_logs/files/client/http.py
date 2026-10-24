"""Minimal request/response types. The transport (`send`) is injected so it can be faked in tests."""
from dataclasses import dataclass, field


@dataclass
class Request:
    method: str
    url: str
    headers: dict = field(default_factory=dict)
    body: dict = None


@dataclass
class Response:
    status: int
    headers: dict = field(default_factory=dict)
    body: dict = None

    @property
    def ok(self):
        return 200 <= self.status < 300


def header(headers, name, default=None):
    """Case-insensitive header lookup."""
    low = name.lower()
    for k, v in headers.items():
        if k.lower() == low:
            return v
    return default


class TransportError(Exception):
    """Raised by a transport when no response was received."""
