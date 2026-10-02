import pytest

from veritrace_simulator import scenario
from veritrace_simulator.scenario import ScenarioError, parse

MINIMAL = """
name: probe
interval_seconds: 5
phases:
  - duration_seconds: 10
    temperature: 4
"""


def test_bundled_scenarios_load():
    names = scenario.bundled()
    assert names == ["normal", "sensor-gap", "short-excursion", "sustained-breach"]
    for name in names:
        loaded = scenario.load(name)
        assert loaded.name == name
        assert loaded.description
        assert loaded.interval_seconds == 5


def test_load_a_file(tmp_path):
    path = tmp_path / "custom.yaml"
    path.write_text(MINIMAL, encoding="utf-8")
    loaded = scenario.load(str(path))
    assert loaded.name == "probe"
    assert loaded.duration_seconds == 10
    assert loaded.humidity_percent is None
    assert loaded.jitter_celsius == 0.1
    assert loaded.phases[0].temperature_at(5) == 4


def test_load_an_unknown_scenario():
    with pytest.raises(ScenarioError, match="neither a bundled scenario"):
        scenario.load("does-not-exist")


def test_linear_temperature():
    loaded = parse(
        """
name: ramp
interval_seconds: 5
route: {from: {lat: 10, lng: 106}, to: {lat: 11, lng: 107}}
phases:
  - duration_seconds: 20
    temperature: {start: 2, end: 10}
  - duration_seconds: 10
    silent: true
"""
    )
    ramp, gap = loaded.phases
    assert [ramp.temperature_at(t) for t in (0, 5, 10, 20, 30)] == [2, 4, 6, 10, 10]
    assert gap.silent
    assert (loaded.origin.lat, loaded.destination.lng) == (10, 107)


@pytest.mark.parametrize(
    ("document", "message"),
    [
        ("- not a mapping", "a scenario is a mapping"),
        ("name: x\ninterval_seconds: 5\nphases: []", "phases must not be empty"),
        ("name: x\nphases: [{duration_seconds: 5, temperature: 4}]", "lacks interval_seconds"),
        ("name: x\ninterval_seconds: 0\nphases: [{duration_seconds: 5, temperature: 4}]", "must be positive"),
        ("name: x\ninterval_seconds: 5\ncolour: red\nphases: [{duration_seconds: 5, temperature: 4}]", "unknown keys"),
        ("name: x\ninterval_seconds: 5\nphases: [{duration_seconds: 5}]", "temperature must be"),
        ("name: x\ninterval_seconds: 5\nphases: [{duration_seconds: 5, temperature: 95}]", "within -50"),
        ("name: x\ninterval_seconds: 5\nphases: [{duration_seconds: 5, temperature: 4, silent: 1}]", "true or false"),
        (
            "name: x\ninterval_seconds: 5\nhumidity_percent: 120\nphases: [{duration_seconds: 5, temperature: 4}]",
            "humidity_percent",
        ),
        (
            "name: x\ninterval_seconds: 5\nroute: {from: {lat: 95, lng: 0}, to: {lat: 0, lng: 0}}\n"
            "phases: [{duration_seconds: 5, temperature: 4}]",
            "not a WGS-84",
        ),
        ("name: [x", "invalid YAML"),
    ],
)
def test_invalid_scenarios(document, message):
    with pytest.raises(ScenarioError, match=message):
        parse(document)
