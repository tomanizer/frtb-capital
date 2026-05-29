# AGENTS.md — frtb-capital suite

Guidance for Codex and other coding agents working in this workspace. Package-specific briefs live under each package (e.g. [`packages/frtb-ima/AGENTS.md`](packages/frtb-ima/AGENTS.md)).

## Project identity

This is a `uv` workspace containing a suite of FRTB market-risk capital calculation packages. Each package implements one capital component (IMA, SBM, DRC, RRAO, CVA) plus a shared `frtb-common` library and a suite-level orchestration layer. SA is the composed Standardised Approach total from SBM, DRC, and RRAO, not a standalone package.

The goal is a transparent, testable prototype suite that demonstrates how an existing risk engine could generate scenario P&L, sensitivity, default-risk, residual-risk, and credit exposure inputs that an ex-post capital layer assembles into IMA, SA component stack, CVA, and top-of-the-house aggregate capital.

## Scope

- **In scope:** IMA, SBM, DRC, RRAO, CVA capital calculation; SA composition in orchestration; suite-level aggregation; shared abstractions.
- **Out of scope:** market data sourcing, pricing engines, regulatory submission packaging, firm-level financial reporting (beyond capital aggregation).

## Regulatory caution

All U.S. NPR 2.0 / Basel FRTB / EU CRR3 / PRA UK CRR content is proposed-rule or comparison material. Do not present outputs as final regulatory capital. Cite specific regulatory paragraphs, not framework names.

## Coding style

- Python 3.11+ across all packages.
- Prefer dataclasses, enums, pure functions.
- `numpy` is the default runtime numerical dependency for capital calculation
  kernels. Adding any other runtime dependency requires an ADR. `pandas`,
  `polars`, `scipy`, and `statsmodels` may be used in notebooks, validation,
  tests, research, or optional adapters when they do not leak into the core
  runtime path; see [`ADR 0011`](docs/decisions/0011-core-runtime-dependency-policy.md).
- Add unit tests for every calculation.
- Synthetic data only; no proprietary market data.
- Favour clarity over cleverness.
- Cite regulatory paragraphs explicitly; do NOT use phrases like "working assumption" or "prototype" as a substitute for citation.
- Preserve attribution readiness for every capital component: stable ids,
  deterministic grouping, intermediate audit records, and branch metadata must
  make later analytical Euler or impact analysis possible without changing the
  capital number. See [`ADR 0012`](docs/decisions/0012-capital-impact-attribution.md).

## Workspace discipline

- **No sibling imports between capital packages.** `frtb-ima` must not import from `frtb-sbm`, `frtb-drc`, `frtb-rrao`, `frtb-cva`, etc. Shared types go in `frtb-common`.
- **One package per PR** unless the change is genuinely cross-cutting (regulatory definition change, shared type update). Cross-cutting PRs must reference an ADR.
- **Per-package versioning.** Bump only the affected package's version.
- **Material changes need ADRs.** See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Review focus

When reviewing or changing code, focus on:

- Package boundary discipline (no sibling imports).
- Consistency of style across packages.
- Regulatory citations in place of "working assumption" language.
- Correct scenario-vector granularity in IMA, correct bucket aggregation in SBM, correct issuer aggregation in DRC, correct residual-risk classification in RRAO, correct exposure-at-default treatment in CVA.
- Deterministic tests; no random seeds without fixing them.
- Frozen dataclasses for audit-grade results.
- Explicit `UnsupportedRegulatoryFeatureError` where a regime is not implemented; never silent computation.
- Audit-record compatibility for any new result that contributes to capital.
- Attribution/impact compatibility for any new capital aggregation branch,
  including explicit residual or unsupported-method behavior where exact Euler
  decomposition is not valid.
