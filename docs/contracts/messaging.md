# Messaging Contracts

Asynchronous contracts between devices, services, and clients. Field names are `snake_case`. Timestamps
are RFC 3339 in UTC (`2026-09-01T14:30:00.123456Z`). Temperatures are in °C and coordinates are WGS-84
decimal degrees.

Compatibility rule:

- Consumers ignore unknown fields.
- Producers may add optional fields within a version.
- Removing or renaming a field, or changing its meaning, requires incrementing `event_version`. During a
  migration, both versions are published.

---

## 1. MQTT: device telemetry

| Property | Value |
| --- | --- |
| Broker | Eclipse Mosquitto 2, MQTT 5 (3.1.1 also accepted from devices) |
| Topic | `veritrace/v1/devices/{device_id}/telemetry` |
| QoS | 1 (at least once); retain disabled |
| Authentication | Username and password per device. Local development also has the shared user `fleet-simulator`. |
| Authorization (ACL) | A device may publish only to its own topic (`%u` pattern). `telemetry-ingest` may subscribe to `veritrace/v1/devices/+/telemetry`. |
| Consumer | `telemetry-stream-service` through the shared subscription `$share/telemetry-ingest/veritrace/v1/devices/+/telemetry` |

Payload (compact, because it is sent by constrained devices):

```json
{
  "sscc": "089300010000000018",
  "ts": 1788273000123,
  "temperature_c": 9.4,
  "humidity_pct": 65.2,
  "lat": 10.870500,
  "lng": 106.803500
}
```

| Field | Type | Rule |
| --- | --- | --- |
| `sscc` | string | Valid SSCC-18 |
| `ts` | integer | Device time, Unix epoch milliseconds |
| `temperature_c` | number | −50…80 |
| `humidity_pct` | number | 0…100; optional |
| `lat`, `lng` | number | valid WGS-84 |

The device ID is taken from the topic, never from the payload.

---

## 2. Kafka: conventions

| Property | Value |
| --- | --- |
| Cluster | Apache Kafka 4 in KRaft mode. Automatic topic creation is disabled; topics are created by infrastructure. |
| Encoding | UTF-8 JSON value; the key is a UTF-8 string |
| Headers | `traceparent` (W3C Trace Context), `content-type: application/json`, `event-type` |
| Producer | Idempotent, `acks=all` |
| Delivery | At least once. Consumers are idempotent. |

| Topic | Key | Partitions | Retention | Producer | Consumers |
| --- | --- | --- | --- | --- | --- |
| `iot.telemetry.raw` | `sscc` | 6 | 7 days | telemetry ingest | telemetry processor |
| `iot.telemetry.dlq` | `sscc` | 1 | 14 days | telemetry processor | operators |
| `shipment.events` | `sscc` | 6 | unlimited | core (outbox relay) | telemetry projection, relayer (M2) |
| `telemetry.incidents` | `sscc` | 6 | unlimited | telemetry processor | relayer (M2) |

Consumer group IDs follow `<service>.<purpose>`, for example `telemetry-stream-service.projection`.

### 2.1 Domain event envelope

`shipment.events` and `telemetry.incidents` share this envelope:

```json
{
  "event_id": "01927c6e-8a1b-7c3d-9e4f-5a6b7c8d9e0f",
  "event_type": "shipment.pickup_confirmed",
  "event_version": 1,
  "occurred_at": "2026-09-01T14:35:00.000000Z",
  "producer": "core-business-service",
  "subject": {
    "shipment_id": "01927c6e-0000-7000-8000-000000000001",
    "sscc": "089300010000000018",
    "status": "IN_TRANSIT"
  },
  "actor": {
    "tenant_id": "01927c6e-0000-7000-8000-00000000000a",
    "user_id": "01927c6e-0000-7000-8000-00000000000b"
  },
  "sequence": 3,
  "prev_event_hash": "…64 hex…",
  "event_hash": "…64 hex…",
  "data": { }
}
```

- `sequence`, `prev_event_hash`, and `event_hash` are present on shipment events only. Incidents carry
  `data.incident_hash` instead.
- `actor` is `null` for system-produced events.

**Hash input:** RFC 8785 canonical JSON of the object
`{event_id, event_type, event_version, occurred_at, subject, actor, sequence, prev_event_hash, data}`.
`event_hash` is its SHA-256 in lowercase hex. `producer` and transport headers are not hashed.

---

## 3. Kafka topic `shipment.events`

Payload (`data`) per event type. All events are `event_version` 1.

**`shipment.created`**

```json
{
  "owner_tenant_id": "uuid",
  "lot_id": "uuid",
  "gtin": "08930001000018",
  "product_name": "Pasteurized Fresh Milk 1L",
  "lot_number": "LOT-2026-0901",
  "expiration_date": "2026-09-15",
  "quantity": 480,
  "min_temp_celsius": 2.0,
  "max_temp_celsius": 8.0,
  "origin": { "location_id": "uuid", "gln": "8930001001015", "name": "Binh Duong DC" },
  "destination": { "location_id": "uuid", "gln": "8934567000017", "name": "District 7 Store Hub" },
  "participants": [
    { "tenant_id": "uuid", "role": "OWNER" },
    { "tenant_id": "uuid", "role": "CARRIER" },
    { "tenant_id": "uuid", "role": "CONSIGNEE" }
  ],
  "assigned_driver_id": null
}
```

**`shipment.participant_added`**: `{ "tenant_id": "uuid", "role": "CARRIER" | "INSPECTOR" }`

**`shipment.driver_assigned`**: `{ "driver_user_id": "uuid" }`

**`shipment.pickup_confirmed`**

```json
{
  "driver_user_id": "uuid",
  "position": { "latitude": 10.870512, "longitude": 106.803488, "accuracy_meters": 12.0 },
  "distance_meters": 18.4
}
```

**`shipment.checkpoint_recorded`**: `{ "facility": { "gln": "…", "name": "…" }, "position": {…}, "distance_meters": 25.1 }`

**`shipment.delivery_confirmed`**: `{ "receiver_user_id": "uuid", "position": {…}, "distance_meters": 9.7 }`

**`shipment.cancelled`**: `{ "reason": "Customer order withdrawn" }`

**`shipment.recalled`**

```json
{
  "recall_id": "uuid",
  "lot_id": "uuid",
  "gtin": "08930001000018",
  "lot_number": "LOT-2026-0901",
  "reason": "Supplier reported contamination",
  "previous_status": "IN_TRANSIT"
}
```

**`shipment.document_attached`** (M2)

```json
{
  "document_id": "uuid",
  "document_type": "CERTIFICATE_OF_QUALITY",
  "plaintext_sha256": "…64 hex…",
  "ciphertext_cid": "bafy…"
}
```

---

## 4. Kafka topic `iot.telemetry.raw`

Normalized readings, one message per reading. This topic has no domain envelope, because it carries raw
data rather than domain events.

```json
{
  "device_id": "REEFER-0001",
  "sscc": "089300010000000018",
  "recorded_at": "2026-09-01T14:30:00.123Z",
  "received_at": "2026-09-01T14:30:00.410Z",
  "temperature_celsius": 9.4,
  "humidity_percent": 65.2,
  "latitude": 10.8705,
  "longitude": 106.8035
}
```

`iot.telemetry.dlq` wraps a failed record as `{ "error": "…", "failed_at": "…", "record": { … } }`.

---

## 5. Kafka topic `telemetry.incidents`

Envelope from §2.1 with `producer = "telemetry-stream-service"` and `actor = null`.

**`cold_chain.breach_confirmed`**

```json
{
  "incident_id": "uuid",
  "shipment_id": "uuid",
  "sscc": "089300010000000018",
  "device_id": "REEFER-0001",
  "started_at": "2026-09-01T14:30:00.000Z",
  "confirmed_at": "2026-09-01T14:30:30.000Z",
  "min_temp_celsius": 2.0,
  "max_temp_celsius": 8.0,
  "temperature_celsius": 9.4,
  "latitude": 10.8705,
  "longitude": 106.8035,
  "incident_hash": "…64 hex…"
}
```

`incident_hash` is the SHA-256 of the RFC 8785 canonical JSON of this object without `incident_hash`.

**`cold_chain.breach_resolved`**

```json
{
  "incident_id": "uuid",
  "sscc": "089300010000000018",
  "ended_at": "2026-09-01T14:36:10.000Z",
  "duration_seconds": 370,
  "extreme_temperature_celsius": 11.2
}
```

---

## 6. WebSocket: real-time notifications

| Property | Value |
| --- | --- |
| Endpoint | `GET /ws/v1/notifications` (telemetry-stream-service, behind the gateway) |
| Subprotocols | The client offers `["veritrace.v1", "bearer.<access_token>"]`; the server selects `veritrace.v1` |
| Authorization | Tenant and role from the token. Notifications go only to participant tenants of the affected shipment. `DRIVER` connections receive only their assigned shipments. |
| Heartbeat | Server ping every 30 s; the connection is closed if no pong arrives within 10 s |
| Token expiry | The server closes the connection with `4401` at token expiry; the client reconnects with a fresh token |
| Close codes | `4400` bad message, `4401` unauthenticated or expired, `4403` forbidden subscription, `4408` too many subscriptions (max 20), `1001` server shutdown |

### 6.1 Server → client

Every message:

```json
{ "type": "…", "id": "uuid", "sent_at": "…", "data": { … } }
```

| `type` | Delivered to | `data` |
| --- | --- | --- |
| `cold_chain.breach_confirmed` | participants and the assigned driver | §5 payload plus `product_name` and `gtin` |
| `cold_chain.breach_resolved` | same | §5 payload |
| `shipment.recalled` | participants of the recalled shipment | `{shipment_id, sscc, recall_id, gtin, lot_number, product_name, reason}` |
| `telemetry.reading` | subscribers of the SSCC | §4 payload without `received_at` |
| `subscribed` / `unsubscribed` | requester | `{ "channel": "telemetry", "sscc": "…" }` |
| `error` | requester | `{ "code": "FORBIDDEN" \| "NOT_FOUND" \| "INVALID_MESSAGE", "message": "…" }` |

### 6.2 Client → server

```json
{ "type": "subscribe", "channel": "telemetry", "sscc": "089300010000000018" }
{ "type": "unsubscribe", "channel": "telemetry", "sscc": "089300010000000018" }
```

Subscriptions are allowed only for shipments that the caller may view
([access-control.md](../domain/access-control.md)).
