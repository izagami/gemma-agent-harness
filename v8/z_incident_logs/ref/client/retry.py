"""Retry with exponential backoff for outgoing HTTP calls."""
import time
from dataclasses import dataclass

from client.http import TransportError, header


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    base_delay_ms: int = 100
    multiplier: float = 2.0
    max_delay_ms: int = 5000
    retry_on: tuple = (502, 503, 504)

    def delay_ms(self, retry_no):
        """Milliseconds to wait before retry number `retry_no` (1-based)."""
        return min(self.max_delay_ms, self.base_delay_ms * self.multiplier ** (retry_no - 1))


RETRYABLE_ERRORS = (TransportError, ConnectionError, TimeoutError)
NON_IDEMPOTENT = ("POST", "PATCH")


def _retry_after_ms(resp):
    v = header(resp.headers or {}, "Retry-After")
    if v is not None and str(v).strip().isdigit():
        return int(str(v).strip()) * 1000
    return None


def call_with_retry(send, request, policy, sleep=time.sleep):
    """Call send(request) until it succeeds or the policy gives up."""
    may_retry = request.method.upper() not in NON_IDEMPOTENT or header(request.headers or {}, "Idempotency-Key") is not None
    limit = policy.max_attempts if may_retry else 1
    attempt = 0
    while True:
        attempt += 1
        try:
            resp = send(request)
        except RETRYABLE_ERRORS:
            if attempt >= limit:
                raise
            sleep(policy.delay_ms(attempt) / 1000)
            continue
        if resp.status not in policy.retry_on or attempt >= limit:
            return resp
        d = policy.delay_ms(attempt)
        ra = _retry_after_ms(resp)
        if ra is not None:
            d = max(d, ra)
        sleep(d / 1000)
