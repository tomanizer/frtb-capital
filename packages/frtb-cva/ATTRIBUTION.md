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
`project_cva_attribution(attribution, result)` maps analytical contribution
records to the shared `frtb_common.CapitalContribution` shape and populates
`input_hash`, `profile_hash`, and reconciliation status from the capital result.

## Method

For BA-CVA methods, netting-set standalone capital lines are emitted as
`analytical_euler` contributions on the stable standalone branch.

For SA-CVA, bucket capital `K_b` is allocated evenly across retained
`sensitivity_ids` in that bucket and labelled as `analytical_euler` in the
package-local result. The risk-class square-root aggregation remains explicitly
unsupported, so these records should be read as bucket-level allocated
contributions, not an exact derivative through the full SA-CVA aggregation.

Projected shared records use `AttributionMethod.ANALYTICAL_EULER` with
`base_amount=amount`, `marginal_multiplier=1.0`, and `contribution=amount`.

## Unsupported Branches

The package-local result reports unsupported nonlinear branches, including:

- `ba_cva_reduced_portfolio_sqrt`
- `ba_cva_hedged_sqrt`
- `ba_cva_beta_floor`
- `sa_cva_risk_class_sqrt:<risk_class>`

When unsupported branches are present, `CvaAttributionResult.reconciled` is
false and projected records carry `ReconciliationStatus.UNRECONCILED`.

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
- Unsupported branches: method/risk-class branch labels in the package-local
  result.

## Limitations

- SA-CVA risk-class square-root aggregation, BA-CVA hedged square-root
  aggregation, and beta floor effects are not forced into exact Euler records.
- The projected shared records do not currently emit separate shared
  `UNSUPPORTED` records for the package-local unsupported branch list.
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
