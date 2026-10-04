from veritrace_demo import cli
from veritrace_demo.notifications import websocket_url


def test_accounts(capsys):
    assert cli.main(["accounts"]) == 0
    out = capsys.readouterr().out
    assert "driver@mekongcold.example" in out
    assert "DEMO_PASSWORD" in out


def test_commands_need_a_password(monkeypatch):
    monkeypatch.delenv("DEMO_PASSWORD", raising=False)
    assert cli.main(["seed"]) == 2
    monkeypatch.setenv("DEMO_PASSWORD", "short")
    assert cli.main(["seed"]) == 2


def test_the_scenario_needs_the_mqtt_password(monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", "veritrace-demo-2026")
    monkeypatch.delenv("MQTT_PASSWORD", raising=False)
    assert cli.main(["scenario"]) == 2


def test_websocket_url():
    assert websocket_url("http://gateway:8000") == "ws://gateway:8000/ws/v1/notifications"
    assert websocket_url("https://api.example.com/") == "wss://api.example.com/ws/v1/notifications"


def test_describe():
    breach = {
        "type": "cold_chain.breach_confirmed",
        "sent_at": "2026-10-02T13:29:45.492Z",
        "data": {
            "sscc": "089300010000000018",
            "temperature_celsius": 10.68,
            "min_temp_celsius": 2,
            "max_temp_celsius": 8,
            "started_at": "2026-10-02T13:29:15.454Z",
        },
    }
    line = cli._describe(breach)
    assert "BREACH" in line and "10.68 °C outside 2–8 °C" in line
    reading = {
        "type": "telemetry.reading",
        "sent_at": "t",
        "data": {"sscc": "089300010000000018", "temperature_celsius": 5, "device_id": "SIM-1"},
    }
    assert "reading" in cli._describe(reading)
