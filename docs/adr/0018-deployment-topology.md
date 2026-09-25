# ADR-0018: Deployment topology (M2)

- **Status:** Accepted
- **Date:** 2026-09-25

## Context

The initial plan targeted Vercel for the frontends and Render for the Go services and the database.
The backend needs Kafka, Mosquitto, Redis, and PostgreSQL with TimescaleDB:

- Render offers none of Kafka, Mosquitto, or the TimescaleDB extension as managed services.
- Self-hosting them on Render requires paid private services with disks.
- Free instances sleep, which breaks the MQTT, Kafka, and WebSocket workloads.

Splitting across several managed vendors, each with its own free-tier limits, multiplies the moving parts.

## Decision

- **Frontends on Vercel**: `enterprise-dashboard`, `driver-mobile-pwa`, and `public-trace-portal`, each
  from its own repository.
- **Backend on a single Linux VM** (4 vCPU, 8 GB RAM class) running the **same Docker Compose topology**
  as local development, with production overrides:
  - **Caddy** as the edge gateway, with automatic HTTPS, the routing table from
    [rest-api.md §2](../contracts/rest-api.md#2-gateway-routing), and WebSocket upgrade;
  - MQTT exposed on 8883 with TLS;
  - persistent named volumes, daily PostgreSQL dumps shipped off the VM, and resource limits per
    container.
- **Images:** each Go service publishes multi-stage, distroless, non-root images to GitHub Container
  Registry, tagged with the git SHA and the release version.
- **CD:**
  1. A release tag builds and pushes the images.
  2. A deploy workflow connects to the VM over SSH with a scoped deploy key, pulls the images, runs
     migrations, and restarts services.
- **Domains:** `app.<domain>` (dashboard), `driver.<domain>` (PWA), `trace.<domain>` (public portal),
  `api.<domain>` (gateway), `mqtt.<domain>` (broker).

## Consequences

- Production matches development, and the whole backend can be reproduced from one repository.
- The single VM is a single point of failure. That is acceptable for this deployment's scale and made
  explicit, and the compose files do not prevent moving components to managed services later.
- A small recurring VM cost replaces a set of free tiers that would not have met the workload.
