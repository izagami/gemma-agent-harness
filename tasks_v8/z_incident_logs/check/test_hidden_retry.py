import os, sys, tempfile, unittest
sys.path.insert(0, "/work")
from client.http import Request, Response, TransportError
from client.retry import RetryPolicy, call_with_retry
from client.config import load_retry_policy, DEFAULTS
from client import payments


class Seq:
    def __init__(self, *items):
        self.items = list(items); self.calls = []

    def __call__(self, req):
        self.calls.append(req)
        x = self.items.pop(0)
        if isinstance(x, BaseException):
            raise x
        return x


def R(status, **h):
    return Response(status, headers={k.replace("_", "-"): v for k, v in h.items()})


P = RetryPolicy(max_attempts=4, base_delay_ms=200, multiplier=2.0, max_delay_ms=1000, retry_on=(502, 503, 504))


class Hidden(unittest.TestCase):
    def run_(self, send, req, policy=P):
        sl = []
        try:
            r = call_with_retry(send, req, policy, sleep=sl.append)
        except Exception as e:
            r = e
        return r, sl

    def assertSleeps(self, got, exp):
        self.assertEqual(len(got), len(exp), got)
        for g, e in zip(got, exp):
            self.assertAlmostEqual(g, e, places=6)

    def test_backoff_sequence_and_cap(self):
        send = Seq(R(503), R(503), R(502), R(200))
        r, sl = self.run_(send, Request("GET", "u"))
        self.assertEqual(r.status, 200); self.assertEqual(len(send.calls), 4)
        self.assertSleeps(sl, [0.2, 0.4, 0.8])

    def test_cap_applies(self):
        p = RetryPolicy(max_attempts=5, base_delay_ms=300, multiplier=3, max_delay_ms=1000, retry_on=(503,))
        r, sl = self.run_(Seq(R(503), R(503), R(503), R(503), R(503)), Request("GET", "u"), p)
        self.assertEqual(r.status, 503)
        self.assertSleeps(sl, [0.3, 0.9, 1.0, 1.0])

    def test_exhausted_returns_last_no_sleep_after(self):
        send = Seq(R(503), R(504), R(502), R(503), R(200))
        r, sl = self.run_(send, Request("GET", "u"))
        self.assertEqual((r.status, len(send.calls)), (503, 4)); self.assertEqual(len(sl), 3)

    def test_non_retryable_status(self):
        for st in (200, 201, 400, 404, 409, 500):
            send = Seq(R(st), R(200))
            r, sl = self.run_(send, Request("GET", "u"))
            self.assertEqual((r.status, len(send.calls), sl), (st, 1, []))

    def test_custom_retry_on(self):
        p = RetryPolicy(max_attempts=3, base_delay_ms=10, multiplier=1, max_delay_ms=100, retry_on=(500,))
        r, sl = self.run_(Seq(R(500), R(503)), Request("GET", "u"), p)
        self.assertEqual(r.status, 503); self.assertSleeps(sl, [0.01])

    def test_transport_errors(self):
        send = Seq(TransportError("x"), ConnectionError("y"), R(200))
        r, sl = self.run_(send, Request("PUT", "u"))
        self.assertEqual(r.status, 200); self.assertSleeps(sl, [0.2, 0.4])
        send = Seq(TimeoutError("t"), R(503), TimeoutError("t2"), TimeoutError("t3"))
        r, sl = self.run_(send, Request("DELETE", "u"))
        self.assertIsInstance(r, TimeoutError); self.assertEqual(str(r), "t3"); self.assertEqual(len(sl), 3)

    def test_post_without_key_not_retried(self):
        for m in ("POST", "PATCH", "post"):
            send = Seq(R(503), R(200))
            r, sl = self.run_(send, Request(m, "u", headers={"Content-Type": "application/json"}))
            self.assertEqual((r.status, len(send.calls), sl), (503, 1, []))
            send = Seq(TimeoutError("t"), R(200))
            r, sl = self.run_(send, Request(m, "u"))
            self.assertIsInstance(r, TimeoutError); self.assertEqual(sl, [])

    def test_post_with_key_retried(self):
        send = Seq(R(503), TimeoutError("t"), R(200))
        r, sl = self.run_(send, Request("POST", "u", headers={"idempotency-key": "k1"}))
        self.assertEqual(r.status, 200); self.assertSleeps(sl, [0.2, 0.4])

    def test_retry_after(self):
        send = Seq(R(503, Retry_After="3"), R(503, Retry_After="0"), R(503, **{"retry-after": "x"}), R(200))
        r, sl = self.run_(send, Request("GET", "u"))
        self.assertEqual(r.status, 200); self.assertSleeps(sl, [3.0, 0.4, 0.8])
        p = RetryPolicy(max_attempts=2, base_delay_ms=100, multiplier=2, max_delay_ms=500, retry_on=(503,))
        r, sl = self.run_(Seq(R(503, Retry_After="7"), R(200)), Request("GET", "u"), p)
        self.assertSleeps(sl, [7.0])

    def test_single_attempt_policy(self):
        p = RetryPolicy(max_attempts=1, base_delay_ms=100, multiplier=2, max_delay_ms=500, retry_on=(503,))
        r, sl = self.run_(Seq(R(503), R(200)), Request("GET", "u"), p)
        self.assertEqual((r.status, sl), (503, []))

    def test_load_policy(self):
        d = tempfile.mkdtemp(); p = os.path.join(d, "s.ini")
        with open(p, "w") as f:
            f.write("[http]\ntimeout_ms = 5\n\n[retry]\nmax_attempts = 2\nbase_delay_ms = 50\nretry_on = 500 ,503\n")
        pol = load_retry_policy(p)
        self.assertEqual((pol.max_attempts, pol.base_delay_ms, tuple(pol.retry_on)), (2, 50, (500, 503)))
        self.assertEqual(pol.multiplier, DEFAULTS["multiplier"]); self.assertEqual(pol.max_delay_ms, DEFAULTS["max_delay_ms"])
        pol = load_retry_policy("/work/config/orders.ini")
        self.assertEqual((pol.max_attempts, pol.base_delay_ms, pol.max_delay_ms, tuple(pol.retry_on)), (3, 200, 2000, (502, 503, 504)))
        self.assertEqual(float(pol.multiplier), 2.0)

    def test_payments_charge_idempotent(self):
        send = Seq(R(503), R(200))
        sl = []
        r = payments.charge(send, P, "O-1", 1200, "pr-000777", sleep=sl.append)
        self.assertEqual((r.status, len(send.calls)), (200, 2))
        hdr = {k.lower(): v for k, v in send.calls[0].headers.items()}
        self.assertEqual(hdr.get("idempotency-key"), "pr-000777")
        self.assertEqual(send.calls[0].method, "POST")


if __name__ == "__main__":
    unittest.main()
