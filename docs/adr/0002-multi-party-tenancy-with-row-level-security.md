# ADR-0002: Multi-party tenancy with row-level security

- **Status:** Accepted
- **Date:** 2026-09-25

## Context

Each company (tenant) must be isolated from the others. Yet one flow of goods involves several companies:

- the **owner** that dispatches a shipment;
- the **carrier** whose driver collects it (possibly the owner's own fleet);
- the **consignee** that receives it;
- in multi-hop distribution, the next tenant that ships the same lot onward.

A recall must reach every tenant that holds affected goods. A strict "row belongs to one tenant" model
cannot express this, and opening shared tables without isolation defeats multi-tenancy.

## Decision

1. **Master data is single-tenant.** `users`, `locations`, `products`, and `inventory_*` carry
   `tenant_id`, with the RLS policy `tenant_id = core.current_tenant_id()`.
2. **GS1 keys are globally unique and prefix-bound.**
   - GS1 assigns a GLN or GTIN to exactly one company.
   - Keys are unique across tenants and must start with the tenant's company prefix.
   - A tenant therefore cannot register another company's keys, and a uniqueness conflict reveals nothing
     that the prefix rule does not already reject.
3. **Shipments are shared through participants.**
   - `shipment_participants (shipment_id, tenant_id, role)` holds the roles `OWNER`, `CARRIER`,
     `CONSIGNEE`, and (M2) `INSPECTOR`.
   - Shipments and their child rows (participants, pickup codes, events, documents) are visible if and
     only if `core.is_shipment_participant(shipment_id)` is true.
   - That is a `SECURITY DEFINER` helper, which avoids recursive policies.
4. **Lots are visible to their owner and their holders.** A holder is a tenant that has, or had, an
   inventory balance of the lot. Holders need this to ship received goods onward
   (`core.is_lot_visible(lot_id)`).
5. **Snapshots instead of cross-tenant reads.** Shipments copy the product fields (GTIN, name,
   temperature bounds), lot fields, and origin and destination facility fields when they are created.
   Participants never read another tenant's catalog, and the record preserves what applied at the time.
6. **Transaction-scoped tenant context.**
   - Every tenant-scoped transaction starts with
     `SELECT set_config('app.current_tenant_id', $1, true)`.
   - `core.current_tenant_id()` reads the setting and returns `NULL` when it is missing or empty.
     `NULL` never equals anything, so policies fail closed.
7. **Least-privilege roles.**
   - Migrations run as `veritrace_core_owner`.
   - The runtime role `veritrace_core_app` owns nothing, has `NOBYPASSRLS`, and receives only
     `SELECT, INSERT, UPDATE, DELETE`. It never receives `TRUNCATE`, which bypasses RLS.
   - Append-only tables (`shipment_events`, `inventory_movements`) do not grant `UPDATE` or `DELETE`.
8. **Controlled cross-tenant operations.** These run through narrow `SECURITY DEFINER` functions with a
   fixed `search_path` and explicit `EXECUTE` grants, and return only the minimum fields:
   - pre-authentication operations (registration, login, refresh);
   - directory lookups (GLN, tenant code);
   - the cross-tenant recall cascade;
   - M2 public projections.

   The full list is in [data-model.md §3.5](../architecture/data-model.md#35-security-definer-functions).

## Consequences

- Cross-company workflows (handover, delivery, multi-hop distribution, recall broadcast, and in M2 audit
  and public trace) work without leaking data.
- Shipment policies depend on the participant lookup, so `(tenant_id, shipment_id)` must be indexed.
- `SECURITY DEFINER` functions are the privileged surface. Each one gets dedicated isolation tests.
- Isolation is verified by integration tests that connect as `veritrace_core_app` to a real
  PostgreSQL instance and assert that other tenants' rows are invisible and immutable.
