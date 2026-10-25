On 2026-09-13 (UTC) customers saw failed checkouts and at least one double charge. This folder contains the production logs of the four services involved (logs/), the orders service's shared HTTP client code (client/), its configuration (config/) and a short description of the services and log formats (docs/services.md). Investigate the incident and fix the client.

Part 1 — write `incident.json` (in this folder) with exactly this information, derived from the logs:

```json
{
  "first_error_utc": "YYYY-MM-DDTHH:MM:SS.mmmZ",
  "root_service": "gateway | auth | orders | payments",
  "failed_order_ids": ["O-....", "..."],
  "charge_attempts": 0,
  "double_charged_order_ids": ["O-....", "..."]
}
```

Definitions (follow them literally):
- A *checkout request* is a gateway request `POST /api/orders/<order_id>/checkout`. A *failed checkout request* is one the gateway answered with a 5xx status. A log line *belongs to* a gateway request if it carries that request's id, or if it is a payments line whose payment reference was used by that request (see docs/services.md for how ids are propagated).
- `failed_order_ids`: order ids whose **last** checkout request (by time) is a failed checkout request. Sorted ascending, no duplicates.
- `first_error_utc`: the timestamp of the earliest line with level `ERROR`, in any of the four logs, that belongs to a failed checkout request. UTC with milliseconds and a trailing `Z`.
- `root_service`: the service whose log contains that line.
- `charge_attempts`: the number of `POST /charge` lines in the payments log that belong to failed checkout requests (every failed checkout request counts, also those whose order later succeeded).
- `double_charged_order_ids`: order ids for which payments answered `POST /charge` with status 200 more than once in total (over all checkout requests of that order). Sorted ascending.

Part 2 — fix `client/` so that outgoing calls follow the intended retry behavior below (the logs show that production did something else). Do not change the function signatures, `client/config.py`'s `DEFAULTS`, `config/`, `logs/`, `docs/` or the existing tests; `python3 -m unittest discover -s tests` must pass. You may add tests.

`call_with_retry(send, request, policy, sleep=time.sleep)`:
1. `send(request)` returns a `Response` or raises a transport error (`client.http.TransportError`, `ConnectionError` or `TimeoutError`).
2. `send` is called at most `policy.max_attempts` times in total (the first call included).
3. A response is retried only if its status is in `policy.retry_on`; any other response is returned immediately. Transport errors are always retryable.
4. Requests with method `POST` or `PATCH` are retried only if the request has an `Idempotency-Key` header (header names are case-insensitive); otherwise `send` is called exactly once. Other methods may always be retried.
5. Before the k-th retry (k = 1, 2, ...) call `sleep(d / 1000)` (seconds) with `d = min(policy.max_delay_ms, policy.base_delay_ms * policy.multiplier ** (k - 1))` milliseconds. If the response being retried has a `Retry-After` header whose value is a non-negative integer number of seconds, use `max(d, that value * 1000)` instead (this is not capped by `max_delay_ms`). `sleep` is called exactly once per retry and never after the last attempt.
6. When attempts run out, return the last response, or re-raise the last transport error if the last attempt raised one.

`load_retry_policy(path)` must read the `[retry]` section of the given ini file (as in config/orders.ini); keys that are missing take the values in `DEFAULTS`; `retry_on` is a comma-separated list of integers with optional spaces.

`client.payments.charge(...)` must send the payment reference as the `Idempotency-Key` header so that charges are retried safely.
