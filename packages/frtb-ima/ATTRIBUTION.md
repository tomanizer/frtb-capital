# Capital Attribution

`frtb-ima` exposes desk-level capital contribution projections over completed
IMA audit records. Attribution is intentionally post-calculation: it reads a
`DeskAuditRecord` and does not recalculate IMCC, SES, PLA, or the selected desk
capital charge.

## Current Support

Public helpers:

```python
from frtb_ima import build_ima_contribution_bundle, desk_contributions
```

`desk_contributions(record)` returns `frtb_common.CapitalContribution` records
for the deepest defensible desk grain available in `DeskAuditRecord`:

- retained IMCC child components when a nested IMCC component map reconciles to
  the selected IMCC amount;
- retained SES child components when a nested SES component map reconciles to
  the selected SES amount;
- retained PLA add-on child components when a nested PLA component map
  reconciles to `pla_addon`;
- aggregate `IMCC`, `SES`, and `PLA_ADDON` records when no reconciling child
  map is available;
- non-additive `UNSUPPORTED` explain records for retained NMRF Type A / Type B
  SES risk-factor amounts and liquidity-horizon ES components;
- `IMA_RC_RESIDUAL`, when a floor, max branch, binding-term effect, or
  unexplained reconciliation difference exists.

`build_ima_contribution_bundle(records, total_ima_capital=...)` wraps one or
more completed desk records in a shared
`frtb_common.contribution_bundle.ComponentContributionBundle` with
`component="frtb_ima"`. The helper validates that all desk records belong to one
run, input hash, and policy hash. When `total_ima_capital` is supplied from an
IMA summary, the emitted additive contribution plus residual total must
reconcile to that summary total before the bundle is returned.

## Method

For additive retained desk components, amounts are projected with
`AttributionMethod.ANALYTICAL_EULER`, `marginal_multiplier=1.0`, and
`contribution=base_amount`. This is an additive desk-component decomposition,
not a risk-factor Euler decomposition through the expected-shortfall scenario
cube.

The helper will use nested component maps under keys such as `components`,
`component_breakdown`, `risk_class_components`, or `bucket_components` only when
the numeric child values sum back to the aggregate IMCC, SES, or PLA amount
within `1e-6`. Non-reconciling child maps are treated as insufficient evidence
and the aggregate component is emitted instead.

NMRF and liquidity-horizon records are emitted only as branch-local explain
evidence with `AttributionMethod.UNSUPPORTED`, `contribution=None`, and
`residual=0.0`. Their `base_amount` carries the retained SES or ES amount and
their `reason` explains why the record is not additive capital: NMRF SES uses
Type A / Type B square-root aggregation, and LHA uses nested liquidity-horizon
square-root aggregation over scenario vectors.

If component records do not sum to the selected desk capital within `1e-6`,
the helper emits one residual record:

- `PARTIAL_RESIDUAL` when the audit record indicates an active floor or selected
  non-spot branch.
- `UNRECONCILED` when no such branch explains the difference.

## Inputs Used

The helpers consume:

- `DeskAuditRecord.run_id`
- `DeskAuditRecord.desk_id`
- `DeskAuditRecord.capital`
- `DeskAuditRecord.imcc`
- `DeskAuditRecord.ses`
- `DeskAuditRecord.pla`
- `DeskAuditRecord.inputs_hash`
- `DeskAuditRecord.policy_hash`

`inputs_hash` and `policy_hash` are propagated to the shared attribution
records as `input_hash` and `profile_hash`; bundle-level hashes are taken from
the same run-level values.

## Allocation Grain

The supported additive grain is retained desk component:

- `source_level="desk"`
- `source_id=<desk_id>`
- `bucket_key=<run_id>`
- `category` in aggregate `IMCC`, `SES`, `PLA_ADDON`, detail categories such as
  `IMCC_CURRENT_ES`, `SES_RATES`, `PLA_ADDON_AMBER_SHORTFALL`, or
  `IMA_RC_RESIDUAL`

Branch-local explain records use narrower source levels without contributing to
the reconciliation total:

- `source_level="risk_factor"` for `SES_NMRF_TYPE_A` and `SES_NMRF_TYPE_B`
- `source_level="liquidity_horizon"` for `IMCC_LH_UNCONSTRAINED` and
  `IMCC_LH_CONSTRAINED`

## Limitations

- No trade-level, scenario-level, PLA-observation-level, or smooth risk-factor
  Euler attribution is implemented.
- NMRF and liquidity-horizon records are explain evidence, not additive capital
  allocation records.
- The method does not differentiate through ES, IMCC, SES, PLA, backtesting, or
  RFET mechanics.
- Floor, max-branch, and binding-term effects are not forced into component
  records; they are reported as explicit residuals.
- Missing desk totals or non-finite numeric values fail before records are
  emitted.

## Evidence

Tests:

- `packages/frtb-ima/tests/test_attribution.py`
- `packages/frtb-orchestration/tests/test_ima_contribution_bundle.py`

Design references:

- `docs/decisions/0012-capital-impact-attribution.md`
- `docs/decisions/0038-suite-wide-attribution-impact-contract.md`
