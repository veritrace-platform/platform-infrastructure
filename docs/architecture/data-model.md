# Data Model

This document is the design reference for every database. The migrations in each service repository are
the executable source of truth. A pull request that changes one must change the other.

## 1. Conventions

| Topic | Rule |
| --- | --- |
| Engine | PostgreSQL 18. The telemetry database adds the TimescaleDB extension. |
| Layout | One database per service, and one application schema per database (`core`, `telemetry`, `relayer`). `public` holds only the migration version table. |
| Naming | `snake_case`. Tables are plural nouns. Foreign keys are `<entity>_id`. Timestamps end in `_at`. Booleans start with `is_`/`has_`. |
| Primary keys | `id uuid DEFAULT uuidv7()`. UUIDv7 is time-ordered, which keeps indexes compact and supports cursor pagination. |
| Time | `timestamptz`, stored and exchanged in UTC. Calendar dates (production and expiration) use `date`. |
| Money-like and measured values | `numeric` with explicit precision. Never floating point. |
| Enumerations | `text` with a `CHECK` constraint. Values are `UPPER_SNAKE_CASE`. |
| Constraint names | `<table>_<columns>_key` (unique), `<table>_<column>_fkey`, `<table>_<rule>_check`, `idx_<table>_<columns>` |
| Audit columns | `created_at` on every table. `updated_at` on mutable tables, maintained by a trigger. |

## 2. Database roles

| Role | Login | Purpose |
| --- | --- | --- |
| `veritrace_core_owner` | yes | Owns `veritrace_core`; runs core migrations |
| `veritrace_core_app` | yes | Core runtime. `NOBYPASSRLS`, DML only, subject to RLS |
| `veritrace_telemetry_owner` | yes | Owns `veritrace_telemetry`; runs telemetry migrations |
| `veritrace_telemetry_app` | yes | Telemetry runtime |
| `veritrace_relayer_owner` | yes | Owns `veritrace_relayer` (M2) |
| `veritrace_relayer_app` | yes | Relayer runtime (M2) |

Role names are fixed across environments, and passwords come from the environment. Infrastructure bootstrap
creates the roles and databases. Migrations create everything else.

---

## 3. Core database (`veritrace_core`, schema `core`)

### 3.1 Tenancy and identity (M1)

**`tenants`** (RLS: the caller's own row only)

| Column | Type | Constraints |
| --- | --- | --- |
| `id` | uuid | PK |
| `code` | text | unique, `^[A-Z0-9_]{3,32}$` |
| `legal_name` | text | 1–255 characters |
| `tax_code` | text | unique, `^[0-9]{10}(-[0-9]{3})?$` |
| `gs1_company_prefix` | text | unique, `^[0-9]{6,10}$` |
| `sscc_extension_digit` | smallint | 0–9, default 0 |
| `sscc_next_serial` | bigint | default 1; incremented atomically when an SSCC is issued |
| `status` | text | `ACTIVE`, `SUSPENDED` |
| `created_at`, `updated_at` | timestamptz | |

**`users`** (RLS: tenant)

| Column | Type | Constraints |
| --- | --- | --- |
| `id` | uuid | PK |
| `tenant_id` | uuid | FK `tenants` |
| `email` | text | unique on `lower(email)` across all tenants |
| `password_hash` | text | Argon2id PHC string |
| `full_name` | text | 1–255 characters |
| `phone` | text | nullable |
| `role` | text | `ADMIN`, `WAREHOUSE_MANAGER`, `DRIVER`, `INSPECTOR` |
| `is_active` | boolean | default true |
| `last_login_at` | timestamptz | nullable |
| `created_at`, `updated_at` | timestamptz | |

**`auth_sessions`** (RLS: tenant; refresh tokens)

| Column | Type | Constraints |
| --- | --- | --- |
| `id` | uuid | PK |
| `tenant_id`, `user_id` | uuid | FK |
| `family_id` | uuid | Rotation family; the whole family is revoked when reuse is detected |
| `token_hash` | bytea | unique; SHA-256 of the opaque token |
| `expires_at` | timestamptz | |
| `rotated_at`, `revoked_at` | timestamptz | nullable |
| `user_agent` | text | nullable |
| `created_at` | timestamptz | |

### 3.2 Catalog and inventory (M1)

**`locations`** (RLS: tenant)

| Column | Type | Constraints |
| --- | --- | --- |
| `id` | uuid | PK |
| `tenant_id` | uuid | FK |
| `gln` | char(13) | globally unique; digits; valid check digit; starts with the tenant's GCP |
| `name` | text | |
| `address` | text | |
| `city` | text | |
| `country_code` | char(2) | ISO 3166-1 alpha-2, default `VN` |
| `latitude` | numeric(9,6) | −90…90 |
| `longitude` | numeric(9,6) | −180…180 |
| `geo_fence_radius_meters` | integer | 50–5000, default 200 |
| `is_headquarters` | boolean | at most one true per tenant (partial unique index) |
| `is_active` | boolean | default true |
| `created_at`, `updated_at` | timestamptz | |

**`products`** (RLS: tenant)

| Column | Type | Constraints |
| --- | --- | --- |
| `id` | uuid | PK |
| `tenant_id` | uuid | FK |
| `gtin` | char(14) | globally unique; valid; tenant GCP at position 2 |
| `name` | text | |
| `description` | text | nullable |
| `min_temp_celsius`, `max_temp_celsius` | numeric(5,2) | −50…80; min < max |
| `is_active` | boolean | default true |
| `created_at`, `updated_at` | timestamptz | |

**`lots`** (RLS: the owner tenant, or a tenant that holds or held stock of the lot)

| Column | Type | Constraints |
| --- | --- | --- |
| `id` | uuid | PK |
| `tenant_id` | uuid | FK; owner (brand owner) |
| `product_id` | uuid | FK `products` |
| `lot_number` | text | `^[0-9A-Za-z._-]{1,20}$`; unique with `product_id` |
| `production_date`, `expiration_date` | date | expiration ≥ production |
| `quantity_commissioned` | integer | > 0 |
| `commissioned_location_id` | uuid | FK `locations` |
| `status` | text | `ACTIVE`, `RECALLED` |
| `recalled_at` | timestamptz | nullable |
| `created_by` | uuid | FK `users` |
| `created_at`, `updated_at` | timestamptz | |

**`inventory_balances`** (RLS: tenant)

| Column | Type | Constraints |
| --- | --- | --- |
| `tenant_id` | uuid | FK |
| `location_id` | uuid | FK; PK part |
| `lot_id` | uuid | FK; PK part |
| `quantity_on_hand` | integer | `>= 0` (this constraint guarantees no oversell) |
| `updated_at` | timestamptz | |

**`inventory_movements`** (RLS: tenant; append-only)

| Column | Type | Constraints |
| --- | --- | --- |
| `id` | uuid | PK |
| `tenant_id`, `location_id`, `lot_id` | uuid | FK |
| `quantity_delta` | integer | ≠ 0 |
| `reason` | text | `COMMISSIONED`, `SHIPMENT_CREATED`, `SHIPMENT_CANCELLED`, `SHIPMENT_DELIVERED` |
| `shipment_id` | uuid | nullable FK |
| `created_by` | uuid | FK `users` |
| `created_at` | timestamptz | |

### 3.3 Shipments (M1)

**`shipments`** (RLS: participants)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid | PK |
| `owner_tenant_id` | uuid | FK `tenants` |
| `sscc` | char(18) | globally unique |
| `lot_id` | uuid | FK `lots` |
| `quantity` | integer | > 0 |
| `gtin`, `product_name`, `lot_number`, `expiration_date` | | Snapshot |
| `min_temp_celsius`, `max_temp_celsius` | numeric(5,2) | Snapshot |
| `origin_location_id` | uuid | FK `locations` (the owner's) |
| `origin_gln`, `origin_name`, `origin_latitude`, `origin_longitude`, `origin_geo_fence_radius_meters` | | Snapshot |
| `destination_location_id` | uuid | FK `locations` (the consignee's) |
| `destination_gln`, `destination_name`, `destination_latitude`, `destination_longitude`, `destination_geo_fence_radius_meters` | | Snapshot |
| `consignee_tenant_id` | uuid | FK `tenants` |
| `carrier_tenant_id` | uuid | FK `tenants` |
| `assigned_driver_id` | uuid | nullable FK `users` |
| `status` | text | `CREATED`, `IN_TRANSIT`, `DELIVERED`, `CANCELLED`, `RECALLED` |
| `picked_up_at`, `delivered_at`, `cancelled_at`, `recalled_at` | timestamptz | nullable |
| `created_by` | uuid | FK `users` |
| `created_at`, `updated_at` | timestamptz | |

Indexes: `(owner_tenant_id, created_at)`, `(lot_id)`, `(status)`, `(assigned_driver_id)`.

**`shipment_participants`** (RLS: participants of the same shipment)

| Column | Type | Notes |
| --- | --- | --- |
| `shipment_id` | uuid | FK; PK part |
| `tenant_id` | uuid | FK; PK part; indexed `(tenant_id, shipment_id)` |
| `role` | text | PK part; `OWNER`, `CARRIER`, `CONSIGNEE`, `INSPECTOR` |
| `created_at` | timestamptz | |

**`pickup_codes`** (RLS: participants)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid | PK |
| `shipment_id` | uuid | FK; at most one active code per shipment (partial unique index) |
| `code_hash` | bytea | `HMAC-SHA256(pepper, shipment_id ‖ code)` |
| `expires_at` | timestamptz | issue time + 15 min |
| `failed_attempts` | smallint | locked at 5 |
| `consumed_at`, `invalidated_at` | timestamptz | nullable |
| `issued_by` | uuid | FK `users` |
| `created_at` | timestamptz | |

**`shipment_events`** (RLS: participants; append-only, no UPDATE or DELETE grant)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid | PK; equals the Kafka `event_id` |
| `shipment_id` | uuid | FK |
| `sequence` | integer | unique with `shipment_id`; starts at 1 |
| `event_type` | text | see [shipment-lifecycle.md §9](../domain/shipment-lifecycle.md#9-shipment-event-log) |
| `event_version` | smallint | payload schema version |
| `status` | text | shipment status after the event |
| `actor_tenant_id`, `actor_user_id` | uuid | FK |
| `occurred_at` | timestamptz | |
| `data` | jsonb | event payload |
| `prev_event_hash` | char(64) | 64 zeros for sequence 1 |
| `event_hash` | char(64) | unique |

**`recalls`** (RLS: tenant)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid | PK |
| `tenant_id` | uuid | FK; lot owner |
| `lot_id` | uuid | FK; unique (a lot is recalled at most once) |
| `reason` | text | 1–1000 characters |
| `affected_shipment_count` | integer | |
| `initiated_by` | uuid | FK `users` |
| `created_at` | timestamptz | |

**`outbox`** (no RLS; internal, never exposed through the API)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | bigint | identity PK; publication order |
| `topic` | text | |
| `message_key` | text | |
| `payload` | jsonb | |
| `headers` | jsonb | includes `traceparent` |
| `created_at` | timestamptz | |
| `published_at` | timestamptz | nullable; rows are deleted 7 days after publication |

### 3.4 Documents and labels (M2)

**`documents`** (RLS: participants of the shipment)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid | PK |
| `shipment_id` | uuid | FK |
| `uploader_tenant_id`, `uploaded_by` | uuid | FK |
| `document_type` | text | `CERTIFICATE_OF_ORIGIN`, `CERTIFICATE_OF_QUALITY`, `INSPECTION_REPORT`, `INVOICE` |
| `file_name` | text | sanitized, ≤ 255 characters |
| `content_type` | text | `application/pdf`, `image/png`, `image/jpeg` |
| `plaintext_size_bytes` | bigint | ≤ 25 MiB |
| `plaintext_sha256` | char(64) | |
| `ciphertext_cid` | text | IPFS CID (v1) |
| `ciphertext_size_bytes` | bigint | |
| `encryption_scheme` | text | `VTENC1` ([ADR-0013](../adr/0013-document-vault-encryption.md)) |
| `wrapped_data_key` | bytea | Data key encrypted with the master key |
| `master_key_id` | text | Identifies the master key version |
| `created_at` | timestamptz | |

**`label_signing_keys`** (RLS: tenant)

| Column | Type | Notes |
| --- | --- | --- |
| `tenant_id` | uuid | PK part |
| `version` | smallint | PK part |
| `wrapped_key` | bytea | 32-byte HMAC key wrapped with the master key |
| `master_key_id` | text | |
| `created_at`, `retired_at` | timestamptz | |

**`label_series`** (RLS: tenant)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid | PK |
| `tenant_id`, `lot_id` | uuid | FK |
| `first_serial` | bigint | ≥ 1; series do not overlap within a lot |
| `label_count` | integer | 1–100 000 |
| `key_version` | smallint | |
| `created_by` | uuid | FK `users` |
| `created_at` | timestamptz | |

**`trace_scans`** (RLS: the lot owner tenant; written through a public `SECURITY DEFINER` function)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid | PK |
| `tenant_id`, `lot_id` | uuid | nullable when the verdict is `UNKNOWN` |
| `gtin`, `lot_number`, `serial` | text | as scanned |
| `verdict` | text | `GENUINE`, `FORGED`, `SUSPICIOUS_DUPLICATE`, `RECALLED`, `UNKNOWN` |
| `latitude`, `longitude` | numeric(9,6) | nullable; rounded to 2 decimals before storage |
| `client_fingerprint` | bytea | salted SHA-256 of IP and user agent |
| `scanned_at` | timestamptz | |

### 3.5 Security-definer functions

| Function | Used by | Returns |
| --- | --- | --- |
| `core.current_tenant_id()` | every RLS policy | the tenant from `app.current_tenant_id`, or `NULL` (fail closed) |
| `core.is_shipment_participant(shipment_id)` | shipment RLS policies | boolean |
| `core.is_lot_visible(lot_id)` | lot RLS policy | boolean |
| `core.register_tenant(...)` | registration | new tenant, admin user, and headquarters IDs |
| `core.find_login_user(email)` | login | user ID, tenant ID, password hash, role, active flag |
| `core.find_auth_session(token_hash)` | token refresh | session and user, for rotation |
| `core.lookup_location_by_gln(gln)` | GLN directory | public location fields and owner tenant |
| `core.lookup_tenant_by_code(code)` | carrier or inspector lookup | ID, code, legal name |
| `core.recall_lot(lot_id, reason, user_id)` | recall | recall ID, affected shipments (runs across tenants) |
| `core.public_*` (M2) | public trace API | public projections only |

Every such function sets `search_path` explicitly. `EXECUTE` is revoked from `PUBLIC` and granted to the
runtime role only.

---

## 4. Telemetry database (`veritrace_telemetry`, schema `telemetry`)

Authorization is enforced in the application from the shipment projection (participants). The telemetry
database has no tenant-scoped RLS, because every row is keyed by SSCC and every read path checks
participation first.

**`sensor_readings`** (TimescaleDB hypertable on `recorded_at`, 1-day chunks)

| Column | Type | Notes |
| --- | --- | --- |
| `recorded_at` | timestamptz | device time |
| `sscc` | char(18) | |
| `device_id` | text | `^[A-Za-z0-9_-]{1,64}$` |
| `temperature_celsius` | numeric(5,2) | |
| `humidity_percent` | numeric(5,2) | nullable |
| `latitude`, `longitude` | numeric(9,6) | |
| `received_at` | timestamptz | |

- Unique `(sscc, device_id, recorded_at)`, which also makes inserts idempotent.
- Index `(sscc, recorded_at DESC)`.
- Compression after 7 days, segmented by `sscc`.
- A continuous aggregate `sensor_readings_15m` (avg, min, and max per SSCC per 15 minutes) serves charts
  and the public timeline.

**`shipment_projection`**

| Column | Type | Notes |
| --- | --- | --- |
| `sscc` | char(18) | PK |
| `shipment_id` | uuid | unique |
| `owner_tenant_id` | uuid | |
| `participant_tenant_ids` | uuid[] | GIN index |
| `assigned_driver_id` | uuid | nullable |
| `status` | text | |
| `gtin`, `product_name`, `lot_number` | text | |
| `min_temp_celsius`, `max_temp_celsius` | numeric(5,2) | |
| `last_event_sequence` | integer | makes projection updates idempotent |
| `updated_at` | timestamptz | |

**`cold_chain_incidents`**

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid | PK |
| `sscc` | char(18) | unique with `started_at` |
| `shipment_id` | uuid | |
| `device_id` | text | |
| `started_at`, `confirmed_at` | timestamptz | |
| `ended_at` | timestamptz | nullable while ongoing |
| `min_temp_celsius`, `max_temp_celsius` | numeric(5,2) | bounds in force |
| `trigger_temperature_celsius` | numeric(5,2) | reading that confirmed the breach |
| `extreme_temperature_celsius` | numeric(5,2) | furthest from bounds so far |
| `latitude`, `longitude` | numeric(9,6) | at confirmation |
| `duration_seconds` | integer | nullable until resolved |
| `incident_hash` | char(64) | unique; covers the confirmation fields only |
| `created_at`, `updated_at` | timestamptz | |

---

## 5. Relayer database (`veritrace_relayer`, schema `relayer`, M2)

**`leaves`**

| Column | Type | Notes |
| --- | --- | --- |
| `leaf_hash` | char(64) | PK; a shipment `event_hash` or an `incident_hash` |
| `source` | text | `SHIPMENT_EVENT`, `COLD_CHAIN_INCIDENT` |
| `source_id` | uuid | |
| `sscc` | char(18) | |
| `is_priority` | boolean | recall events |
| `batch_id` | bigint | nullable FK |
| `leaf_index` | integer | nullable |
| `proof` | text[] | nullable; hex sibling hashes |
| `received_at` | timestamptz | |

**`batches`**

| Column | Type | Notes |
| --- | --- | --- |
| `id` | bigint | PK; equals the on-chain `batchId` (sequential from 1) |
| `merkle_root` | char(64) | |
| `leaf_count` | integer | |
| `manifest_cid` | text | IPFS CID of the batch manifest |
| `status` | text | `BUILT`, `SUBMITTED`, `CONFIRMED`, `FAILED` |
| `tx_hash` | char(64) | nullable; of the mined transaction |
| `block_number` | bigint | nullable |
| `created_at`, `confirmed_at` | timestamptz | |

**`chain_transactions`**

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid | PK |
| `batch_id` | bigint | FK |
| `nonce` | bigint | |
| `tx_hash` | char(64) | unique |
| `max_fee_per_gas_wei`, `max_priority_fee_per_gas_wei` | numeric(78,0) | |
| `status` | text | `PENDING`, `REPLACED`, `MINED`, `FAILED` |
| `sent_at`, `mined_at` | timestamptz | |
| `gas_used` | bigint | nullable |

**`chain_cursors`**

| Column | Type | Notes |
| --- | --- | --- |
| `name` | text | PK (for example `commitment-indexer`) |
| `last_block_number` | bigint | |
| `updated_at` | timestamptz | |
