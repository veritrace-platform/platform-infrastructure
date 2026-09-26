# ADR-0018: Deployment topology and cost

- **Status:** Accepted
- **Date:** 2026-09-26

## Context

VeriTrace must run with **no guaranteed budget**. The target is $0 per month, with any paid option
bounded and optional. It is not yet known whether M2 will be demonstrated from a workstation or from a
public deployment, so both must be possible without redesign.

| Milestone | What must be reachable |
| --- | --- |
| M1 — Operational Core | Dashboard and driver PWA on a workstation. Phones need an HTTPS URL, because camera and geolocation APIs only work in secure contexts. |
| M2 — Decentralized Trust | Everything in M1, plus the public trace portal (scanned from a phone), on-chain proofs, the IPFS vault, and observability |

**Measured footprint:**

- The M1 backend (PostgreSQL + TimescaleDB, Kafka, Mosquitto, Redis, gateway, two Go services) uses about
  **0.6 GB of RAM** at idle.
- With the M2 additions (relayer, IPFS node, Prometheus, Loki, Alloy, Grafana), the estimate is
  **1.6–2 GB**.
- A 4 GB host is enough, and 8 GB or more is comfortable.

**Hosting options evaluated** (facts verified in September 2026; free tiers change, so re-check before
committing):

| Option | Monthly cost | Fit | Main risks |
| --- | --- | --- | --- |
| Render (original plan) | Free instances: 512 MB, sleep after 15 min, no persistent disk | ❌ Kafka, MQTT, and TimescaleDB cannot run on free instances | Paid services with disks are needed for each component; sleeping breaks MQTT and WebSocket |
| Managed free tiers per component | $0 at first | ❌ No free managed Kafka or TimescaleDB that fits; five vendors mean five sets of limits and expiries | Fragile and not reproducible |
| **Oracle Cloud Always Free, Ampere A1** | **$0** permanently: 2 OCPU (Arm) + 12 GB RAM, 200 GB block storage, home region | ✅ Runs the whole stack with headroom | Card needed for identity verification; A1 capacity may be unavailable in some regions; idle instances can be reclaimed (7 days below 20% CPU, network, **and** memory; the stack keeps memory above 20%); Arm64 images required |
| Azure credit offer | $0: a $100 credit valid for 12 months, no card required | ⚠️ A 4 GB burstable VM costs about $30–40 per month at list price, so the credit covers about **3 months**. The always-free B1s (1 GB) is too small. | The deployment window must be planned |
| AWS Free plan | $0: $100–200 credits for 6 months; card required | ⚠️ Covers a small 4 GB instance for 6 months | The account plan expires after 6 months |
| Workstation + Cloudflare quick tunnel | $0 | ✅ Demonstrations and phone testing | The URL changes on every start; the host must stay on |
| Small paid VPS (2–4 vCPU / 4–8 GB) | about €4–8 | ✅ Simple and predictable | Recurring cost |

## Decision

1. **One topology, two run modes.** The same compose topology (base file plus profiles) runs in both
   modes. Services are configured only through environment variables, so switching modes never changes
   code.

   | | **Local mode** (guaranteed for M1 and M2) | **Cloud mode** (optional for M2) |
   | --- | --- | --- |
   | Backend | Workstation, Docker Compose | One VM, the same compose files plus production overrides |
   | Frontends | Run on the workstation | Vercel Hobby (free) |
   | Public HTTPS URL | `tunnel` profile (Cloudflare quick tunnel, temporary URL) | Caddy with Let's Encrypt, on a free DNS name (DuckDNS or sslip.io) |
   | Chain | Polygon Amoy (real explorer links; needs internet and faucet POL), or local Anvil when offline | Polygon Amoy |
   | IPFS | Local Kubo node (`web3` profile) | Kubo node on the VM |
   | Observability | `observability` profile | Same profile on the VM |
   | Cost | $0 | $0 with the host below |

2. **Labels follow the run mode.** Consumer labels embed `PUBLIC_TRACE_BASE_URL`.
   - In local mode, the base URL is the tunnel URL of that session, and labels are generated and shown on
     screen during the demonstration. They are not pre-printed.
   - In cloud mode, the base URL is the stable portal URL, and labels may be printed.
3. **Cloud host, if cloud mode is used:**
   - **Oracle Cloud Always Free A1** (2 OCPU, 12 GB, $0).
   - Fallbacks, in order: the Azure credit offer (deploy only for the final ~3 months of M2), then a small
     paid VPS (about €4–8 per month).
4. **Multi-architecture images.** Release pipelines build `linux/amd64` and `linux/arm64` images, pushed
   to GitHub Container Registry (free for public repositories). Every host option works, including Arm.
5. **Every external dependency must have a $0 path.** The inventory, limits, and fallbacks are in
   [external-services.md](../architecture/external-services.md). A dependency without a $0 path needs a
   new ADR.

## Consequences

- M2 can be demonstrated entirely from a workstation at no cost. Cloud deployment is an additive step
  (SCM-EP7-US04), not a prerequisite.
- In cloud mode the single VM is a single point of failure. That is acceptable and explicit. The host is
  reproducible from this repository (compose plus backups) and can be rebuilt on a fallback within hours.
- Free-tier terms can change. [external-services.md](../architecture/external-services.md) is reviewed
  at the start of M2 and again before any deployment.
