"""The fleet: devices attached to shipments, and the readings they report as a scenario plays."""

from __future__ import annotations

import random
from collections.abc import Iterator
from dataclasses import dataclass, field

from veritrace_simulator.gs1 import valid_sscc
from veritrace_simulator.scenario import Phase, Scenario

TOPIC = "veritrace/v1/devices/{device_id}/telemetry"


@dataclass
class Device:
    """A data logger attached to the logistic unit with the SSCC."""

    device_id: str
    sscc: str
    # How long before each tick the device takes its reading, so that devices on one SSCC do not share timestamps.
    lead_ms: int
    rng: random.Random = field(repr=False)

    @property
    def topic(self) -> str:
        return TOPIC.format(device_id=self.device_id)


def devices_for(ssccs: list[str], per_shipment: int, interval_seconds: float, seed: int | None) -> list[Device]:
    """Create per_shipment devices for each SSCC. A seed makes the noise of every device reproducible."""
    if per_shipment < 1:
        raise ValueError("each shipment needs at least one device")
    devices = []
    for sscc in ssccs:
        if not valid_sscc(sscc):
            raise ValueError(f"{sscc!r} is not a valid SSCC-18")
        for n in range(per_shipment):
            device_id = f"SIM-{sscc}-{n + 1}"
            rng = random.Random(f"{seed}-{device_id}") if seed is not None else random.Random()
            lead_ms = int(n * interval_seconds * 1000 / per_shipment)
            devices.append(Device(device_id=device_id, sscc=sscc, lead_ms=lead_ms, rng=rng))
    return devices


@dataclass(frozen=True)
class Message:
    device: Device
    payload: dict


@dataclass(frozen=True)
class Tick:
    """The readings due elapsed_seconds after the scenario started."""

    elapsed_seconds: float
    phase: str
    messages: tuple[Message, ...]


def timeline(scenario: Scenario, devices: list[Device], start_ms: int) -> Iterator[Tick]:
    """Yield the scenario's ticks, one per interval. A silent phase yields ticks without messages."""
    duration = scenario.duration_seconds
    ticks = int(duration // scenario.interval_seconds)
    for k in range(ticks):
        elapsed = k * scenario.interval_seconds
        phase, phase_elapsed = _phase_at(scenario, elapsed)
        if phase.silent:
            yield Tick(elapsed, phase.name, ())
            continue
        progress = elapsed / duration
        lat = scenario.origin.lat + (scenario.destination.lat - scenario.origin.lat) * progress
        lng = scenario.origin.lng + (scenario.destination.lng - scenario.origin.lng) * progress
        messages = []
        for device in devices:
            temperature = phase.temperature_at(phase_elapsed) + device.rng.gauss(0, scenario.jitter_celsius)
            payload = {
                "sscc": device.sscc,
                "ts": start_ms + int(elapsed * 1000) - device.lead_ms,
                "temperature_c": round(min(max(temperature, -50.0), 80.0), 2),
            }
            if scenario.humidity_percent is not None:
                humidity = scenario.humidity_percent + device.rng.gauss(0, 1.0)
                payload["humidity_pct"] = round(min(max(humidity, 0.0), 100.0), 1)
            payload["lat"] = round(lat, 6)
            payload["lng"] = round(lng, 6)
            messages.append(Message(device, payload))
        yield Tick(elapsed, phase.name, tuple(messages))


def _phase_at(scenario: Scenario, elapsed: float) -> tuple[Phase, float]:
    """Return the phase that covers elapsed seconds, and the seconds since it began."""
    begin = 0.0
    for phase in scenario.phases:
        if elapsed < begin + phase.duration_seconds:
            return phase, elapsed - begin
        begin += phase.duration_seconds
    last = scenario.phases[-1]
    return last, last.duration_seconds
