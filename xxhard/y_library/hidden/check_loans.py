import os, sys, tempfile
sys.path.insert(0, "/work")
from datetime import date
from app.main import create_app
from app.storage import Storage

day = [date(2026, 10, 1)]
app = create_app(today=lambda: day[0])
H = app.handle

def eq(res, status, body=None):
    assert res.status == status, (res.status, res.body, status)
    if body is not None:
        assert res.body == body, (res.body, body)
    return res.body

for i in range(1, 7):
    eq(H("POST", "/books", {"title": f"t{i}", "author": "a"}), 201)
eq(H("POST", "/members", {"name": "A", "email": "a@x.jp"}), 201)
eq(H("POST", "/members", {"name": "B", "email": "b@x.jp"}), 201)

# validation
eq(H("POST", "/loans", {}), 400, {"error": "validation", "fields": {"book_id": "required", "member_id": "required"}})
eq(H("POST", "/loans", {"book_id": "1", "member_id": 1, "days": 31, "x": 1}), 400,
   {"error": "validation", "fields": {"book_id": "must be an integer", "days": "must be <= 30", "x": "unknown field"}})
eq(H("POST", "/loans", {"book_id": 1, "member_id": True, "days": 0}), 400,
   {"error": "validation", "fields": {"days": "must be >= 1", "member_id": "must be an integer"}})
eq(H("POST", "/loans", None), 400, {"error": "validation", "fields": {"_body": "must be an object"}})
# not found: book checked before member
eq(H("POST", "/loans", {"book_id": 99, "member_id": 99}), 404, {"error": "not_found", "detail": "book not found"})
eq(H("POST", "/loans", {"book_id": 1, "member_id": 99}), 404, {"error": "not_found", "detail": "member not found"})

# create
eq(H("POST", "/loans", {"book_id": 1, "member_id": 1}), 201,
   {"id": 1, "book_id": 1, "member_id": 1, "loaned_on": "2026-10-01", "due_on": "2026-10-15", "returned_on": None})
eq(H("POST", "/loans", {"book_id": 1, "member_id": 2}), 409, {"error": "conflict", "detail": "book already on loan"})
eq(H("POST", "/loans", {"book_id": 2, "member_id": 1, "days": 30}), 201,
   {"id": 2, "book_id": 2, "member_id": 1, "loaned_on": "2026-10-01", "due_on": "2026-10-31", "returned_on": None})
day[0] = date(2026, 10, 5)
eq(H("POST", "/loans", {"book_id": 3, "member_id": 1, "days": 1}), 201)
eq(H("POST", "/loans", {"book_id": 4, "member_id": 1}), 409, {"error": "conflict", "detail": "loan limit reached"})
# book check comes before the limit check
eq(H("POST", "/loans", {"book_id": 2, "member_id": 1}), 409, {"error": "conflict", "detail": "book already on loan"})

# delete blocked while on loan
eq(H("DELETE", "/books/1"), 409, {"error": "conflict", "detail": "book on loan"})
eq(H("GET", "/books/1"), 200)

# return
eq(H("POST", "/loans/1/return"), 200,
   {"id": 1, "book_id": 1, "member_id": 1, "loaned_on": "2026-10-01", "due_on": "2026-10-15", "returned_on": "2026-10-05"})
eq(H("POST", "/loans/1/return"), 409, {"error": "conflict", "detail": "already returned"})
eq(H("POST", "/loans/77/return"), 404, {"error": "not_found", "detail": "loan not found"})
eq(H("GET", "/loans/1/return"), 405, {"error": "method_not_allowed"})
# limit frees up after a return
eq(H("POST", "/loans", {"book_id": 4, "member_id": 1}), 201)
eq(H("POST", "/loans", {"book_id": 1, "member_id": 2, "days": 3}), 201)

# member loans
b = eq(H("GET", "/members/1/loans"), 200)
assert [l["id"] for l in b["loans"]] == [1, 2, 3, 4], b
assert set(b["loans"][0]) == {"id", "book_id", "member_id", "loaned_on", "due_on", "returned_on"}, b
b = eq(H("GET", "/members/1/loans?active=1"), 200)
assert [l["id"] for l in b["loans"]] == [2, 3, 4], b
eq(H("GET", "/members/9/loans"), 404, {"error": "not_found", "detail": "member not found"})

# overdue: not returned and due_on < today
day[0] = date(2026, 10, 6)   # loan 3 due 10-06 -> not yet
eq(H("GET", "/loans/overdue"), 200, {"loans": []})
day[0] = date(2026, 10, 7)
b = eq(H("GET", "/loans/overdue"), 200)
assert [l["id"] for l in b["loans"]] == [3], b
day[0] = date(2026, 10, 20)
b = eq(H("GET", "/loans/overdue"), 200)
assert [l["id"] for l in b["loans"]] == [3, 4, 5], b
H("POST", "/loans/4/return")
b = eq(H("GET", "/loans/overdue"), 200)
assert [l["id"] for l in b["loans"]] == [3, 5], b

# returned loans do not block deletion
eq(H("DELETE", "/books/4"), 204)
# existing routes unchanged
eq(H("GET", "/members/1"), 200)
eq(H("GET", "/loans"), 405, {"error": "method_not_allowed"})

# persistence
with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "db.json")
    a1 = create_app(Storage(p), today=lambda: date(2026, 1, 10))
    a1.handle("POST", "/books", {"title": "t", "author": "a"})
    a1.handle("POST", "/members", {"name": "A", "email": "a@x.jp"})
    eq(a1.handle("POST", "/loans", {"book_id": 1, "member_id": 1, "days": 2}), 201)
    a2 = create_app(Storage(p), today=lambda: date(2026, 1, 20))
    b = eq(a2.handle("GET", "/members/1/loans"), 200)
    assert b["loans"] == [{"id": 1, "book_id": 1, "member_id": 1, "loaned_on": "2026-01-10",
                           "due_on": "2026-01-12", "returned_on": None}], b
    eq(a2.handle("POST", "/loans", {"book_id": 1, "member_id": 1}), 409)
    eq(a2.handle("POST", "/loans/1/return"), 200)
    a3 = create_app(Storage(p), today=lambda: date(2026, 1, 21))
    assert eq(a3.handle("POST", "/loans", {"book_id": 1, "member_id": 1}), 201)["id"] == 2
    assert a3.handle("GET", "/members/1/loans").body["loans"][0]["returned_on"] == "2026-01-20"
print("ok")
