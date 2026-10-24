# Checkout path (production)

    client -> gateway -> auth (token check)
                     -> orders -> inventory (in-process)
                               -> payments  (POST /charge, via client/payments.py + client/retry.py)

* gateway: edge proxy. One log line per finished request, local time of the host (JST).
  Generates the request id (`req=`) and forwards it to auth and orders.
* auth: token verification. Syslog format; the host clock is JST and the lines carry no zone.
* orders: JSON lines, `ts` is epoch milliseconds (UTC). The forwarded request id is logged as `rid`.
  Each checkout gets one payment reference (`payment_ref`, `pr-NNNNNN`) that is sent to payments on every attempt.
* payments: one line per finished request, UTC. Also runs the nightly refund batch (refs `rf-...`).

Retry settings for outgoing calls from orders live in `config/orders.ini` (section `[retry]`).

Incident 2026-09-13 (on-call notes): customers reported failed checkouts around 03:1x JST and at least
one double charge. payments was also paging about its DB pool. Logs for the window are in logs/.
