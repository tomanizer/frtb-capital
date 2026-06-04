# Capital Attribution

`frtb-drc` emits deterministic attribution records over completed DRC capital
results. Attribution is post-calculation: it consumes the validated
`DrcCapitalResult`, retained net-JTD and branch evidence, and run-scoped
risk-weight lineage without changing DRC capital.

## Current Support

Public helpers:

```python
from frtb_drc import calculate_drc_attribution, validate_attribution_reconciliation
```

Row and batch calculation paths populate `DrcCapitalResult.attribution_records`
where the caller supplies the risk-weight evidence needed by the supported
path.

## Method

Supported stable bucket/category branches use analytical Euler attribution over
net JTD records. The helper uses:

- category capital and category branch metadata;
- bucket capital, HBR, floor metadata, and citations;
- net JTD amount, direction, ids, and source position ids;
- run-scoped position risk weights;
- CTP category recognition factors when the risk class is correlation trading
  portfolio.

For non-CTP paths, attribution is bucket-local through the HBR expression. For
CTP, the method applies the active positive/negative bucket recognition factor
before reconciling to CTP category capital.

## Unsupported and Residual Branches

The helper emits `UNSUPPORTED` records with the unattributed amount carried in
`residual` when exact Euler attribution is not valid. Current unsupported cases
include:

- category floors;
- bucket floors;
- zero HBR denominator;
- missing net JTD records;
- missing, invalid, or non-unique risk-weight lineage for the positions inside
  a net JTD record.

The helper emits `RESIDUAL` records for empty category residuals or remaining
category capital needed to reconcile analytical records to capital.

`validate_attribution_reconciliation` requires the sum of contributions plus
residuals to equal `result.total_drc` within tolerance.

## Inputs Used

`calculate_drc_attribution` consumes:

- `DrcCapitalResult.categories`
- `DrcCapitalResult.net_jtds`
- `DrcCapitalResult.total_drc`
- `risk_weights_by_position`
- optional `input_hash` and `profile_hash`, usually copied from the result

## Allocation Grain

- Analytical records: `source_level="net_jtd"`.
- Unsupported records: `source_level="bucket"` or `source_level="category"`.
- Residual records: `source_level="category"`.

## Limitations

- Attribution does not back-propagate through gross-JTD netting or fair-value
  cap evidence; it starts from the completed net-JTD and bucket result graph.
- Exact Euler attribution requires unique risk-weight lineage for the positions
  represented by each net JTD record.
- Floors and zero-denominator branches are reported explicitly instead of being
  smoothed or approximated.
- Baseline-versus-candidate impact remains separate from marginal attribution.

## Evidence

Tests:

- `packages/frtb-drc/tests/test_drc_attribution.py`

Design references:

- `docs/decisions/0012-capital-impact-attribution.md`
- `docs/decisions/0031-drc-attribution-method-contract.md`
- `docs/decisions/0038-suite-wide-attribution-impact-contract.md`
