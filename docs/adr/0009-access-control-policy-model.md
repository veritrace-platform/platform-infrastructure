# ADR-0009: Access control policy model

- **Status:** Accepted
- **Date:** 2026-09-25

## Context

The initial concept stated one global rule:

```
AllowAccess ⇔ (User.TenantID = Resource.TenantID) ∧ (Context.InGeoFence) ∧ (Shipment.Status = IN_TRANSIT)
```

This rule has three problems:

1. It applies one condition to every action. Creating a shipment or reading a catalog would require an
   in-transit shipment and a geo-fence.
2. Requiring the same tenant contradicts the multi-party model (ADR-0002). Carriers and consignees act on
   shipments owned by another tenant.
3. Device GPS is client-reported and can be spoofed. Alone, it is evidence rather than proof.

## Decision

Authorization is evaluated **per action**:

```
Allow(user, action, resource, ctx) ⇔
      Party(user.tenant, resource) ∈ PartiesAllowed(action)
    ∧ user.role ∈ RolesAllowed(action)
    ∧ StatePrecondition(action, resource)
    ∧ ContextConstraint(action, ctx)
```

- **Party** is the relationship between the caller's tenant and the resource:
  - `OWNER`, `CARRIER`, `CONSIGNEE`, or `INSPECTOR` for shipments;
  - own tenant for master data;
  - lot owner or lot holder for lots.
- **StatePrecondition** follows the state machine
  ([shipment-lifecycle.md](../domain/shipment-lifecycle.md)).
- **ContextConstraint** covers action-specific checks:
  - a scanned SSCC match;
  - a pickup code;
  - a geo-fence: `haversine(device, facility) ≤ radius + min(accuracy, 50 m)`.

The original rule is preserved as one row of the matrix, *Record checkpoint*: same party (carrier),
inside a geo-fence, while `IN_TRANSIT`. The full matrix is in
[access-control.md](../domain/access-control.md).

Implementation:

- The policy is a table-driven, pure Go function with exhaustive unit tests. The service layer calls it
  before every state change. Any action without an entry is denied.
- RLS remains the outer boundary: the policy decides what a user may *do* with rows they can already
  *see*.
- Positions and accuracy submitted with geo-fenced actions are recorded in the event payload.

## Consequences

- Each action states its own conditions, and they are testable in isolation.
- A policy engine (OPA, Casbin) is unnecessary at this scale. The function can be replaced if runtime
  policy editing is ever needed.
- Geo-fencing raises the cost of fraud but cannot stop a spoofed device. The pickup code and the audit
  trail compensate for that.
