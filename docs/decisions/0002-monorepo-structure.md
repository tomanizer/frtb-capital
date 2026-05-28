# 2. Monorepo structure for the FRTB capital suite

Date: 2026-05-28

## Status

Accepted

## Context

The FRTB capital suite consists of four primary capital components — Internal Models Approach (IMA), Standardized Approach (SA), Default Risk Charge (DRC), Credit Valuation Adjustment (CVA) — plus a suite-level orchestration layer that aggregates them into firm-level capital.

Each component is, under SR 11-7 / PRA SS 1/23, a distinct model requiring its own documentation pack, validation evidence, and ongoing monitoring. But they share enough common plumbing (regulatory policy framework, audit records, scenario metadata, sign conventions, business calendar) that maintaining four separate repositories would cause:

- Style and assumption drift across components.
- Non-atomic cross-cutting regulatory changes.
- Duplicate copies of shared abstractions.
- Fragmented AI-agent context (Codex working on SA cannot see IMA's solution to the same problem).
- Awkward orchestration via internal package indexing or git-SHA pins.

Conversely, putting everything in a single flat package would lose the per-model boundary that SR 11-7 expects.

## Decision

Adopt a **monorepo with multiple packages**, structured as a `uv` workspace:

```
frtb-capital/
├── packages/
│   ├── frtb-common/         # shared primitives
│   ├── frtb-ima/            # Internal Models Approach
│   ├── frtb-sa/             # Standardized Approach
│   ├── frtb-drc/            # Default Risk Charge
│   ├── frtb-cva/            # Credit Valuation Adjustment
│   └── frtb-orchestration/  # suite-level aggregation
└── ...
```

Each package has its own `pyproject.toml`, version, tests, and model documentation pack. Sibling capital packages must not import from each other. Shared types live in `frtb-common`. The orchestration package is the only one allowed to import from multiple capital components.

Package boundaries will be enforced by `importlinter` (to be added).

## Consequences

**Positive:**

- Consistent style and conventions enforced structurally.
- Shared abstractions live in one place; no copy-paste drift.
- Cross-cutting regulatory changes are atomic PRs.
- AI agents have full suite context.
- Per-package versioning preserves SR 11-7 model boundaries.
- Per-package model documentation packs remain independently reviewable.

**Negative:**

- One-way door: moving back to polyrepo is expensive.
- Discipline required to maintain package boundaries; needs tooling enforcement.
- Larger repository; CI must be configured for per-package paths to avoid running everything on every change.

## Alternatives considered

1. **Polyrepo with a meta-repo.** Each component in its own GitHub repo, an orchestration repo depending on the others via PyPI or git pins. Rejected because the drift risk and cross-cutting change friction dominate; the independence-of-ownership benefit does not apply (one team owns the suite).

2. **Single flat package.** All capital code in one Python package. Rejected because it loses the per-model SR 11-7 boundary and complicates versioning.

## References

- Path-to-production audit: `tomanizer/frtb-capital` issue #1
  (transferred from `tomanizer/FRTB-IMA` issue #31).
- `docs/ARCHITECTURE.md`.
