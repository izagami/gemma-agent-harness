import re
from urllib.parse import parse_qsl

from app.errors import ApiError, MethodNotAllowed, NotFound
from app.http import Response

# {name} matches one path segment; {name:int} matches digits and converts to int.
_CONVERTERS = {"str": (r"[^/]+", str), "int": (r"\d+", int)}
_PARAM = re.compile(r"\{(\w+)(?::(\w+))?\}")


class Route:
    def __init__(self, method, pattern, handler):
        self.method = method.upper()
        self.pattern = pattern
        self.handler = handler
        self.regex, self.converters = self._compile(pattern)

    @staticmethod
    def _compile(pattern):
        out, pos, converters = "^", 0, {}
        for m in _PARAM.finditer(pattern):
            name, kind = m.group(1), m.group(2) or "str"
            if kind not in _CONVERTERS:
                raise ValueError(f"unknown converter {kind!r} in {pattern!r}")
            rx, conv = _CONVERTERS[kind]
            out += re.escape(pattern[pos:m.start()]) + f"(?P<{name}>{rx})"
            converters[name] = conv
            pos = m.end()
        out += re.escape(pattern[pos:]) + "$"
        return re.compile(out), converters

    def match(self, path):
        m = self.regex.match(path)
        if m is None:
            return None
        return {k: self.converters[k](v) for k, v in m.groupdict().items()}


class Router:
    """Routes are tried in registration order; the first route whose pattern and method match wins."""

    def __init__(self):
        self.routes = []

    def add(self, method, pattern, handler):
        self.routes.append(Route(method, pattern, handler))

    def dispatch(self, ctx, request):
        path, _, qs = request.path.partition("?")
        request.query = dict(parse_qsl(qs))
        path_matched = False
        for route in self.routes:
            params = route.match(path)
            if params is None:
                continue
            path_matched = True
            if route.method != request.method.upper():
                continue
            request.params = params
            try:
                return route.handler(ctx, request)
            except ApiError as e:
                return Response(e.status, e.to_body())
        err = MethodNotAllowed() if path_matched else NotFound()
        return Response(err.status, err.to_body())
