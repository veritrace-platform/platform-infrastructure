# Engineering Workflow

## 1. Branches

| Branch | Purpose | Merges from |
| --- | --- | --- |
| `main` | Released code only. Every commit on `main` is tagged. | `develop` (release PR) |
| `develop` | Integration branch; always builds and passes CI | Work branches |
| `feat/<id>-<slug>` | New behavior, for example `feat/scm-ep1-us03-tenant-isolation` | — |
| `fix/<slug>` | Bug fix | — |
| `docs/<slug>`, `chore/<slug>`, `refactor/<slug>`, `test/<slug>`, `ci/<slug>` | Non-functional changes | — |

- Work branches start from `develop` and return to it through a pull request.
- `main` and `develop` are protected: no direct pushes, and CI must pass.

## 2. Commits

The format is [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <imperative summary, lower case, no period, ≤ 72 chars>

<optional body: what and why, wrapped at 72>

<optional footer: Refs: SCM-EP2-US05 / BREAKING CHANGE: …>
```

- **Types:** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`, `build`, `perf`.
- **Scopes:** a domain or area of the repository, such as `auth`, `tenancy`, `gs1`, `shipments`,
  `handover`, `recall`, `ingest`, `detector`, `ws`, `relayer`, `compose`, `docs`.
- One logical change per commit, and the build passes at every commit.

## 3. Pull requests

- Keep each pull request to one story, or one coherent slice of a story. It should be reviewable in about
  30 minutes.
- The description states what changed, how it was verified, and which story it references (template
  provided organization-wide).
- Pull requests are merged by **squash**, and the pull request title becomes the commit message. For that
  reason the title follows the commit format.
- A change that touches a contract (migration, OpenAPI, messaging document, ADR) updates it in the same
  pull request. A cross-repository contract change links the counterpart pull request.

## 4. Definition of Done

A story is done when all of the following hold:

1. **Behavior** matches the domain documents and the OpenAPI or messaging contracts.
2. **Tests:**
   - unit tests cover domain logic and edge cases (≥ 80% of statements in domain packages);
   - integration tests cover persistence, RLS isolation, and messaging paths.
3. **Quality:** `make lint test` passes locally and CI is green.
4. **Security:**
   - no secrets in code or logs;
   - tenant isolation goes through the transaction helper;
   - authorization goes through the policy.
5. **Docs:** contracts, ADRs (if a decision changed), and the [roadmap](../roadmap.md) status are updated.

## 5. Releases and versioning

- Each repository follows [Semantic Versioning](https://semver.org/). Tags are `vMAJOR.MINOR.PATCH` on
  `main`.
- Development before the first release uses `0.y.z`. Completion of **M1 — Operational Core** is released
  as `v1.0.0` in each participating repository.
- Release notes are published as GitHub Releases and grouped by commit type.
