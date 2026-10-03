"""A notification WebSocket client (docs/contracts/messaging.md §6) that collects messages in the background."""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable
from urllib.parse import urlsplit, urlunsplit

from websockets.exceptions import ConnectionClosed
from websockets.sync.client import ClientConnection, connect

log = logging.getLogger("veritrace_demo")

SUBPROTOCOL = "veritrace.v1"


def websocket_url(api_url: str) -> str:
    """Return the notification endpoint behind the gateway at api_url."""
    parts = urlsplit(api_url)
    scheme = {"http": "ws", "https": "wss"}.get(parts.scheme, parts.scheme)
    return urlunsplit((scheme, parts.netloc, "/ws/v1/notifications", "", ""))


class Listener:
    """Connects with an access token, subscribes to the telemetry of some SSCCs, and records every message.

    Messages are kept in arrival order; wait_for blocks until one matches."""

    def __init__(
        self, url: str, token: str, name: str, *, on_message: Callable[[str, dict], None] | None = None
    ) -> None:
        self.name = name
        self.messages: list[dict] = []
        self.close_code: int | None = None
        self._changed = threading.Condition()
        self._on_message = on_message
        self._ws: ClientConnection = connect(url, subprotocols=[SUBPROTOCOL, f"bearer.{token}"], open_timeout=10)
        if self._ws.subprotocol != SUBPROTOCOL:
            raise RuntimeError(f"the server selected the subprotocol {self._ws.subprotocol!r}")
        self._thread = threading.Thread(target=self._read, name=f"listener-{name}", daemon=True)
        self._thread.start()

    def _read(self) -> None:
        try:
            for raw in self._ws:
                message = json.loads(raw)
                with self._changed:
                    self.messages.append(message)
                    self._changed.notify_all()
                if self._on_message:
                    self._on_message(self.name, message)
        except ConnectionClosed as closed:
            with self._changed:
                self.close_code = closed.rcvd.code if closed.rcvd else None
                self._changed.notify_all()

    def subscribe(self, sscc: str, timeout: float = 10) -> dict:
        """Subscribe to the telemetry of an SSCC and return the server's answer."""
        self._ws.send(json.dumps({"type": "subscribe", "channel": "telemetry", "sscc": sscc}))
        answer = self.wait_for(lambda m: m["type"] in ("subscribed", "error") and _about(m, sscc), timeout)
        if answer is None:
            raise TimeoutError(f"{self.name}: no answer to the subscription to {sscc}")
        return answer

    def wait_for(self, matches: Callable[[dict], bool], timeout: float) -> dict | None:
        """Return the first message that matches, waiting up to timeout seconds for it."""
        deadline = time.monotonic() + timeout
        with self._changed:
            while True:
                for m in self.messages:
                    if matches(m):
                        return m
                remaining = deadline - time.monotonic()
                if remaining <= 0 or self.close_code is not None:
                    return None
                self._changed.wait(remaining)

    def count(self, message_type: str) -> int:
        with self._changed:
            return sum(1 for m in self.messages if m["type"] == message_type)

    def close(self) -> None:
        self._ws.close()
        self._thread.join(timeout=5)


def _about(message: dict, sscc: str) -> bool:
    data = message.get("data") or {}
    return data.get("sscc") == sscc or message["type"] == "error"
