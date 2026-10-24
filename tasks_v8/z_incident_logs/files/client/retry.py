"""Retry with exponential backoff for outgoing HTTP calls."""
import time
from dataclasses import dataclass

from client.http import TransportError


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    base_delay_ms: int = 100
    multiplier: float = 2.0
    max_delay_ms: int = 5000
    retry_on: tuple = (502, 503, 504)

    def delay(self, retry_no):
        """Seconds to wait before retry number `retry_no` (1-based)."""
        d = self.base_delay_ms // 1000 * self.multiplier ** retry_no
        return min(d, self.max_delay_ms)


RETRYABLE_ERRORS = (TransportError, ConnectionError, TimeoutError)


def call_with_retry(send, request, policy, sleep=time.sleep):
    """Call send(request) until it succeeds or the policy gives up."""
    attempt = 0
    while True:
        attempt += 1
        try:
            resp = send(request)
        except RETRYABLE_ERRORS:
            if attempt >= policy.max_attempts:
                raise
            sleep(policy.delay(attempt))
            continue
        if resp.status not in policy.retry_on or attempt >= policy.max_attempts:
            return resp
        sleep(policy.delay(attempt))
