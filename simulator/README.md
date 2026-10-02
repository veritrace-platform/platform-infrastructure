# IoT fleet simulator

Replays cold-chain scenarios as device readings over MQTT, so that the telemetry service can be exercised
without hardware. Each simulated device publishes one reading per interval to
`veritrace/v1/devices/{device_id}/telemetry`, in the payload format of
[messaging.md §1](https://github.com/veritrace-platform/veritrace/blob/main/docs/contracts/messaging.md#1-mqtt-device-telemetry).
It connects as the development user `fleet-simulator`, which may publish for any device.

## Scenarios

The scenarios are written for goods kept at 2–8 °C, the bounds of chilled products such as fresh milk. The
breach rules they exercise are in
[cold-chain-monitoring.md](https://github.com/veritrace-platform/veritrace/blob/main/docs/domain/cold-chain-monitoring.md).

| Scenario | What happens | Expected outcome |
| --- | --- | --- |
| `normal` | 4–5 °C for five minutes | No excursion |
| `short-excursion` | A door opens for 25 s | Excursion shorter than 30 s; no breach |
| `sustained-breach` | The compressor fails for 90 s | Breach confirmed 30 s into the excursion, resolved when the temperature recovers |
| `sensor-gap` | Two 20 s excursions with 20 s of silence between them | The gap ends the episode; no breach |

A scenario is a YAML file of phases; see `src/veritrace_simulator/scenario.py` for the format. Pass a path
instead of a name to replay your own.

## Running

Readings are evaluated only for shipments that exist, so pass the SSCC of a shipment created through the core
API. Any valid SSCC is stored.

```bash
# In the compose network (from platform-infrastructure):
make simulate SCENARIO=sustained-breach SSCC=089300010000000018
make simulate SCENARIO=normal SSCC="089300010000000018 089345670000000017" ARGS="--devices-per-shipment 2 --loop"

# On the host:
cd simulator
MQTT_PASSWORD=simulator-dev uv run veritrace-simulator run sustained-breach --sscc 089300010000000018
uv run veritrace-simulator run sensor-gap --sscc 089300010000000018 --dry-run   # print instead of publishing
```

| Option | Effect |
| --- | --- |
| `--sscc` | Shipment to report on; repeatable |
| `--devices-per-shipment` | Devices on each shipment (default 1); their readings are staggered within the interval |
| `--loop` | Repeat the scenario until stopped |
| `--ticks` | Stop after this many intervals |
| `--seed` | Make the temperature noise reproducible |
| `--dry-run` | Print the readings at once instead of publishing them |

The broker connection comes from `MQTT_URL` (default `mqtt://localhost:1883`), `MQTT_USERNAME` (default
`fleet-simulator`), and `MQTT_PASSWORD`.

## Development

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv run pytest
```
