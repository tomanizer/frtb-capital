# Capital Attribution

`frtb-ima` exposes desk-level capital contribution projections over completed
IMA audit records. Attribution is intentionally post-calculation: it reads a
`DeskAuditRecord` and does not recalculate IMCC, SES, PLA, or the selected desk
capital charge.

## Current Support

Public helper:

```python
from frtb_ima import desk_contributions
```

`desk_contributions(record)` returns `frtb_common.CapitalContribution` records
for the desk-level components available in `DeskAuditRecord`:

- `IMCC`
- `SES`
- `PLA_ADDON`, when present
- `IMA_RC_RESIDUAL`, when a floor, max branch, or unexplained reconciliation
  difference exists

## Method

For the standard additive desk path, component amounts are projected with
`AttributionMethod.ANALYTICAL_EULER`, `marginal_multiplier=1.0`, and
`contribution=base_amount`. This is an additive desk-component decomposition,
not a risk-factor Euler decomposition through the expected-shortfall scenario
cube.

If component records do not sum to the selected desk capital within `1e-6`,
the helper emits one residual record:

- `PARTIAL_RESIDUAL` when the audit record indicates an active floor or selected
  non-spot branch.
- `UNRECONCILED` when no such branch explains the difference.

## Inputs Used

The helper consumes:

- `DeskAuditRecord.run_id`
- `DeskAuditRecord.desk_id`
- `DeskAuditRecord.capital`
- `DeskAuditRecord.imcc`
- `DeskAuditRecord.ses`
- `DeskAuditRecord.inputs_hash`
- `DeskAuditRecord.policy_hash`

`inputs_hash` and `policy_hash` are propagated to the shared attribution
records as `input_hash` and `profile_hash`.

## Allocation Grain

The supported grain is desk component:

- `source_level="desk"`
- `source_id=<desk_id>`
- `bucket_key=<run_id>`
- `category` in `IMCC`, `SES`, `PLA_ADDON`, or `IMA_RC_RESIDUAL`

## Limitations

- No trade-level, risk-factor-level, scenario-level, liquidity-horizon-level,
  NMRF-level, or PLA-observation-level attribution is implemented.
- The method does not differentiate through ES, IMCC, SES, PLA, backtesting, or
  RFET mechanics.
- Floor and max-branch effects are not forced into component records; they are
  reported as explicit residuals.
- Missing desk totals or non-finite numeric values fail before records are
  emitted.

## Evidence

Tests:

- `packages/frtb-ima/tests/test_attribution.py`

Design references:

- `docs/decisions/0012-capital-impact-attribution.md`
- `docs/decisions/0038-suite-wide-attribution-impact-contract.md`
