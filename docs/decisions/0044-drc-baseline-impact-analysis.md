# ADR 0044: DRC baseline impact analysis

## Status

Accepted.

## Context

ADR 0012 requires capital packages to preserve stable ids, branch metadata, and
reconciliation hooks for later impact analysis. ADR 0031 separates DRC
analytical attribution from baseline-vs-candidate impact, and ADR 0038 defines
the suite-wide `CapitalImpact` type for cross-run capital deltas.

`frtb-drc` now emits attribution records on capital results, but clients also
need a public API that explains how a candidate DRC result differs from a
baseline result without presenting that explanation as regulatory capital or
analytical Euler contribution.

## Decision

`frtb-drc` exposes `calculate_drc_impact(baseline, candidate)` and
`validate_drc_impact_reconciliation` from the package top level.

The API returns `DrcImpactAnalysis`, which contains:

- one suite-wide `CapitalImpact` total with `delta = candidate - baseline`;
- DRC-specific `DrcImpactRecord` records for stable bucket branches, profile
  changes, position moves, category moves, floor branches, and unsupported
  branches;
- an explicit residual amount and reconciliation status.

Stable bucket branches may emit `DrcImpactMethod.FINITE_DIFFERENCE` records.
Profile changes, bucket/category moves, floors, zero denominators, rejected
offsets, and unsupported feature branches emit `UNSUPPORTED` records. Any
capital delta not explained by finite-difference records is carried by a
`RESIDUAL` record so the impact record set reconciles to the total delta.

Impact generation must not mutate either input result or change DRC capital
totals. Impact records are explainability and change-control artifacts, not
regulatory capital calculations and not marginal contributions.

## Consequences

Clients get a package-owned change-analysis API that preserves DRC branch
metadata and uses the shared suite impact contract.

The public API surface grows by five symbols:
`calculate_drc_impact`, `validate_drc_impact_reconciliation`,
`DrcImpactAnalysis`, `DrcImpactRecord`, and `DrcImpactMethod`.

Future branch-specific decomposition can refine unsupported or residual
records, but must continue to preserve the capital totals and reconciliation
invariant.
