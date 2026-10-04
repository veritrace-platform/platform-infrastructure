"""Scenarios: what a reefer's sensors report over time, as a sequence of phases.

A scenario file is YAML:

    name: sustained-breach
    description: The reefer fails for 90 s, so the detector confirms a breach and later resolves it.
    interval_seconds: 5          # one reading per device per interval
    humidity_percent: 62         # omit or null for devices without a humidity sensor
    jitter_celsius: 0.1          # standard deviation of the noise added to each temperature
    route:                       # positions move from one point to the other over the scenario
      from: {lat: 10.7627, lng: 106.7429}
      to: {lat: 10.7296, lng: 106.7188}
    phases:
      - name: pre-cooled
        duration_seconds: 60
        temperature: 4.5         # constant, or {start: 9.5, end: 11.0} for a linear change
      - name: sensor offline
        duration_seconds: 20
        silent: true             # no readings during the phase
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any

import yaml

# Default route: a cold store and a store hub in Ho Chi Minh City.
DEFAULT_FROM = (10.7627, 106.7429)
DEFAULT_TO = (10.7296, 106.7188)


class ScenarioError(ValueError):
    """A scenario file that cannot be replayed."""


@dataclass(frozen=True)
class Point:
    lat: float
    lng: float


@dataclass(frozen=True)
class Phase:
    name: str
    duration_seconds: float
    temperature_start: float
    temperature_end: float
    silent: bool = False

    def temperature_at(self, elapsed: float) -> float:
        """Return the temperature elapsed seconds into the phase, before noise."""
        fraction = min(max(elapsed / self.duration_seconds, 0.0), 1.0)
        return self.temperature_start + (self.temperature_end - self.temperature_start) * fraction


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    interval_seconds: float
    humidity_percent: float | None
    jitter_celsius: float
    origin: Point
    destination: Point
    phases: tuple[Phase, ...]

    @property
    def duration_seconds(self) -> float:
        return sum(p.duration_seconds for p in self.phases)


def _bundled_dir() -> Traversable:
    return resources.files("veritrace_simulator") / "scenarios"


def bundled() -> list[str]:
    """Return the names of the scenarios that ship with the simulator."""
    return sorted(Path(entry.name).stem for entry in _bundled_dir().iterdir() if entry.name.endswith(".yaml"))


def load(name_or_path: str) -> Scenario:
    """Load a bundled scenario by name, or a scenario file by path."""
    if name_or_path in bundled():
        text = _bundled_dir().joinpath(f"{name_or_path}.yaml").read_text(encoding="utf-8")
    else:
        path = Path(name_or_path)
        if not path.is_file():
            raise ScenarioError(f"{name_or_path!r} is neither a bundled scenario ({', '.join(bundled())}) nor a file")
        text = path.read_text(encoding="utf-8")
    return parse(text)


def parse(text: str) -> Scenario:
    """Parse and validate a scenario document."""
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as err:
        raise ScenarioError(f"invalid YAML: {err}") from err
    if not isinstance(doc, dict):
        raise ScenarioError("a scenario is a mapping")
    _only(
        doc,
        "scenario",
        {"name", "description", "interval_seconds", "humidity_percent", "jitter_celsius", "route", "phases"},
    )

    name = _require(doc, "name", str, "scenario")
    interval = _positive(_require(doc, "interval_seconds", (int, float), "scenario"), "interval_seconds")
    humidity = doc.get("humidity_percent")
    if humidity is not None and (not _number(humidity) or not 0 <= humidity <= 100):
        raise ScenarioError("humidity_percent must be a number from 0 to 100, or null")
    jitter = doc.get("jitter_celsius", 0.1)
    if not _number(jitter) or jitter < 0:
        raise ScenarioError("jitter_celsius must be a number of at least 0")

    origin, destination = Point(*DEFAULT_FROM), Point(*DEFAULT_TO)
    if "route" in doc:
        route = doc["route"]
        if not isinstance(route, dict):
            raise ScenarioError("route must be a mapping with from and to")
        _only(route, "route", {"from", "to"})
        origin = _point(_require(route, "from", dict, "route"), "route.from")
        destination = _point(_require(route, "to", dict, "route"), "route.to")

    raw_phases = _require(doc, "phases", list, "scenario")
    if not raw_phases:
        raise ScenarioError("phases must not be empty")
    phases = tuple(_phase(p, i) for i, p in enumerate(raw_phases))
    return Scenario(
        name=name,
        description=doc.get("description", ""),
        interval_seconds=float(interval),
        humidity_percent=None if humidity is None else float(humidity),
        jitter_celsius=float(jitter),
        origin=origin,
        destination=destination,
        phases=phases,
    )


def _phase(raw: Any, index: int) -> Phase:
    where = f"phases[{index}]"
    if not isinstance(raw, dict):
        raise ScenarioError(f"{where} must be a mapping")
    _only(raw, where, {"name", "duration_seconds", "temperature", "silent"})
    name = raw.get("name", f"phase {index + 1}")
    duration = _positive(_require(raw, "duration_seconds", (int, float), where), f"{where}.duration_seconds")
    silent = raw.get("silent", False)
    if not isinstance(silent, bool):
        raise ScenarioError(f"{where}.silent must be true or false")
    temperature = raw.get("temperature")
    if temperature is None and silent:
        start = end = 0.0
    elif _number(temperature):
        start = end = float(temperature)
    elif isinstance(temperature, dict):
        _only(temperature, f"{where}.temperature", {"start", "end"})
        start = _require(temperature, "start", (int, float), f"{where}.temperature")
        end = _require(temperature, "end", (int, float), f"{where}.temperature")
    else:
        raise ScenarioError(f"{where}.temperature must be a number or a mapping with start and end")
    for value in (start, end):
        if not -50 <= value <= 80:
            raise ScenarioError(f"{where}.temperature must stay within -50…80 °C, the range devices may report")
    return Phase(str(name), float(duration), float(start), float(end), silent)


def _point(raw: dict, where: str) -> Point:
    _only(raw, where, {"lat", "lng"})
    lat = _require(raw, "lat", (int, float), where)
    lng = _require(raw, "lng", (int, float), where)
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ScenarioError(f"{where} is not a WGS-84 coordinate")
    return Point(float(lat), float(lng))


def _number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _require(doc: dict, key: str, kind: type | tuple[type, ...], where: str) -> Any:
    if key not in doc:
        raise ScenarioError(f"{where} lacks {key}")
    value = doc[key]
    if not isinstance(value, kind) or isinstance(value, bool):
        raise ScenarioError(f"{where}.{key} has the wrong type")
    return value


def _positive(value: float, where: str) -> float:
    if value <= 0:
        raise ScenarioError(f"{where} must be positive")
    return value


def _only(doc: dict, where: str, allowed: set[str]) -> None:
    unknown = set(doc) - allowed
    if unknown:
        raise ScenarioError(f"{where} has unknown keys: {', '.join(sorted(map(str, unknown)))}")
