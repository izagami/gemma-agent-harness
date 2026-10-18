from datetime import timedelta

from app.errors import Conflict, NotFound
from app.handlers import members
from app.http import created, ok
from app.validation import Field, validate

LOAN = {
    "book_id": Field(int),
    "member_id": Field(int),
    "days": Field(int, required=False, default=14, min=1, max=30),
}
MAX_ACTIVE = 3


def active_loans(app, **where):
    return [l for l in app.storage.find("loans", **where) if l["returned_on"] is None]


def create_loan(app, req):
    data = validate(req.body, LOAN)
    if app.storage.get("books", data["book_id"]) is None:
        raise NotFound("book not found")
    members.get_or_404(app, data["member_id"])
    if active_loans(app, book_id=data["book_id"]):
        raise Conflict("book already on loan")
    if len(active_loans(app, member_id=data["member_id"])) >= MAX_ACTIVE:
        raise Conflict("loan limit reached")
    today = app.today()
    return created(app.storage.insert("loans", {
        "book_id": data["book_id"], "member_id": data["member_id"],
        "loaned_on": today.isoformat(), "due_on": (today + timedelta(days=data["days"])).isoformat(),
        "returned_on": None}))


def return_loan(app, req):
    loan = app.storage.get("loans", req.params["id"])
    if loan is None:
        raise NotFound("loan not found")
    if loan["returned_on"] is not None:
        raise Conflict("already returned")
    return ok(app.storage.update("loans", loan["id"], {"returned_on": app.today().isoformat()}))


def member_loans(app, req):
    members.get_or_404(app, req.params["id"])
    if req.query.get("active") == "1":
        return ok({"loans": active_loans(app, member_id=req.params["id"])})
    return ok({"loans": app.storage.find("loans", member_id=req.params["id"])})


def overdue(app, req):
    today = app.today().isoformat()
    return ok({"loans": [l for l in active_loans(app) if l["due_on"] < today]})
