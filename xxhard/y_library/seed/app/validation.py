"""Declarative validation of JSON bodies.

validate(body, schema) returns a cleaned dict or raises ValidationError whose
`fields` maps each bad field to a message (see docs/API.md for the messages).
"""
from app.errors import ValidationError


class Field:
    def __init__(self, type, required=True, default=None, min=None, max=None, max_len=None, nullable=False):
        self.type = type
        self.required = required
        self.default = default
        self.min = min
        self.max = max
        self.max_len = max_len
        self.nullable = nullable

    def check(self, value):
        """Return an error message for value, or None if it is acceptable."""
        if value is None:
            return None if self.nullable else "must not be null"
        if self.type is int:
            if isinstance(value, bool) or not isinstance(value, int):
                return "must be an integer"
        elif self.type is str:
            if not isinstance(value, str):
                return "must be a string"
            if not value.strip():
                return "must not be empty"
            if self.max_len is not None and len(value) > self.max_len:
                return f"must be at most {self.max_len} characters"
        if self.min is not None and value < self.min:
            return f"must be >= {self.min}"
        if self.max is not None and value > self.max:
            return f"must be <= {self.max}"
        return None


def validate(body, schema, partial=False):
    """partial=True (for updates): missing fields are simply left out of the result."""
    if not isinstance(body, dict):
        raise ValidationError({"_body": "must be an object"})
    errors, out = {}, {}
    for name in body:
        if name not in schema:
            errors[name] = "unknown field"
    for name, f in schema.items():
        if name not in body:
            if partial:
                continue
            if f.required:
                errors[name] = "required"
            else:
                out[name] = f.default
            continue
        msg = f.check(body[name])
        if msg:
            errors[name] = msg
        else:
            out[name] = body[name]
    if errors:
        raise ValidationError(errors)
    return out
