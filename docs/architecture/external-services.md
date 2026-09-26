# External Services and Cost Register

Every third-party service VeriTrace depends on, with the plan used, the limits that matter, how the
platform stays within them, and the $0 fallback. Policy: [ADR-0018](../adr/0018-deployment-topology.md).
Figures were verified in September 2026 and must be re-checked before M2 deployment.

## 1. Summary

| Milestone | Expected monthly cost |
| --- | --- |
| M1 — Operational Core | **$0**: local mode (Docker Compose), with an optional Cloudflare quick tunnel |
| M2 — Decentralized Trust | **$0**: local mode is always available. Optional cloud mode on Oracle Always Free is also $0; about €4–8 per month only if the paid VPS fallback is ever needed |

## 2. Inventory

| Service | Used for | Milestone | Plan | Limits that matter | How we stay within | $0 fallback |
| --- | --- | --- | --- | --- | --- | --- |
| GitHub (repos, Actions, GHCR) | Source, CI, container images | M1+ | Free for public repositories | — | Public repositories | — |
| Cloudflare quick tunnel | Temporary HTTPS URL for phones and demos | M1+ | Free, no account | Random URL per start; no uptime guarantee | Used for testing and demos only, never in printed labels | ngrok free |
| Backend host (cloud mode only) | Compose stack in M2 | M2 | Oracle Always Free A1 | 2 OCPU, 12 GB RAM, 200 GB storage; idle reclamation | Stack keeps memory above 20%; backups off-host | Azure credit offer, then workstation + tunnel |
| Vercel (cloud mode only) | Dashboard, driver PWA, public portal | M2 | Hobby (free, non-commercial) | Fair-use bandwidth and build limits | Three small projects; no media hosting | Cloudflare Pages |
| DNS name for the backend (cloud mode only) | TLS certificate for the API on the VM | M2 | DuckDNS or sslip.io (free) | Community services | Caddy automatic HTTPS | Custom domain (~$10–15 per year, optional) |
| Let's Encrypt | TLS certificates | M2 | Free | Issuance rate limits | Caddy reuses certificates across restarts (persistent volume) | — |
| Polygon Amoy testnet | On-chain commitments | M2 | Free test POL from faucets | About 0.1–0.5 POL per day per faucet | ≈0.002–0.003 POL per `commitBatch`; batches are sealed only when leaves are pending, at most every 10 minutes; development uses a local Anvil chain | Several faucets (Alchemy, QuickNode, Chainlink) |
| RPC provider | Chain reads, writes, subscriptions | M2 | Alchemy free tier, or the public Amoy RPC | Request quotas | One relayer, low volume, indexer backfills in pages | Public RPC `rpc-amoy.polygon.technology` |
| Polygonscan / Etherscan API | Contract source verification | M2 | Free API key | Rate limit | One-time verification per deployment | Manual verification on the explorer |
| IPFS | Encrypted documents, batch manifests | M2 | Self-hosted Kubo node on the backend host | Host disk | Documents ≤ 25 MiB; manifests are small JSON | — |
| Pinata | Optional remote pinning of document CIDs | M2 | Free: 1 GB storage, 500 files | 500-file cap | Only document CIDs are remote-pinned (never manifests), through Kubo's remote pinning; disabled by default | None needed: Kubo is primary |
| Grafana stack | Metrics, logs, dashboards | M2 | Self-hosted (Prometheus, Loki, Alloy, Grafana) | Host RAM (~0.7 GB) | Short retention (7 days) | — |

## 3. Rules

- Do not introduce a service that needs a paid plan, or a card-backed trial that auto-converts to
  paid, without an ADR.
- Secrets and credentials for these services live only in environment files on the host or in CI
  secrets.
- When a free tier changes, update this table in the same change as any configuration adjustment.
