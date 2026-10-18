from datetime import date

from app.handlers import books, loans, members
from app.http import Request
from app.router import Router
from app.storage import Storage


class App:
    def __init__(self, storage, today):
        self.storage = storage
        self.today = today          # callable returning a datetime.date
        self.router = Router()

    def handle(self, method, path, body=None):
        return self.router.dispatch(self, Request(method, path, body))


def create_app(storage=None, today=date.today):
    app = App(storage if storage is not None else Storage(), today)
    r = app.router
    r.add("GET", "/books", books.list_books)
    r.add("POST", "/books", books.create_book)
    r.add("GET", "/books/{id:int}", books.get_book)
    r.add("PATCH", "/books/{id:int}", books.update_book)
    r.add("DELETE", "/books/{id:int}", books.delete_book)
    r.add("GET", "/members", members.list_members)
    r.add("POST", "/members", members.create_member)
    r.add("GET", "/members/{id:int}", members.get_member)
    r.add("GET", "/members/{id:int}/loans", loans.member_loans)
    r.add("POST", "/loans", loans.create_loan)
    r.add("GET", "/loans/overdue", loans.overdue)
    r.add("POST", "/loans/{id:int}/return", loans.return_loan)
    return app
