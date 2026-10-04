"""Publishers: an MQTT client that publishes as the devices, and a printer for dry runs."""

from __future__ import annotations

import json
import sys
import threading
import uuid
from typing import Any, Protocol, TextIO
from urllib.parse import urlsplit

import paho.mqtt.client as mqtt

DEFAULT_PORT = 1883
TIMEOUT_SECONDS = 10.0


class PublishError(RuntimeError):
    """The broker refused the connection or did not acknowledge a reading."""


class Publisher(Protocol):
    def publish(self, topic: str, payload: dict) -> None: ...

    def close(self) -> None: ...


def encode(payload: dict) -> str:
    """Encode a payload as compact JSON, as constrained devices send it."""
    return json.dumps(payload, separators=(",", ":"))


def parse_broker_url(url: str) -> tuple[str, int]:
    """Return the host and port of an mqtt:// URL."""
    parts = urlsplit(url)
    if parts.scheme != "mqtt" or not parts.hostname:
        raise ValueError(f"MQTT_URL must look like mqtt://host:1883, got {url!r}")
    return parts.hostname, parts.port or DEFAULT_PORT


class MqttPublisher:
    """Publishes readings with QoS 1 and waits for each acknowledgement. The connection uses MQTT 3.1.1, which
    the broker accepts from constrained devices."""

    def __init__(self, url: str, username: str, password: str) -> None:
        host, port = parse_broker_url(url)
        self._connected = threading.Event()
        self._reason: Any = None
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"veritrace-simulator-{uuid.uuid4().hex[:12]}",
            protocol=mqtt.MQTTv311,
        )
        self._client.username_pw_set(username, password)
        self._client.on_connect = self._on_connect
        try:
            self._client.connect(host, port, keepalive=30)
        except OSError as err:
            raise PublishError(f"cannot reach the MQTT broker at {host}:{port}: {err}") from err
        self._client.loop_start()
        if not self._connected.wait(TIMEOUT_SECONDS):
            self.close()
            raise PublishError("the MQTT broker did not answer the connection")
        if self._reason is not None and self._reason.is_failure:
            self.close()
            raise PublishError(f"the MQTT broker refused the connection: {self._reason}")

    def _on_connect(self, _client: mqtt.Client, _userdata: Any, _flags: Any, reason: Any, _props: Any) -> None:
        self._reason = reason
        self._connected.set()

    def publish(self, topic: str, payload: dict) -> None:
        info = self._client.publish(topic, encode(payload), qos=1)
        info.wait_for_publish(TIMEOUT_SECONDS)
        if not info.is_published():
            raise PublishError(f"the MQTT broker did not acknowledge a reading on {topic}")

    def close(self) -> None:
        self._client.disconnect()
        self._client.loop_stop()


class PrintPublisher:
    """Writes each reading as a line of JSON instead of publishing it."""

    def __init__(self, out: TextIO | None = None) -> None:
        self._out = out or sys.stdout

    def publish(self, topic: str, payload: dict) -> None:
        self._out.write(f"{topic} {encode(payload)}\n")

    def close(self) -> None:
        self._out.flush()
