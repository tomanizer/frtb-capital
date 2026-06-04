# Capital Attribution

`frtb-cva` exposes attribution over completed CVA capital results. The helper
does not recalculate BA-CVA, SA-CVA, mixed carve-out capital, hedge eligibility,
or qualified-index routing.

## Current Support

Public helpers:

```python
from frtb_cva import attribute_cva_capital, project_cva_attribution
```

`attribute_cva_capital(result)` returns a package-local `CvaAttributionResult`.
`project_cva_attribution(attribution, result)` maps standalone explain rows,
unsupported-branch markers, and residual records to the shared
`frtb_common.CapitalContribution` shape. Projection populates `input_hash`,
`profile_hash`, citations, reasons, and reconciliation status from the capital
result.

## Method

For BA-CVA methods, netting-set standalone capital lines are emitted as
`standalone` explain contributions on the stable standalone branch. Reduced
portfolio square-root aggregation, full BA-CVA hedged square-root aggregation,
and the beta floor are not represented as exact Euler records.

For SA-CVA, bucket capital `K_b` is allocated evenly across retained
`sensitivity_ids` in that bucket and labelled as `standalone_allocated` in the
package-local result. The allocation explains retained bucket capital only. It
is not an exact derivative through the risk-class square-root aggregation or the
SA-CVA multiplier.

Projected shared records use:

- `AttributionMethod.STANDALONE` for BA netting-set standalone lines and SA
  bucket allocations, with `contribution=amount` and
  `marginal_multiplier=None`.
- `AttributionMethod.UNSUPPORTED` for nonlinear CVA branches that are visible
  but not allocated as exact Euler.
- `AttributionMethod.RESIDUAL` for the reconciliation gap between total CVA
  capital and the standalone/allocated explain rows.

## Unsupported Branches

The package-local result reports unsupported nonlinear branches, including:

- `ba_cva_reduced_portfolio_sqrt`
- `ba_cva_hedged_sqrt`
- `ba_cva_beta_floor`
- `sa_cva_risk_class_sqrt:<risk_class>`

When unsupported branches are present, `CvaAttributionResult.reconciled` is
false. Projected records carry `ReconciliationStatus.PARTIAL_RESIDUAL` and
reconcile to `CvaCapitalResult.total_cva_capital` through:

```text
sum(record.contribution or 0) + sum(record.residual)
```

## Inputs Used

Attribution consumes:

- `CvaCapitalResult.method`
- `CvaCapitalResult.total_cva_capital`
- `ba_cva_netting_set_lines`
- `ba_cva_reduced` and `ba_cva_full` branch presence
- `sa_cva_risk_class_capitals`
- bucket `K_b`, sensitivity ids, citations
- `input_hash` and `profile_hash` during projection

## Allocation Grain

- BA-CVA stable branch: netting set standalone capital.
- SA-CVA bucket allocation: retained sensitivity id inside a risk-class bucket.
- Unsupported branches: shared `UNSUPPORTED` records with stable branch ids and
  reasons.
- Residual: one shared `RESIDUAL` record when the standalone/allocated rows do
  not sum to total CVA capital.

## Limitations

- SA-CVA risk-class square-root aggregation, BA-CVA hedged square-root
  aggregation, and beta floor effects are not forced into exact Euler records.
- Unsupported records mark method limitations and cite the relevant branch; they
  do not allocate nonlinear capital by themselves. The reconciliation amount is
  carried by the residual record.
- Unsupported CVA methods, unsupported future profiles or profile cells, and
  MAR50.9 materiality-threshold alternatives fail before attribution can run.
- Finite-difference impact is implemented separately in `impact.py` and is not
  marginal attribution.

## Evidence

Tests:

- `packages/frtb-cva/tests/test_cva_attribution.py`
- `packages/frtb-cva/tests/test_cva_impact.py`

Design and regulatory references:

- `docs/decisions/0012-capital-impact-attribution.md`
- `docs/decisions/0038-suite-wide-attribution-impact-contract.md`
- Basel MAR50.8
- Basel MAR50.14-MAR50.26
- Basel MAR50.42-MAR50.77
