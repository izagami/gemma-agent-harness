# Library API

`create_app(storage=None, today=date.today)` returns an `App`; call
`app.handle(method, path, body=None)` to get a `Response(status, body)`.
`app.today()` is the current date (inject a fixed one in tests).

## Errors

| status | body |
|---|---|
| 400 | `{"error": "validation", "fields": {field: message, ...}}` |
| 404 | `{"error": "not_found"}` (unknown path) or `{"error": "not_found", "detail": "..."}` |
| 405 | `{"error": "method_not_allowed"}` (path exists, method does not) |
| 409 | `{"error": "conflict", "detail": "..."}` |

Validation messages: `required`, `unknown field`, `must not be null`, `must be an integer`,
`must be a string`, `must not be empty`, `must be at most N characters`, `must be >= N`,
`must be <= N`; a body that is not a JSON object gives `{"_body": "must be an object"}`.

## Books

- `POST /books` `{"title": str, "author": str, "year": int|null (optional, 0..2100)}` → 201 book
- `GET /books[?author=...]` → 200 `{"books": [...]}` (id order)
- `GET /books/{id}` → 200 book / 404 `book not found`
- `PATCH /books/{id}` (any subset of the fields) → 200 book
- `DELETE /books/{id}` → 204 `{}`

## Members

- `POST /members` `{"name": str, "email": str}` → 201 member. Email is stored trimmed and
  lower-cased; 400 `{"email": "invalid email"}`; 409 `email already registered`.
- `GET /members` → 200 `{"members": [...]}`
- `GET /members/{id}` → 200 member / 404 `member not found`
