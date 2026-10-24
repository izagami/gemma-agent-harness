import unittest

from client.http import Request, Response
from client.retry import RetryPolicy, call_with_retry


class Fake:
    def __init__(self, *statuses):
        self.statuses = list(statuses)
        self.calls = 0

    def __call__(self, req):
        self.calls += 1
        return Response(self.statuses.pop(0))


class RetryTest(unittest.TestCase):
    def test_success_first_try(self):
        send = Fake(200)
        r = call_with_retry(send, Request("GET", "http://x/"), RetryPolicy(), sleep=lambda s: None)
        self.assertEqual((r.status, send.calls), (200, 1))

    def test_get_retried_on_503(self):
        send = Fake(503, 200)
        r = call_with_retry(send, Request("GET", "http://x/"), RetryPolicy(), sleep=lambda s: None)
        self.assertEqual((r.status, send.calls), (200, 2))

    def test_not_retried_on_404(self):
        send = Fake(404, 200)
        r = call_with_retry(send, Request("GET", "http://x/"), RetryPolicy(), sleep=lambda s: None)
        self.assertEqual((r.status, send.calls), (404, 1))


if __name__ == "__main__":
    unittest.main()
