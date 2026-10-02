"""The M1 acceptance scenario: one shipment of chilled milk from the cold store of Saigon Fresh Foods to the store hub
of District 7 Fresh Mart, carried by Mekong Cold Chain Logistics, through every step of the custody handover and a
cold-chain breach, and finally recalled. Each step checks what the platform answers, including the rules it must
enforce; the first unexpected answer stops the run.

Every run commissions a lot and creates a shipment of its own, so the scenario can run again on a seeded stack.
"""

from __future__ import annotations

import datetime as dt
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from veritrace_simulator import scenario as scenarios
from veritrace_simulator.cli import play
from veritrace_simulator.fleet import devices_for
from veritrace_simulator.gs1 import valid_sscc
from veritrace_simulator.publisher import MqttPublisher

from veritrace_demo import fixtures as f
from veritrace_demo.client import Api, ApiError
from veritrace_demo.notifications import Listener, websocket_url
from veritrace_demo.seed import commission, seed

log = logging.getLogger("veritrace_demo")

# A compressed sustained breach for 2–8 °C goods: readings leave the bounds for 40 s, so the breach is confirmed
# 30 s after the first of them and resolved at the first reading back in bounds.
BREACH = scenarios.parse(
    """
name: acceptance-breach
description: The reefer fails for 40 s and recovers.
interval_seconds: 5
humidity_percent: 64
jitter_celsius: 0.05
phases:
  - name: in range
    duration_seconds: 10
    temperature: 4.5
  - name: compressor failure
    duration_seconds: 40
    temperature: {start: 9.5, end: 11}
  - name: recovered
    duration_seconds: 15
    temperature: 5
"""
)

SHIPPED_QUANTITY = 480
ACCURACY_METERS = 8.0
VISIBILITY_TIMEOUT = 20.0
NOTIFICATION_TIMEOUT = 30.0


@dataclass(frozen=True)
class Settings:
    api_url: str
    password: str
    mqtt_url: str
    mqtt_username: str
    mqtt_password: str


class Failed(Exception):
    """The platform did not answer as the scenario expects."""


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise Failed(message)


def expect_problem(call: Callable[[], Any], status: int, code: str) -> ApiError:
    """Run a call that the platform must refuse with the given status and problem code."""
    try:
        call()
    except ApiError as err:
        expect(err.status == status and err.code == code, f"expected {status} {code}, got {err}")
        return err
    raise Failed(f"expected {status} {code}, but the request succeeded")


def position(place: f.Place, north_meters: float = 0) -> dict:
    """A position at the place, or the given distance north of it."""
    return {
        "latitude": round(place.latitude + north_meters / 111_320, 6),
        "longitude": place.longitude,
        "accuracy_meters": ACCURACY_METERS,
    }


class Steps:
    """Prints each passed check, numbered."""

    def __init__(self, out: Callable[[str], None]) -> None:
        self.out = out
        self.passed = 0

    def ok(self, message: str) -> None:
        self.passed += 1
        self.out(f"  ✓ {message}")

    def section(self, title: str) -> None:
        self.out(f"\n{title}")


def run(settings: Settings, out: Callable[[str], None] = print) -> int:
    """Run the scenario and return the exit code: 0 when every check passes."""
    api = Api(settings.api_url)
    listeners: list[Listener] = []
    steps = Steps(out)
    try:
        acceptance(api, settings, steps, listeners)
    except (Failed, ApiError, TimeoutError, OSError) as err:
        trace = f" (trace_id {err.trace_id})" if isinstance(err, ApiError) and err.trace_id else ""
        out(f"  ✗ {err}{trace}")
        out(f"\nThe acceptance run failed after {steps.passed} checks.")
        return 1
    finally:
        for listener in listeners:
            listener.close()
        api.close()
    out(f"\nThe M1 acceptance run passed: {steps.passed} checks.")
    return 0


def acceptance(api: Api, s: Settings, steps: Steps, listeners: list[Listener]) -> None:
    steps.section("Platform and seed data")
    jwks = api.get("/.well-known/jwks.json")
    expect(bool(jwks.get("keys")), "core publishes no token verification key")
    steps.ok("core answers through the gateway and publishes its token keys")
    seeded = seed(api, s.password)
    steps.ok(f"seed is in place ({seeded.summary()})")

    def token(company: f.Company, role: str) -> str:
        return api.login(f.account_with_role(company, role).email, s.password)

    owner_admin, owner_manager = token(f.OWNER, "ADMIN"), token(f.OWNER, "WAREHOUSE_MANAGER")
    carrier_manager, driver = token(f.CARRIER, "WAREHOUSE_MANAGER"), token(f.CARRIER, "DRIVER")
    receiver, outsider = token(f.CONSIGNEE, "WAREHOUSE_MANAGER"), token(f.OUTSIDER, "ADMIN")
    steps.ok("every role signs in: owner admin and warehouse manager, carrier dispatcher and driver, dock receiver")

    steps.section("Lot and shipment")
    now = dt.datetime.now()
    lot = commission(
        api,
        owner_manager,
        seeded.products[f.PRODUCT.gtin]["id"],
        seeded.locations[f.ORIGIN.gln]["id"],
        "DEMO-" + now.strftime("%y%m%d-%H%M%S"),
        SHIPPED_QUANTITY,
        now.date(),
        14,
    )
    expect(lot["status"] == "ACTIVE", f"lot status {lot['status']}")
    steps.ok(f"lot {lot['lot_number']} commissioned: {SHIPPED_QUANTITY} x {f.PRODUCT.name} at {f.ORIGIN.name}")

    shipment = api.post(
        "/api/v1/shipments",
        owner_manager,
        {
            "lot_id": lot["id"],
            "quantity": SHIPPED_QUANTITY,
            "origin_location_id": seeded.locations[f.ORIGIN.gln]["id"],
            "destination_gln": f.DESTINATION.gln,
            "carrier_tenant_code": f.CARRIER.code,
        },
    )
    shipment_id, sscc = shipment["id"], shipment["sscc"]
    roles = sorted(f"{p['role']}:{p['tenant_code']}" for p in shipment["participants"])
    expect(shipment["status"] == "CREATED", f"shipment status {shipment['status']}")
    expect(valid_sscc(sscc) and sscc[1:].startswith(f.OWNER.gs1_company_prefix), f"SSCC {sscc} is not the owner's")
    expect(
        roles == sorted([f"OWNER:{f.OWNER.code}", f"CARRIER:{f.CARRIER.code}", f"CONSIGNEE:{f.CONSIGNEE.code}"]),
        f"participants {roles}",
    )
    steps.ok(f"shipment {sscc} created by the owner; participants {', '.join(roles)}")

    driver_id = seeded.users[f.account_with_role(f.CARRIER, "DRIVER").email]["id"]
    api.post(f"/api/v1/shipments/{shipment_id}/driver", carrier_manager, {"driver_user_id": driver_id})
    steps.ok("the carrier's dispatcher assigns its driver")

    steps.section("Pickup")
    pickup_code = api.post(f"/api/v1/shipments/{shipment_id}/pickup-code", owner_manager)["code"]
    steps.ok("the owner issues a six-digit pickup code to hand to the driver")
    wrong = f"{(int(pickup_code) + 1) % 1_000_000:06d}"
    pickup_path = f"/api/v1/shipments/{shipment_id}/pickup"
    err = expect_problem(
        lambda: api.post(pickup_path, driver, {"sscc": sscc, "code": wrong, "position": position(f.ORIGIN)}),
        422,
        "PICKUP_CODE_INVALID",
    )
    steps.ok(f"a wrong pickup code is refused ({err.problem.get('remaining_attempts')} attempts left)")
    picked = api.post(pickup_path, driver, {"sscc": sscc, "code": pickup_code, "position": position(f.ORIGIN)})
    expect(picked["status"] == "IN_TRANSIT", f"status after pickup {picked['status']}")
    steps.ok("the driver scans the SSCC, enters the code at the cold store, and the shipment is IN_TRANSIT")

    steps.section("Cold chain")
    for name, who in (("owner", owner_admin), ("driver", driver)):
        wait_until_visible(api, who, sscc, name)
    ws_url = websocket_url(s.api_url)
    announce = _announcer(steps)
    owner_feed = Listener(ws_url, owner_admin, "owner admin", on_message=announce)
    driver_feed = Listener(ws_url, driver, "driver")
    receiver_feed = Listener(ws_url, receiver, "dock receiver")
    outsider_feed = Listener(ws_url, outsider, "outsider")
    listeners.extend([owner_feed, driver_feed, receiver_feed, outsider_feed])
    for feed in (owner_feed, driver_feed):
        answer = feed.subscribe(sscc)
        expect(answer["type"] == "subscribed", f"{feed.name} could not subscribe: {answer}")
    answer = outsider_feed.subscribe(sscc)
    expect(answer["type"] == "error" and answer["data"]["code"] == "NOT_FOUND", f"outsider subscription: {answer}")
    steps.ok("owner and driver follow the shipment's live telemetry; another tenant may not (NOT_FOUND)")

    steps.out(f"    replaying a {int(BREACH.duration_seconds)} s breach over MQTT as device SIM-{sscc}-1 …")
    replay(s, sscc)
    for feed in (owner_feed, driver_feed, receiver_feed):
        for kind in ("cold_chain.breach_confirmed", "cold_chain.breach_resolved"):
            got = feed.wait_for(lambda m, k=kind: m["type"] == k and m["data"]["sscc"] == sscc, NOTIFICATION_TIMEOUT)
            expect(got is not None, f"{feed.name} did not receive {kind}")
    confirmed = owner_feed.wait_for(lambda m: m["type"] == "cold_chain.breach_confirmed", 0)
    assert confirmed is not None
    latency = _seconds(confirmed["sent_at"]) - _seconds(confirmed["data"]["confirmed_at"])
    steps.ok(
        f"breach confirmed and resolved; notified to owner, driver, and dock receiver "
        f"{latency * 1000:.0f} ms after the confirming reading"
    )
    readings = owner_feed.count("telemetry.reading")
    expect(readings >= int(BREACH.duration_seconds // BREACH.interval_seconds) - 1, f"only {readings} live readings")
    expect(receiver_feed.count("telemetry.reading") == 0, "the dock receiver got readings without subscribing")
    expect(not outsider_feed.messages[1:], f"the outsider received {outsider_feed.messages[1:]}")
    steps.ok(f"{readings} live readings reached the subscribers only; the other tenant received nothing")

    incidents = api.get(f"/api/v1/telemetry/shipments/{sscc}/incidents", receiver)["items"]
    expect(len(incidents) == 1, f"{len(incidents)} incidents")
    incident = incidents[0]
    expect(incident["ended_at"] is not None and incident["duration_seconds"] >= 30, f"incident {incident}")
    expect(incident["incident_hash"] == confirmed["data"]["incident_hash"], "the incident hash differs from the event")
    steps.ok(
        f"incident {incident['id']}: {incident['duration_seconds']} s, peak "
        f"{incident['extreme_temperature_celsius']} °C, hash {incident['incident_hash'][:16]}…"
    )
    series = api.get(f"/api/v1/telemetry/shipments/{sscc}/readings", owner_admin, resolution="1m")["items"]
    expect(any(b["max_temperature_celsius"] > f.PRODUCT.max_temp_celsius for b in series), f"1-minute series {series}")
    summary = api.get("/api/v1/telemetry/incidents/summary", owner_admin)
    expect(summary["last_24h_count"] >= 1, f"summary {summary}")
    expect_problem(lambda: api.get(f"/api/v1/telemetry/shipments/{sscc}/readings", outsider), 404, "NOT_FOUND")
    steps.ok(f"readings per minute ({len(series)} buckets) and the incident summary; hidden from the other tenant")

    steps.section("Checkpoint and delivery")
    checkpoint_path = f"/api/v1/shipments/{shipment_id}/checkpoints"
    err = expect_problem(
        lambda: api.post(
            checkpoint_path, driver, {"sscc": sscc, "gln": f.CHECKPOINT.gln, "position": position(f.CHECKPOINT, 2000)}
        ),
        422,
        "OUTSIDE_GEOFENCE",
    )
    steps.ok(
        f"a checkpoint {err.problem.get('distance_meters'):.0f} m from the depot is refused "
        f"(geo-fence {err.problem.get('allowed_meters')} m)"
    )
    api.post(checkpoint_path, driver, {"sscc": sscc, "gln": f.CHECKPOINT.gln, "position": position(f.CHECKPOINT)})
    steps.ok(f"the driver checks in at {f.CHECKPOINT.name}")
    delivered = api.post(
        f"/api/v1/shipments/{shipment_id}/delivery", receiver, {"sscc": sscc, "position": position(f.DESTINATION)}
    )
    expect(delivered["status"] == "DELIVERED", f"status after delivery {delivered['status']}")
    steps.ok(f"the dock receiver scans the pallet at {f.DESTINATION.name}: DELIVERED")

    integrity = api.get(f"/api/v1/shipments/{shipment_id}/integrity", receiver)
    expect(integrity["valid"] and integrity["event_count"] == 5, f"integrity {integrity}")
    steps.ok(f"the event log verifies: {integrity['event_count']} events, head {integrity['head_hash'][:16]}…")
    expect_problem(lambda: api.get(f"/api/v1/shipments/{shipment_id}", outsider), 404, "NOT_FOUND")
    steps.ok("the other tenant cannot see the shipment (404)")

    steps.section("Recall")
    recall = api.post(f"/api/v1/lots/{lot['id']}/recall", owner_admin, {"reason": "Supplier reported contamination"})
    expect(recall["affected_shipment_count"] == 1, f"recall {recall}")
    for feed in (owner_feed, driver_feed, receiver_feed):
        got = feed.wait_for(
            lambda m: m["type"] == "shipment.recalled" and m["data"]["sscc"] == sscc, NOTIFICATION_TIMEOUT
        )
        expect(got is not None, f"{feed.name} did not receive shipment.recalled")
    steps.ok("the owner recalls the lot; owner, driver, and dock receiver are alerted at once")
    expect_problem(
        lambda: api.post(f"/api/v1/shipments/{shipment_id}/cancel", owner_manager, {"reason": "Too late"}),
        409,
        "SHIPMENT_RECALLED_LOCKED",
    )
    steps.ok("the recalled shipment is locked: commands answer SHIPMENT_RECALLED_LOCKED")
    integrity = api.get(f"/api/v1/shipments/{shipment_id}/integrity", receiver)
    expect(integrity["valid"] and integrity["event_count"] == 6, f"integrity after recall {integrity}")
    steps.ok("the event log still verifies with the recall: 6 events")


def wait_until_visible(api: Api, token: str, sscc: str, who: str) -> None:
    """Wait until the telemetry service projects the shipment for the caller, which follows core's events."""
    deadline = time.monotonic() + VISIBILITY_TIMEOUT
    while True:
        try:
            api.get(f"/api/v1/telemetry/shipments/{sscc}/incidents", token)
            return
        except ApiError as err:
            if err.status not in (403, 404) or time.monotonic() > deadline:
                raise Failed(f"the telemetry service does not show {sscc} to the {who}: {err}") from err
        time.sleep(0.5)


def replay(s: Settings, sscc: str) -> None:
    """Publish the breach readings for the SSCC in real time."""
    publisher = MqttPublisher(s.mqtt_url, s.mqtt_username, s.mqtt_password)
    try:
        play(BREACH, devices_for([sscc], 1, BREACH.interval_seconds, seed=None), publisher, threading.Event())
    finally:
        publisher.close()


def _announcer(steps: Steps) -> Callable[[str, dict], None]:
    def announce(_name: str, message: dict) -> None:
        if message["type"].startswith("cold_chain."):
            data = message["data"]
            detail = f"{data.get('temperature_celsius', data.get('extreme_temperature_celsius'))} °C"
            steps.out(f"    ← {message['type']} at {message['sent_at']} ({detail})")

    return announce


def _seconds(timestamp: str) -> float:
    return dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()
