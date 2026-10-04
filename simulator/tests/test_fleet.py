import pytest

from veritrace_simulator import scenario
from veritrace_simulator.fleet import devices_for, timeline

SSCC = "089300010000000018"
OTHER_SSCC = "089345670000000017"
START_MS = 1_790_000_000_000

# The breach rule of docs/domain/cold-chain-monitoring.md section 4, for 2–8 °C goods.
T_MIN, T_MAX = 2.0, 8.0
CONFIRM_SECONDS, MAX_GAP_SECONDS = 30, 15


def readings(name, per_shipment=1, ssccs=(SSCC,)):
    loaded = scenario.load(name)
    devices = devices_for(list(ssccs), per_shipment, loaded.interval_seconds, seed=42)
    return [m.payload for tick in timeline(loaded, devices, START_MS) for m in tick.messages]


def longest_excursion(payloads, max_gap=MAX_GAP_SECONDS):
    """Return the longest span of an episode of out-of-bounds readings, in seconds."""
    longest, start, last = 0.0, None, None
    for p in sorted(payloads, key=lambda p: p["ts"]):
        t = p["ts"] / 1000
        if last is not None and t - last > max_gap:
            start = None
        if T_MIN <= p["temperature_c"] <= T_MAX:
            start = None
        else:
            start = t if start is None else start
            longest = max(longest, t - start)
        last = t
    return longest


def test_normal_never_leaves_the_bounds():
    assert longest_excursion(readings("normal")) == 0


def test_short_excursion_is_too_short_for_a_breach():
    assert 0 < longest_excursion(readings("short-excursion")) < CONFIRM_SECONDS


def test_sustained_breach_is_confirmed_and_resolved():
    payloads = readings("sustained-breach")
    assert longest_excursion(payloads) >= CONFIRM_SECONDS
    assert T_MIN <= payloads[-1]["temperature_c"] <= T_MAX


def test_sensor_gap_splits_the_excursion():
    payloads = readings("sensor-gap")
    assert 0 < longest_excursion(payloads) < CONFIRM_SECONDS
    # Without the gap rule, the two excursions would add up to a breach.
    assert longest_excursion(payloads, max_gap=float("inf")) >= CONFIRM_SECONDS


def test_payload_format():
    payload = readings("normal")[0]
    # docs/contracts/messaging.md section 1; the device ID is in the topic, never in the payload.
    assert list(payload) == ["sscc", "ts", "temperature_c", "humidity_pct", "lat", "lng"]
    assert payload["sscc"] == SSCC
    assert payload["ts"] == START_MS
    assert isinstance(payload["ts"], int)
    assert 0 <= payload["humidity_pct"] <= 100


def test_one_reading_per_device_per_interval():
    loaded = scenario.load("normal")
    payloads = readings("normal", per_shipment=2, ssccs=(SSCC, OTHER_SSCC))
    assert len(payloads) == 4 * loaded.duration_seconds / loaded.interval_seconds
    assert {p["sscc"] for p in payloads} == {SSCC, OTHER_SSCC}


def test_devices_on_one_shipment_do_not_share_timestamps():
    devices = devices_for([SSCC], 2, 5, seed=1)
    assert [d.device_id for d in devices] == [f"SIM-{SSCC}-1", f"SIM-{SSCC}-2"]
    assert devices[0].topic == f"veritrace/v1/devices/SIM-{SSCC}-1/telemetry"
    assert [d.lead_ms for d in devices] == [0, 2500]
    first_tick = next(timeline(scenario.load("normal"), devices, START_MS))
    assert [m.payload["ts"] for m in first_tick.messages] == [START_MS, START_MS - 2500]


def test_silent_phases_publish_nothing():
    loaded = scenario.load("sensor-gap")
    ticks = list(timeline(loaded, devices_for([SSCC], 1, 5, seed=1), START_MS))
    silent = [t for t in ticks if t.phase == "sensor offline"]
    assert len(silent) == 4
    assert all(not t.messages for t in silent)


def test_a_seed_makes_runs_reproducible():
    assert readings("short-excursion") == readings("short-excursion")


@pytest.mark.parametrize("sscc", ["089300010000000019", "8930001001015", "abc"])
def test_invalid_ssccs_are_refused(sscc):
    with pytest.raises(ValueError, match="not a valid SSCC"):
        devices_for([sscc], 1, 5, seed=None)
