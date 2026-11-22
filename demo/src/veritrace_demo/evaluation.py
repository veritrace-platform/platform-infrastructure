"""Forecast evaluation run: measures the excursion warnings of the platform end to end.

The run builds a long synthetic journey of chilled milk (2–8 °C) out of episodes whose outcome is known — loads that
warm until they breach, door openings that do not, sudden failures with no build-up, slow drifts, and overcooling —
separated by steady stretches. It replays the journey for a new shipment with past device times, so hours of journey
pass through MQTT, Kafka, the detector, and the forecast in seconds, and then reads what the platform measured: the
forecast quality of the shipment's warnings, its incidents, and its thermal exposure. Nobody acts on a warning in a
simulation, so the precision reported here is exact, not a lower bound.

The journey depends only on the seed, so a run can be repeated, and two runs compared.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import random
import threading
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass

from veritrace_simulator import scenario as scenarios
from veritrace_simulator.cli import play
from veritrace_simulator.fleet import devices_for
from veritrace_simulator.publisher import MqttPublisher

from veritrace_demo import fixtures as f
from veritrace_demo.client import Api
from veritrace_demo.scenario import Failed, Settings, expect, wait_until_visible
from veritrace_demo.seed import commission, seed

log = logging.getLogger("veritrace_demo")

# Bounds of the evaluated goods, and the breach rule of cold-chain-monitoring.md section 4.
T_MIN, T_MAX = 2.0, 8.0
CONFIRM_SECONDS = 30
INTERVAL_SECONDS = 5.0
JITTER_CELSIUS = 0.1
# The journey ends a minute ago and stays well within the 24 hours of past readings that ingestion accepts.
END_BEFORE_SECONDS = 60
MAX_JOURNEY_SECONDS = 20 * 3600
SETTLE_TIMEOUT = 120.0

# How often each kind of episode occurs, and whether it breaches.
KINDS = {
    "build-up": (35, True),
    "door opening": (25, False),
    "sudden failure": (15, True),
    "slow drift": (15, False),
    "overcooling": (10, True),
}


@dataclass(frozen=True)
class Episode:
    """One episode of the journey, in seconds from its start."""

    kind: str
    start_seconds: float
    end_seconds: float
    breach_expected: bool


@dataclass(frozen=True)
class Journey:
    scenario: scenarios.Scenario
    episodes: tuple[Episode, ...]

    @property
    def duration_seconds(self) -> float:
        return self.scenario.duration_seconds


def build(seed_value: int, episodes: int) -> Journey:
    """Build the journey of a seed: a steady start, then episodes, each followed by a steady stretch."""
    rng = random.Random(seed_value)
    phases: list[scenarios.Phase] = []
    elapsed = 0.0

    def add(name: str, minutes: float, start: float, end: float | None = None) -> None:
        nonlocal elapsed
        seconds = round(minutes * 60 / INTERVAL_SECONDS) * INTERVAL_SECONDS
        phases.append(scenarios.Phase(name, seconds, round(start, 2), round(start if end is None else end, 2)))
        elapsed += seconds

    level = rng.uniform(3.8, 5.2)
    add("steady", 15, level)
    weights = [w for w, _ in KINDS.values()]
    result = []
    for n in range(episodes):
        kind = rng.choices(list(KINDS), weights)[0]
        begin = elapsed
        match kind:
            case "build-up":
                peak, slope = rng.uniform(9, 12), rng.uniform(0.25, 1.5)
                add(f"{n}: warming", (peak - level) / slope, level, peak)
                add(f"{n}: breach", rng.uniform(1, 4), peak)
                add(f"{n}: recovering", rng.uniform(2, 5), peak, level)
            case "sudden failure":
                peak = rng.uniform(10, 14)
                add(f"{n}: failure", rng.uniform(1, 3), peak)
                add(f"{n}: recovering", rng.uniform(2, 4), peak, level)
            case "door opening":
                peak, slope = rng.uniform(6.3, 7.6), rng.uniform(0.6, 1.2)
                add(f"{n}: door open", (peak - level) / slope, level, peak)
                add(f"{n}: door closed", (peak - level) / rng.uniform(0.6, 1.2), peak, level)
            case "slow drift":
                top = min(level + rng.uniform(1.0, 2.0), 7.0)
                add(f"{n}: drifting", rng.uniform(10, 20), level, top)
                add(f"{n}: corrected", rng.uniform(5, 10), top, level)
            case "overcooling":
                bottom, slope = rng.uniform(0.5, 1.5), rng.uniform(0.3, 0.8)
                add(f"{n}: overcooling", (level - bottom) / slope, level, bottom)
                add(f"{n}: too cold", rng.uniform(1, 3), bottom)
                add(f"{n}: corrected", rng.uniform(2, 4), bottom, level)
        result.append(Episode(kind, begin, elapsed, KINDS[kind][1]))
        add("steady", rng.uniform(10, 20), level)
    scenario = scenarios.Scenario(
        name=f"evaluation-{seed_value}",
        description=f"Forecast evaluation journey of seed {seed_value} with {episodes} episodes",
        interval_seconds=INTERVAL_SECONDS,
        humidity_percent=65,
        jitter_celsius=JITTER_CELSIUS,
        origin=scenarios.Point(f.ORIGIN.latitude, f.ORIGIN.longitude),
        destination=scenarios.Point(f.DESTINATION.latitude, f.DESTINATION.longitude),
        phases=tuple(phases),
    )
    if scenario.duration_seconds > MAX_JOURNEY_SECONDS:
        raise ValueError(f"{episodes} episodes make a journey longer than {MAX_JOURNEY_SECONDS // 3600} hours")
    return Journey(scenario, tuple(result))


@dataclass
class Outcome:
    """What the platform recorded for one episode."""

    episode: Episode
    incidents: int
    warning: str  # the outcome of the first warning issued in the episode, or "none"
    lead_time_seconds: int | None


def evaluate(settings: Settings, seed_value: int, episodes: int, out: Callable[[str], None] = print) -> dict:
    """Run the evaluation and return its report."""
    journey = build(seed_value, episodes)
    api = Api(settings.api_url)
    try:
        return _run(api, settings, journey, seed_value, out)
    finally:
        api.close()


def _run(api: Api, s: Settings, journey: Journey, seed_value: int, out: Callable[[str], None]) -> dict:
    seeded = seed(api, s.password)
    manager = api.login(f.account_with_role(f.OWNER, "WAREHOUSE_MANAGER").email, s.password)
    admin = api.login(f.account_with_role(f.OWNER, "ADMIN").email, s.password)
    now = dt.datetime.now(dt.UTC)
    lot = commission(
        api,
        manager,
        seeded.products[f.PRODUCT.gtin]["id"],
        seeded.locations[f.ORIGIN.gln]["id"],
        "EVAL-" + now.strftime("%y%m%d-%H%M%S"),
        10,
        now.date() - dt.timedelta(days=1),
        14,
    )
    shipment = api.post(
        "/api/v1/shipments",
        manager,
        {
            "lot_id": lot["id"],
            "quantity": 10,
            "origin_location_id": seeded.locations[f.ORIGIN.gln]["id"],
            "destination_gln": f.DESTINATION.gln,
            "carrier_tenant_code": f.CARRIER.code,
        },
    )
    sscc = shipment["sscc"]
    wait_until_visible(api, admin, sscc, "owner")
    hours = journey.duration_seconds / 3600
    out(f"Shipment {sscc} (lot {lot['lot_number']}): replaying {hours:.1f} h of journey with past device times …")

    backdate = journey.duration_seconds + END_BEFORE_SECONDS
    started = time.time() - backdate
    publisher = MqttPublisher(s.mqtt_url, s.mqtt_username, s.mqtt_password)
    try:
        devices = devices_for([sscc], 1, INTERVAL_SECONDS, seed=seed_value)
        play(journey.scenario, devices, publisher, threading.Event(), backdate_seconds=backdate)
    finally:
        publisher.close()
    last_reading = started + journey.duration_seconds - INTERVAL_SECONDS
    _settle(api, admin, sscc, last_reading)

    # Cancelling ends monitoring: an open warning is closed as INCONCLUSIVE and the exposure ends there.
    api.post(f"/api/v1/shipments/{shipment['id']}/cancel", manager, {"reason": "Forecast evaluation finished"})
    exposure = _end_of_monitoring(api, admin, sscc)
    performance = api.get("/api/v1/telemetry/warnings/performance", admin, sscc=sscc)
    warnings = list(api.items(f"/api/v1/telemetry/shipments/{sscc}/warnings", admin))
    incidents = list(api.items(f"/api/v1/telemetry/shipments/{sscc}/incidents", admin))
    outcomes = match(journey, started, warnings, incidents)

    report = {
        "seed": seed_value,
        "sscc": sscc,
        "journey_hours": round(hours, 2),
        "readings": int(journey.duration_seconds / INTERVAL_SECONDS),
        "episodes": [asdict(o) for o in outcomes],
        "performance": performance,
        "thermal_exposure": exposure,
    }
    for line in summary(journey, outcomes, performance, exposure, seed_value):
        out(line)
    missed = [o for o in outcomes if (o.incidents > 0) != o.episode.breach_expected]
    expect(not missed, f"episodes whose breaches differ from the journey: {missed}")
    return report


def _settle(api: Api, token: str, sscc: str, last_reading: float) -> None:
    """Wait until the platform has stored the journey's last reading and its forecast quality stops changing."""
    deadline = time.monotonic() + SETTLE_TIMEOUT
    since = dt.datetime.fromtimestamp(last_reading - 60, dt.UTC).isoformat().replace("+00:00", "Z")
    previous = None
    while time.monotonic() < deadline:
        time.sleep(2)
        readings = api.get(f"/api/v1/telemetry/shipments/{sscc}/readings", token, **{"from": since})["items"]
        stored = any(_epoch(r["recorded_at"]) >= last_reading - 1 for r in readings)
        p = api.get("/api/v1/telemetry/warnings/performance", token, sscc=sscc)
        # The window moves with every call; the counts tell whether processing goes on.
        current = (p["warnings"], p["incidents"])
        if stored and current == previous:
            return
        previous = current
    raise Failed("the platform did not settle on the journey within two minutes")


def _epoch(timestamp: str) -> float:
    return dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()


def _end_of_monitoring(api: Api, token: str, sscc: str) -> dict:
    deadline = time.monotonic() + SETTLE_TIMEOUT
    while time.monotonic() < deadline:
        exposure = api.get(f"/api/v1/telemetry/shipments/{sscc}/thermal-exposure", token)
        if exposure["monitoring_ended"]:
            return exposure
        time.sleep(0.5)
    raise Failed(f"the telemetry service still monitors {sscc} after its cancellation")


def match(journey: Journey, started: float, warnings: list[dict], incidents: list[dict]) -> list[Outcome]:
    """Match the platform's incidents and warnings to the episodes they fall in."""

    def offset(timestamp: str) -> float:
        return _epoch(timestamp) - started

    outcomes = []
    for e in journey.episodes:
        inside = [w for w in warnings if e.start_seconds <= offset(w["issued_at"]) < e.end_seconds]
        inside.sort(key=lambda w: w["issued_at"])
        first = inside[0] if inside else None
        outcomes.append(
            Outcome(
                episode=e,
                incidents=sum(1 for i in incidents if e.start_seconds <= offset(i["started_at"]) < e.end_seconds),
                warning=(first["outcome"] or "OPEN") if first else "none",
                lead_time_seconds=first["lead_time_seconds"] if first else None,
            )
        )
    return outcomes


def summary(journey: Journey, outcomes: list[Outcome], p: dict, exposure: dict, seed_value: int) -> list[str]:
    """Describe the run for a terminal."""
    kinds = Counter(e.kind for e in journey.episodes)
    expected = sum(1 for e in journey.episodes if e.breach_expected)
    w, lead = p["warnings"], p["lead_time_seconds"]

    def pct(v: float | None) -> str:
        return "n/a" if v is None else f"{v:.1%}"

    lines = [
        "",
        f"Forecast evaluation — seed {seed_value}, {len(journey.episodes)} episodes, "
        f"{journey.duration_seconds / 3600:.1f} h of device time",
        "  Episodes:  " + ", ".join(f"{n} {k}" for k, n in kinds.most_common()),
        f"  Breaches:  {expected} episodes; {p['incidents']['count']} incidents recorded, "
        f"{p['incidents']['warned']} of them warned",
        f"  Warnings:  {w['issued']} issued: {w['breached']} breached, {w['cleared']} cleared, "
        f"{w['inconclusive']} inconclusive",
        f"  Precision: {pct(p['precision'])}    Recall: {pct(p['recall'])}",
    ]
    if lead:
        lines.append(
            f"  Lead time: median {lead['median']:.0f} s, minimum {lead['min']:.0f} s, mean {lead['mean']:.0f} s; "
            f"excursion time error {p['mean_excursion_time_error_seconds']:.0f} s on average"
        )
    lines += ["", f"  {'#':>3}  {'episode':16} {'start':>8}  {'breach':6}  {'incidents':9}  {'warning':12}  lead"]
    for n, o in enumerate(outcomes):
        e = o.episode
        start = f"{int(e.start_seconds // 3600)}:{int(e.start_seconds % 3600 // 60):02d}"
        lead_time = "" if o.lead_time_seconds is None else f"{o.lead_time_seconds} s"
        lines.append(
            f"  {n:>3}  {e.kind:16} {start:>8}  {'yes' if e.breach_expected else 'no':6}  {o.incidents:<9}  "
            f"{o.warning:12}  {lead_time}"
        )
    shelf = exposure.get("shelf_life") or {}
    lines += [
        "",
        f"  Thermal exposure: MKT {exposure['mean_kinetic_temperature_celsius']} °C, "
        f"{exposure['time_above_max_seconds'] // 60} min above and {exposure['time_below_min_seconds'] // 60} min "
        f"below the bounds; shelf life {shelf.get('status')}, {shelf.get('shelf_life_loss_hours')} h lost, "
        f"estimated expiration {shelf.get('estimated_expiration_date')}",
    ]
    return lines


def write_report(report: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
