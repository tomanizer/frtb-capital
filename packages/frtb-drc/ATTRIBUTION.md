# Capital Attribution

`frtb-drc` emits deterministic attribution records over completed DRC capital
results. Attribution is post-calculation: it consumes the validated
`DrcCapitalResult`, retained net-JTD and branch evidence, and run-scoped
risk-weight lineage without changing DRC capital.

## Current Support

Public helpers:

```python
from frtb_drc import (
    calculate_drc_attribution,
    summarize_drc_attribution_by_bucket,
    summarize_drc_attribution_by_category,
    summarize_drc_attribution_by_issuer,
    summarize_drc_attribution_by_risk_class,
    top_drc_attribution_summaries,
    validate_attribution_reconciliation,
)
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

## Contributor Summaries

`DrcAttributionSummary` projects existing `CapitalContribution` records for
analyst-facing views. Summary helpers never re-run DRC capital or analytical
Euler formulas; they only group records already present on the result or passed
explicitly by the caller.

Supported grains:

- `summarize_drc_attribution_by_issuer(result)` groups net-JTD records by the
  retained `NetJtd.obligor_or_tranche_key`.
- `summarize_drc_attribution_by_bucket(result)` groups by `bucket_key`.
- `summarize_drc_attribution_by_category(result)` groups by the DRC category
  label carried on the attribution record. DRC categories currently align with
  risk-class capital stacks.
- `summarize_drc_attribution_by_risk_class(result)` groups by retained net-JTD
  risk class where available and falls back to the record category for residual
  or unsupported records.
- `top_drc_attribution_summaries(result, grain="issuer", limit=10)` returns the
  largest groups by absolute contribution plus residual.

Each summary retains deterministic `source_ids`, `net_jtd_ids`, method labels,
citations, and reason strings. Unsupported and residual records are included in
summary totals rather than dropped. Records without issuer or bucket lineage are
reported under `UNALLOCATED`, preserving reconciliation while making the missing
allocation boundary explicit.

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

Risk-weight lineage diagnostics use stable reason prefixes for the failed
precondition: `missing risk weight`, `non-finite risk weight`, `negative risk
weight`, and `non-unique risk weights`. The unsupported record keeps the bucket
residual so reconciliation remains visible while the failed input condition is
explicit.

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

Summary helpers consume:

- `DrcCapitalResult.attribution_records` or explicitly supplied records
- `DrcCapitalResult.net_jtds` for issuer and risk-class lineage

## Allocation Grain

- Analytical records: `source_level="net_jtd"`.
- Unsupported records: `source_level="bucket"` or `source_level="category"`.
- Residual records: `source_level="category"`.
- Summary projections: issuer, bucket, category, and risk class.

## Limitations

- Attribution does not back-propagate through gross-JTD netting or fair-value
  cap evidence; it starts from the completed net-JTD and bucket result graph.
- Exact Euler attribution requires unique risk-weight lineage for the positions
  represented by each net JTD record.
- Floors and zero-denominator branches are reported explicitly instead of being
  smoothed or approximated.
- Issuer summaries cannot assign bucket/category unsupported residuals to an
  issuer when the source record has no net-JTD lineage; those amounts remain
  visible under `UNALLOCATED`.
- Baseline-versus-candidate impact remains separate from marginal attribution.

## Evidence

Tests:

- `packages/frtb-drc/tests/test_drc_attribution.py`
- `packages/frtb-drc/tests/test_drc_attribution_summaries.py`

Design references:

- `docs/decisions/0012-capital-impact-attribution.md`
- `docs/decisions/0031-drc-attribution-method-contract.md`
- `docs/decisions/0038-suite-wide-attribution-impact-contract.md`
