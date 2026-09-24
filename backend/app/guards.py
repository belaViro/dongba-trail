"""Bound request bodies and expensive calls before multipart parsing."""

import hashlib
import json
import time
from collections import OrderedDict, deque
from uuid import uuid4

from starlette.types import ASGIApp, Receive, Scope, Send

from backend.app.config import Settings


class RequestGuards:
    def __init__(self, app: ASGIApp, settings: Settings):
        self.app = app
        self.settings = settings
        self.windows: OrderedDict[str, deque[float]] = OrderedDict()

    def allowed(self, key: str, limit: int) -> bool:
        instant = time.monotonic()
        window = self.windows.setdefault(key, deque())
        self.windows.move_to_end(key)
        while window and window[0] <= instant - 60:
            window.popleft()
        while len(self.windows) > 10000:
            self.windows.popitem(last=False)
        if len(window) >= limit:
            return False
        window.append(instant)
        return True

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id

        async def reject(status: int, code: str, message: str):
            body = json.dumps({"request_id": request_id, "code": code, "message": message}).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": status,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"x-request-id", request_id.encode()),
                        (b"cache-control", b"no-store"),
                        (b"x-content-type-options", b"nosniff"),
                        *([(b"retry-after", b"60")] if status == 429 else []),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})

        headers = dict(scope["headers"])
        client = scope.get("client") or ("unknown", 0)
        path = scope["path"]
        if path.startswith("/api/"):
            if not self.allowed(f"ip:{client[0]}", self.settings.request_limit_per_minute):
                await reject(429, "RATE_LIMITED", "Too many requests; retry in one minute")
                return
            if path == "/api/v1/recognize":
                identity = hashlib.sha256(
                    headers.get(b"authorization", client[0].encode())
                ).hexdigest()
                if not self.allowed(
                    f"recognize:{identity}", self.settings.recognition_limit_per_minute
                ):
                    await reject(429, "RATE_LIMITED", "Recognition request limit reached")
                    return

        limit = self.settings.max_image_bytes + 65536
        try:
            content_length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            await reject(400, "INVALID_REQUEST", "Invalid content length")
            return
        if content_length < 0 or content_length > limit:
            await reject(413, "REQUEST_TOO_LARGE", "Request exceeds the upload limit")
            return
        chunks = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            data = message.get("body", b"")
            total += len(data)
            if total > limit:
                await reject(413, "REQUEST_TOO_LARGE", "Request exceeds the upload limit")
                return
            chunks.append(data)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        async def guarded_send(message):
            if message["type"] == "http.response.start":
                response_headers = list(message.get("headers", []))
                response_headers = [
                    (key, val) for key, val in response_headers if key.lower() != b"x-request-id"
                ]
                response_headers.extend(
                    [
                        (b"x-request-id", request_id.encode()),
                        (b"x-content-type-options", b"nosniff"),
                        (b"referrer-policy", b"same-origin"),
                    ]
                )
                message = {**message, "headers": response_headers}
            await send(message)

        await self.app(scope, replay, guarded_send)
