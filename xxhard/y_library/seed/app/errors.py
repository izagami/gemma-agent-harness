"""API errors. Raise them from handlers; the router turns them into responses."""


class ApiError(Exception):
    status = 500
    code = "internal"

    def __init__(self, detail=None):
        super().__init__(detail)
        self.detail = detail

    def to_body(self):
        body = {"error": self.code}
        if self.detail is not None:
            body["detail"] = self.detail
        return body


class BadRequest(ApiError):
    status = 400
    code = "bad_request"


class NotFound(ApiError):
    status = 404
    code = "not_found"


class MethodNotAllowed(ApiError):
    status = 405
    code = "method_not_allowed"


class Conflict(ApiError):
    status = 409
    code = "conflict"


class ValidationError(ApiError):
    status = 400
    code = "validation"

    def __init__(self, fields):
        super().__init__(None)
        self.fields = dict(fields)

    def to_body(self):
        return {"error": self.code, "fields": dict(sorted(self.fields.items()))}
