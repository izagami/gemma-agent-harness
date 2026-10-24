"""Client for the payments service (POST /charge)."""
from client.http import Request
from client.retry import call_with_retry


def charge(send, policy, order_id, amount, payment_ref, sleep=None):
    """Charge `amount` yen for an order. payment_ref is generated once per checkout and reused on retries."""
    req = Request("POST", "http://payments.internal/charge",
                  headers={"Content-Type": "application/json", "X-Payment-Ref": payment_ref,
                           "Idempotency-Key": payment_ref},
                  body={"order_id": order_id, "amount": amount, "ref": payment_ref})
    kw = {} if sleep is None else {"sleep": sleep}
    return call_with_retry(send, req, policy, **kw)
