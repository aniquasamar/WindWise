"""A tiny ASGI test harness: call an ASGI app directly, with no web server or framework."""
import asyncio
import json
from dataclasses import dataclass, field


@dataclass
class Result:
    status: int
    headers: dict
    body: bytes
    scope: dict = field(repr=False, default_factory=dict)

    def json(self):
        return json.loads(self.body)


def call(app, method="GET", path="/", headers=None, client=("203.0.113.9", 5000), scheme="http"):
    hdrs = [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in (headers or {}).items()]
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method, "scheme": scheme,
        "path": path, "raw_path": path.encode(), "query_string": b"", "headers": hdrs,
        "client": client, "server": ("testserver", 80),
    }
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    asyncio.run(app(scope, receive, send))
    start = next(m for m in messages if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    return Result(start["status"], {k.decode(): v.decode() for k, v in start["headers"]}, body, scope)


def json_app(body=b'{"hello":"world"}', status=200, content_type=b"application/json", extra=None):
    """A minimal ASGI app that returns a fixed response."""
    async def app(scope, receive, send):
        headers = [(b"content-type", content_type), (b"content-length", str(len(body)).encode())]
        headers += list(extra or [])
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})
    return app


def failing_app(message="secret detail at C:\\private\\file.py"):
    async def app(scope, receive, send):
        raise RuntimeError(message)
    return app


def failing_after_start_app():
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        raise RuntimeError("late failure")
    return app