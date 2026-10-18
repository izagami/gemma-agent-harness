from app.errors import Conflict, NotFound, ValidationError
from app.http import created, ok
from app.validation import Field, validate

MEMBER = {
    "name": Field(str, max_len=100),
    "email": Field(str, max_len=200),
}


def get_or_404(app, member_id):
    member = app.storage.get("members", member_id)
    if member is None:
        raise NotFound("member not found")
    return member


def create_member(app, req):
    data = validate(req.body, MEMBER)
    email = data["email"].strip().lower()
    if email.count("@") != 1 or email.startswith("@") or email.endswith("@"):
        raise ValidationError({"email": "invalid email"})
    if app.storage.find("members", email=email):
        raise Conflict("email already registered")
    data["email"] = email
    return created(app.storage.insert("members", data))


def get_member(app, req):
    return ok(get_or_404(app, req.params["id"]))


def list_members(app, req):
    return ok({"members": app.storage.find("members")})
