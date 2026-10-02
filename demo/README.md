# Demonstration kit

Everything needed to demonstrate M1 — Operational Core on a workstation:

- **Seed** (`make seed`): four companies, their users, locations, products, and lots, created through the public
  APIs. It is idempotent: it creates what is missing and leaves the rest alone.
- **Acceptance run** (`make demo`): one shipment through the whole custody handover, a cold-chain breach, and
  a recall, checking at each step what the platform answers. It doubles as the M1 acceptance test and takes
  about two minutes.
- **Notification watcher** (`make demo-watch`): the real-time notifications of any demo account, in the
  terminal.

## Quick start

```bash
cd platform-infrastructure
make up-apps        # the stack with core and telemetry built from the sibling repositories
make seed           # the demo world
make demo           # the acceptance run; exits non-zero on the first unexpected answer
```

The kit runs as a container of the `demo` profile and reaches the API through the gateway, so it works the same
whether the services run in containers (`make up-apps`) or on the host (`make up` and `make run` in each
service).

## The demo world

| Company | Code | Part | Places |
| --- | --- | --- | --- |
| Saigon Fresh Foods Joint Stock Company | `SGFRESH` | Owner: makes the goods and ships them | Head office `8930001001015`; Tan Thuan cold store `8930001000025` (origin) |
| Mekong Cold Chain Logistics Company Limited | `MEKONG_COLD` | Carrier | Thu Duc cold depot `8935002000012` (checkpoint) |
| District 7 Fresh Mart Company Limited | `D7MART` | Consignee | District 7 store hub `8934567000017` (destination) |
| Hanoi Dairy Corporation | `HANOI_DAIRY` | Another tenant, which must see none of the above | Hanoi Dairy plant `8936003000018` |

Saigon Fresh Foods sells pasteurized fresh milk (`08930001000018`, 2–8 °C), natural yogurt (`08930001000025`,
2–6 °C), and frozen basa fillet (`08930001000032`, −25 to −18 °C), with one lot of each at the cold store
(`L2026-MILK-01`, `L2026-YOG-01`, `L2026-BASA-01`). The cold store and the store hub lie at the two ends of the
simulator's default route.

### Accounts

Every account signs in with `DEMO_PASSWORD` from `.env` (`veritrace-demo-2026` unless you changed it).
`make demo-accounts` prints this table.

| Company | Role | Email | Name |
| --- | --- | --- | --- |
| `SGFRESH` | `ADMIN` | `admin@sgfresh.example` | Nguyen Van An |
| `SGFRESH` | `WAREHOUSE_MANAGER` | `warehouse@sgfresh.example` | Le Thi Hoa |
| `MEKONG_COLD` | `ADMIN` | `admin@mekongcold.example` | Pham Minh Quan |
| `MEKONG_COLD` | `WAREHOUSE_MANAGER` | `dispatch@mekongcold.example` | Vo Thanh Tam |
| `MEKONG_COLD` | `DRIVER` | `driver@mekongcold.example` | Tran Van Binh |
| `D7MART` | `ADMIN` | `admin@d7mart.example` | Do Thu Trang |
| `D7MART` | `WAREHOUSE_MANAGER` | `dock@d7mart.example` | Huynh Quoc Bao |
| `HANOI_DAIRY` | `ADMIN` | `admin@hanoidairy.example` | Bui Duc Long |

## The acceptance run

Each run commissions a lot of its own (`DEMO-<date>-<time>`) and ships it, so it can run again on the same
stack. In order, it checks that:

1. **Platform and seed data:** core publishes its token keys through the gateway; the seed is in place; every
   role signs in.
2. **Lot and shipment:** the owner's warehouse manager commissions 480 bottles of milk and ships them to the
   store hub with `MEKONG_COLD` as carrier. The SSCC belongs to the owner, and the participants are the owner,
   the carrier, and the consignee. The carrier's dispatcher assigns its driver.
3. **Pickup:** the owner issues a pickup code. A wrong code is refused with `PICKUP_CODE_INVALID`; the right code,
   scanned SSCC, and a position at the cold store put the shipment `IN_TRANSIT`.
4. **Cold chain:** the owner and the driver subscribe to the shipment's live telemetry; the Hanoi tenant may not
   (`NOT_FOUND`). The kit replays 65 s of readings over MQTT, with 40 s above 8 °C. The breach is confirmed
   30 s into the excursion and resolved when the temperature recovers. The owner, the driver, and the dock
   receiver are notified within a second, and only the subscribers get live readings. The incident, with its
   hash, the per-minute readings, and the incident summary are served by the telemetry API, and hidden from the
   Hanoi tenant.
5. **Checkpoint and delivery:** a checkpoint 2 km from the depot is refused with `OUTSIDE_GEOFENCE`; at the depot it
   is recorded. The dock receiver delivers at the store hub. The event log verifies (5 events), and the Hanoi
   tenant cannot see the shipment (404).
6. **Recall:** the owner recalls the lot. Everyone who may view the shipment is alerted at once, the shipment is
   locked (`SHIPMENT_RECALLED_LOCKED`), and the event log still verifies with the recall (6 events).

The run prints one line per check and ends with `The M1 acceptance run passed: 22 checks.`, or with the first
unexpected answer, its problem code, and its `trace_id`, which leads to the service log.

## Presenting live

A suggested sequence with three terminals in `platform-infrastructure`:

1. `make up-apps && make seed`, and `make up-tools` for Kafka UI on <http://localhost:8085>.
2. Terminal 1: `make demo-watch ACCOUNT=admin@d7mart.example`, the consignee's alerts.
3. Terminal 2: `make demo`, which narrates each step and the breach as it happens.
4. Kafka UI: the `shipment.events`, `iot.telemetry.raw`, and `telemetry.incidents` topics.
5. Terminal 3: `make psql-core` and `SELECT sequence, event_type, event_hash FROM core.shipment_events ORDER BY
   id DESC LIMIT 6;` for the hash chain; `make psql-telemetry` and `SELECT * FROM
   telemetry.cold_chain_incidents;` for the incident.
6. Other scenarios for a shipment in transit: `make simulate SCENARIO=sensor-gap SSCC=<sscc>` (no breach), or
   `make demo-watch ACCOUNT=admin@sgfresh.example SSCC=<sscc>` to follow its readings.

## Starting over

`make reset` deletes every volume, and with it the demo data; `make up-apps && make seed` brings it back. The seed
never changes what exists, so a stack seeded with another `DEMO_PASSWORD` keeps its passwords: use the old one, or
reset.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `502` from the gateway | The services are not running: `make up-apps`, or start them on the host. |
| `rate limited …; waiting` | Sign-in allows 10 attempts a minute per client address; the kit waits and continues. |
| `cannot sign in with DEMO_PASSWORD` | The stack was seeded with another password. |
| `the telemetry service does not show <sscc>` | Telemetry is not running, or it does not follow `shipment.events`; check `make logs SERVICE=telemetry-stream-service`. |
| No breach notification | Check that Mosquitto is healthy (`make ps`) and that telemetry's `/readyz` on <http://localhost:8091/readyz> reports `mqtt: ok`. |

## Running on the host

```bash
cd platform-infrastructure/demo
uv sync
API_URL=http://localhost:8000 DEMO_PASSWORD=veritrace-demo-2026 MQTT_PASSWORD=simulator-dev \
  uv run veritrace-demo scenario
```

`veritrace-demo` also reads `MQTT_URL` (default `mqtt://localhost:1883`) and `MQTT_USERNAME` (default
`fleet-simulator`).

## Development

Python 3.13 with uv, ruff, and pytest, as the simulator, whose package the kit uses to replay readings.

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv run pytest
```
