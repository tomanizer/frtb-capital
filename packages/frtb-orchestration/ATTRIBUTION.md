# Capital Attribution

`frtb-orchestration` owns suite-level aggregation of package contribution
bundles. It does not recalculate component attribution and does not reach into
private component internals.

## Current Support

Public helper:

```python
from frtb_orchestration import (
    aggregate_suite_attribution,
    build_suite_attribution_report,
    summarise_suite_attribution,
)
```

`aggregate_suite_attribution(suite_result=..., component_bundles=...)` returns a
`SuiteAttributionResult` that preserves incoming
`frtb_common.ComponentContributionBundle` objects unchanged and adds one
suite-level residual record.

`build_suite_attribution_report(suite_result=..., component_bundles=...)` wraps
the same validation and residual construction in a client-facing
`SuiteAttributionReport`. The report exposes a canonical component set,
component sections, reconciliation status, residual reason, and a
JSON-serialisable `as_dict()` payload for notebooks and APIs.

`summarise_suite_attribution(report=...)` builds analyst-facing projections from
an existing `SuiteAttributionReport`: top contributors, grouped contributors by
component and source level, residual records, and unsupported attribution
records. The summary rows include `component`, `contribution_id`, `source_id`,
`source_level`, `bucket_key`, `category`, `method`, `contribution`, `residual`,
`reconciliation_status`, and `reason` fields for drillthrough to package-owned
records.

## Method

The suite aggregation method is reconciliation and preservation:

1. Canonicalize component bundle labels.
2. Validate each bundle total against the matching component capital in
   `SuiteCapitalResult`.
3. Require exactly one complete supported component set:
   `frtb_ima + frtb_sa + frtb_cva`, or
   `frtb_ima + frtb_sbm + frtb_drc + frtb_rrao + frtb_cva`.
4. Preserve every incoming `CapitalContribution` record unchanged.
5. Emit one `AttributionMethod.RESIDUAL` record at `source_level="suite"` to
   reconcile bundle totals to top-of-house capital.
6. For report output, order component sections canonically as either
   `frtb_ima`, `frtb_sa`, `frtb_cva` or `frtb_ima`, `frtb_sbm`, `frtb_drc`,
   `frtb_rrao`, `frtb_cva`.
7. For summaries, derive rows only from the report contribution records. Top
   contributors are sorted by absolute `contribution + residual`, then by stable
   ids. Residual and unsupported tables preserve producer-owned method and
   reason fields.

The suite residual has `ReconciliationStatus.RECONCILED` when component bundle
totals equal suite capital within `1e-6`; otherwise it has
`PARTIAL_RESIDUAL`.

## Inputs Used

The helper consumes:

- `SuiteCapitalResult.total_capital`
- `SuiteCapitalResult.ima_capital`
- `SuiteCapitalResult.sa_capital`
- `SuiteCapitalResult.cva_capital`
- SA component subtotals for SBM, DRC, and RRAO when decomposed bundles are used
- complete `ComponentContributionBundle` inputs

The report builder consumes the same inputs and optional `suite_total_capital`
override accepted by `aggregate_suite_attribution`.

The summary helper consumes an already-built `SuiteAttributionReport` and does
not consume raw package inputs.

## Allocation Grain

Orchestration supports:

- top-level bundle set: `frtb_ima`, `frtb_sa`, `frtb_cva`;
- decomposed SA bundle set: `frtb_ima`, `frtb_sbm`, `frtb_drc`, `frtb_rrao`,
  `frtb_cva`;
- one suite residual record.

It does not change the source grain chosen by component packages.
`SuiteAttributionReport.contribution_records` returns component records followed
by the suite residual record; component records are the original
`CapitalContribution` objects.

`SuiteAttributionSummary` supports the same allocation grains and adds:

- `top_contributors`;
- `contributors_by_component`;
- `contributors_by_source_level`;
- `residual_records`;
- `unsupported_records`.

## Limitations

- Partial component sets are rejected.
- Duplicate component bundles are rejected.
- Component totals that do not match suite component capital are rejected.
- Orchestration does not invent exact Euler decomposition for non-additive
  component internals or unsupported component branches.
- Summary helpers are projections only. They do not re-run package capital,
  marginal multipliers, finite differences, or fallback calculations.
- Cross-run impact analysis is outside this helper.

## Evidence

Tests:

- `packages/frtb-orchestration/tests/test_suite_capital.py`

Package guides:

- `packages/frtb-ima/ATTRIBUTION.md`
- `packages/frtb-sbm/ATTRIBUTION.md`
- `packages/frtb-drc/ATTRIBUTION.md`
- `packages/frtb-rrao/ATTRIBUTION.md`
- `packages/frtb-cva/ATTRIBUTION.md`

Design references:

- `docs/decisions/0032-orchestration-sa-arithmetic-and-fallback-routing.md`
- `docs/decisions/0038-suite-wide-attribution-impact-contract.md`
- `docs/decisions/0039-orchestration-suite-capital-aggregation.md`
