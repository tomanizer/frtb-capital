# Capital Attribution

`frtb-common` does not calculate capital and does not choose package-specific
attribution methods. It owns the shared attribution contracts that capital
packages project into after their own capital result has already been produced.

## Current Support

The shared runtime contracts are:

- `AttributionMethod`: `ANALYTICAL_EULER`, `RESIDUAL`, and `UNSUPPORTED`.
- `ReconciliationStatus`: `RECONCILED`, `PARTIAL_RESIDUAL`, `UNRECONCILED`,
  and `UNKNOWN`.
- `CapitalContribution`: one package-neutral contribution record.
- `ComponentContributionBundle`: a component-level wrapper used by
  `frtb-orchestration`.
- `CapitalImpact`: package-neutral baseline-versus-candidate capital delta,
  separate from attribution.

## Method Contract

`ANALYTICAL_EULER` records must carry both `marginal_multiplier` and
`contribution`. `RESIDUAL` and `UNSUPPORTED` records carry the explicitly
unattributed amount in `residual` and explain the cause in `reason`.

For a complete contribution set, the intended reconciliation invariant is:

```text
sum(contribution where contribution is not None) + sum(residual) == capital
```

The shared bundle contract enforces this invariant within a relative tolerance
of `1e-6` for component totals.

## Inputs Used

`frtb-common` only validates record shape. It does not interpret sensitivities,
scenario vectors, JTD records, RRAO lines, CVA exposures, regulatory profiles,
or branch metadata. Those semantics remain package-owned.

## Allocation Grain

The shared `source_level`, `source_id`, `bucket_key`, and `category` fields are
free text by design so each capital package can use its natural attribution
grain, such as desk, sensitivity, net JTD, line, netting set, component, or
suite.

## Limitations

- No capital component may rely on `frtb-common` to decide whether Euler
  attribution is valid for a regulatory branch.
- `CapitalContribution` is a projection contract, not a calculation kernel.
- `CapitalImpact` finite-difference records are movement analysis, not
  marginal capital attribution.

## Evidence

Contract behavior is covered by:

- `packages/frtb-common/tests/test_attribution.py`
- `packages/frtb-common/tests/test_attribution_contract.py`

Design references:

- `docs/decisions/0012-capital-impact-attribution.md`
- `docs/decisions/0037-analytical-euler-decomposition-framework.md`
- `docs/decisions/0038-suite-wide-attribution-impact-contract.md`
