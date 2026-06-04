# Capital Attribution

`frtb-sbm` exposes post-calculation attribution for completed
`SbmCapitalResult` objects. The helper reads retained scenario, bucket,
correlation, sensitivity, citation, input-hash, and profile-hash evidence; it
does not alter the SBM capital number.

## Current Support

Package helper:

```python
from frtb_sbm.attribution import calculate_sbm_attribution
```

`calculate_sbm_attribution(result)` returns
`frtb_common.CapitalContribution` records for all risk classes in the result.

## Method

For supported delta and vega paths, the package uses analytical Euler
attribution at sensitivity grain over the selected MAR21.4 scenario branch.
For sensitivity `i` in bucket `a` with selected risk-class capital `K`:

```text
marginal_i = ((rho_a @ WS_a)[i] + (gamma @ S)_a) / K
contribution_i = WS_i * marginal_i
```

In this expression, `(gamma @ S)_a` is computed from the retained
off-diagonal inter-bucket correlation records only. The implementation ignores
same-bucket diagonal entries, so no `S_a` diagonal term is included or needs to
be subtracted.

The method uses:

- selected intra-bucket pairwise correlations;
- selected inter-bucket `gamma` correlations;
- selected bucket `S_b` values;
- scaled weighted sensitivities;
- the selected risk-class scenario and selected capital.

The implementation emits a rounding residual only when the Euler contributions
do not reconcile to selected risk-class capital within `1e-6`.

## Unsupported Branches

The helper emits `AttributionMethod.UNSUPPORTED` with the selected risk-class
capital carried in `residual` when exact Euler attribution is not valid or the
required evidence is unavailable. Current unsupported cases include:

- curvature risk measures, because the CVR `max(..., 0)` floor in Basel MAR21.5
  prevents exact Euler decomposition in the implemented path;
- missing selected scenario detail;
- selected scenario detail absent from retained records;
- alternative `S_b` under Basel MAR21.4(5)(b), because adjusted `S_b` values are
  not retained for attribution;
- incomplete pairwise correlation materialisation;
- active bucket floors;
- missing intra-bucket detail.

## Inputs Used

The attribution helper consumes only fields already present on the
`SbmCapitalResult` and nested result records:

- `input_hash` and `profile_hash`;
- risk-class selected capital, selected scenario, and citation ids;
- selected `RiskClassScenarioDetail`;
- bucket capital records and floor metadata;
- `WeightedSensitivity` records and their `sensitivity_id`, `scaled_amount`,
  and citations;
- retained pairwise and inter-bucket correlation records.

## Allocation Grain

- Analytical records: `source_level="sensitivity"`, one record per retained
  weighted sensitivity.
- Unsupported records: `source_level="risk_class"`, one record per unsupported
  selected risk-class branch.
- Residual records: `source_level="risk_class"`, one explicit reconciliation
  residual when needed.

## Limitations

- Attribution is available only after a successful capital calculation.
- Unsupported regulatory profiles and unsupported capital paths fail before
  attribution can run.
- Curvature attribution is deliberately not approximated as Euler attribution in
  the current implementation.
- Finite-difference impact is a separate `impact.py` concern and is not
  reported as marginal contribution.

## Evidence

Tests:

- `packages/frtb-sbm/tests/test_sbm_attribution_impact.py`

Design and regulatory references:

- `docs/decisions/0012-capital-impact-attribution.md`
- `docs/decisions/0038-suite-wide-attribution-impact-contract.md`
- Basel MAR21.4(4)-(5)
- Basel MAR21.5
