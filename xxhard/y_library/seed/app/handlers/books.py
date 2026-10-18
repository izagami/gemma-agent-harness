from app.errors import NotFound
from app.http import created, no_content, ok
from app.validation import Field, validate

BOOK = {
    "title": Field(str, max_len=200),
    "author": Field(str, max_len=100),
    "year": Field(int, required=False, min=0, max=2100, nullable=True),
}


def get_or_404(app, book_id):
    book = app.storage.get("books", book_id)
    if book is None:
        raise NotFound("book not found")
    return book


def create_book(app, req):
    data = validate(req.body, BOOK)
    return created(app.storage.insert("books", data))


def get_book(app, req):
    return ok(get_or_404(app, req.params["id"]))


def list_books(app, req):
    where = {}
    if "author" in req.query:
        where["author"] = req.query["author"]
    return ok({"books": app.storage.find("books", **where)})


def update_book(app, req):
    get_or_404(app, req.params["id"])
    data = validate(req.body, BOOK, partial=True)
    return ok(app.storage.update("books", req.params["id"], data))


def delete_book(app, req):
    get_or_404(app, req.params["id"])
    app.storage.delete("books", req.params["id"])
    return no_content()
