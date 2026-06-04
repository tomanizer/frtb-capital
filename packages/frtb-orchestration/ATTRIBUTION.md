# Capital Attribution

`frtb-orchestration` owns suite-level aggregation of package contribution
bundles. It does not recalculate component attribution and does not reach into
private component internals.

## Current Support

Public helper:

```python
from frtb_orchestration import aggregate_suite_attribution
```

`aggregate_suite_attribution(suite_result=..., component_bundles=...)` returns a
`SuiteAttributionResult` that preserves incoming
`frtb_common.ComponentContributionBundle` objects unchanged and adds one
suite-level residual record.

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

## Allocation Grain

Orchestration supports:

- top-level bundle set: `frtb_ima`, `frtb_sa`, `frtb_cva`;
- decomposed SA bundle set: `frtb_ima`, `frtb_sbm`, `frtb_drc`, `frtb_rrao`,
  `frtb_cva`;
- one suite residual record.

It does not change the source grain chosen by component packages.

## Limitations

- Partial component sets are rejected.
- Duplicate component bundles are rejected.
- Component totals that do not match suite component capital are rejected.
- Orchestration does not invent exact Euler decomposition for non-additive
  component internals or unsupported component branches.
- Cross-run impact analysis is outside this helper.

## Evidence

Tests:

- `packages/frtb-orchestration/tests/test_suite_capital.py`

Design references:

- `docs/decisions/0032-orchestration-sa-arithmetic-and-fallback-routing.md`
- `docs/decisions/0038-suite-wide-attribution-impact-contract.md`
- `docs/decisions/0039-orchestration-suite-capital-aggregation.md`
