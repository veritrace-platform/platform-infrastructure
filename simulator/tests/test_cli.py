import threading

import pytest

from veritrace_simulator import cli, scenario
from veritrace_simulator.fleet import devices_for
from veritrace_simulator.publisher import parse_broker_url

SSCC = "089300010000000018"


class Recorder:
    def __init__(self):
        self.messages = []
        self.closed = False

    def publish(self, topic, payload):
        self.messages.append((topic, payload))

    def close(self):
        self.closed = True


def test_dry_run_prints_every_reading(capsys):
    assert cli.main(["run", "short-excursion", "--sscc", SSCC, "--dry-run", "--seed", "3"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 29  # 145 s at one reading every 5 s
    topic, payload = lines[0].split(" ", 1)
    assert topic == f"veritrace/v1/devices/SIM-{SSCC}-1/telemetry"
    assert payload.startswith('{"sscc":"089300010000000018","ts":')


def test_ticks_bound_a_run(capsys):
    assert cli.main(["run", "normal", "--sscc", SSCC, "--dry-run", "--ticks", "3"]) == 0
    assert len(capsys.readouterr().out.splitlines()) == 3


def test_invalid_sscc_is_a_usage_error():
    assert cli.main(["run", "normal", "--sscc", "089300010000000019", "--dry-run"]) == 2


def test_publishing_needs_a_password(monkeypatch):
    monkeypatch.delenv("MQTT_PASSWORD", raising=False)
    assert cli.main(["run", "normal", "--sscc", SSCC]) == 1


def test_list(capsys):
    assert cli.main(["list"]) == 0
    assert "sustained-breach" in capsys.readouterr().out


def test_play_paces_ticks_by_the_clock():
    loaded = scenario.load("sensor-gap")
    devices = devices_for([SSCC], 1, loaded.interval_seconds, seed=1)
    now = [1_000.0]
    waits = []

    class Stop(threading.Event):
        def wait(self, timeout=None):
            waits.append(timeout)
            now[0] += timeout
            return False

    recorder = Recorder()
    assert cli.play(loaded, devices, recorder, Stop(), max_ticks=6, clock=lambda: now[0]) == 0
    assert waits == [0, 5, 5, 5, 5, 5]
    assert [p["ts"] for _, p in recorder.messages] == [1_000_000 + 5_000 * k for k in range(6)]


def test_play_loops_until_stopped():
    loaded = scenario.parse("name: x\ninterval_seconds: 5\nphases: [{duration_seconds: 10, temperature: 4}]")
    devices = devices_for([SSCC], 1, 5, seed=1)
    recorder = Recorder()
    assert cli.play(loaded, devices, recorder, threading.Event(), loop=True, max_ticks=5, realtime=False) == 0
    # The loop continues the timeline, so timestamps keep increasing across repetitions.
    timestamps = [p["ts"] for _, p in recorder.messages]
    assert len(timestamps) == 5
    assert timestamps == sorted(timestamps)
    assert len(set(timestamps)) == 5


def test_play_stops_when_asked():
    loaded = scenario.load("normal")
    stop = threading.Event()
    stop.set()
    recorder = Recorder()
    assert cli.play(loaded, devices_for([SSCC], 1, 5, seed=1), recorder, stop) == 0
    assert recorder.messages == []


@pytest.mark.parametrize(
    ("url", "expected"),
    [("mqtt://localhost:1883", ("localhost", 1883)), ("mqtt://mosquitto", ("mosquitto", 1883))],
)
def test_parse_broker_url(url, expected):
    assert parse_broker_url(url) == expected


@pytest.mark.parametrize("url", ["localhost:1883", "tcp://localhost:1883", "mqtt://"])
def test_parse_broker_url_rejects(url):
    with pytest.raises(ValueError, match="MQTT_URL"):
        parse_broker_url(url)
