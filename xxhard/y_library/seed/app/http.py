from dataclasses import dataclass, field


@dataclass
class Request:
    method: str
    path: str                      # may contain a query string: "/books?author=Soseki"
    body: object = None            # parsed JSON body (usually a dict) or None
    query: dict = field(default_factory=dict)    # filled by the router
    params: dict = field(default_factory=dict)   # path parameters, filled by the router


@dataclass
class Response:
    status: int
    body: dict


def ok(body):
    return Response(200, body)


def created(body):
    return Response(201, body)


def no_content():
    return Response(204, {})
