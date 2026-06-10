# Capital Attribution Methods

This guide explains the attribution methods used across the `frtb-capital`
suite and when each method is appropriate. Package-specific implementation
details live in each package's `ATTRIBUTION.md`; this page is the suite-level
method guide.

Capital attribution is an explain layer over an already computed capital
result. It must not change the capital number. Capital kernels produce the
audited result and branch metadata; attribution modules consume that result and
emit contribution, residual, unsupported, or impact records.

## Method Selection

| Method | Use when | Do not use when |
| --- | --- | --- |
| Analytical Euler contribution | The capital function is sufficiently smooth, positively homogeneous of degree 1 in the source-level input, and evaluated on a stable branch. | Floors, caps, max/min choices, bucket moves, eligibility switches, zero denominators, or missing lineage make the derivative invalid or unstable. |
| Standalone contribution | The package has an additive or standalone capital line that is already a meaningful explain amount. | The amount is being presented as a marginal derivative through a nonlinear aggregation that was not actually differentiated. |
| Branch residual | A component contribution set is mostly explainable but needs an explicit residual for floors, branch selection, rounding, or top-of-house reconciliation. | The residual would hide an unsupported method or silently force capital into unrelated source records. |
| Unsupported attribution | The package cannot produce a defensible attribution for the active branch. | A valid residual or standalone contribution can honestly explain the branch without implying false precision. |
| Finite-difference impact | Comparing two completed runs, such as baseline versus candidate capital. | Reporting marginal contribution inside one run. Finite difference is movement analysis, not Euler attribution. |

## Analytical Euler

Analytical Euler attribution is preferred where it is mathematically valid. For
a capital measure `K(x)` and source-level input `x_i`, the contribution is:

```text
contribution_i = x_i * dK / dx_i
```

Euler attribution works cleanly when `K` is:

- differentiable at the active point;
- positively homogeneous of degree 1 in the source-level inputs;
- evaluated on a stable regulatory branch;
- supported by retained audit records sufficient to compute the derivative;
- free of active floors, caps, zero denominators, and discontinuous switches at
  the attribution point.

When those conditions hold, contributions should reconcile to the attributed
capital total within the suite tolerance defined by
[ADR 0038](decisions/0038-suite-wide-attribution-impact-contract.md).

## FRTB Branches That Need Care

Some FRTB components include nonlinear or discontinuous behavior where exact
Euler decomposition is not valid or not stable. Package docs must state these
cases plainly and choose a labelled fallback.

Common examples:

- **Max/min or selected-scenario branches:** a small input movement can change
  the selected branch, so the derivative on one branch may not explain the
  neighboring result.
- **Floors and caps:** derivatives can be zero, discontinuous, or undefined at
  the floor/cap boundary.
- **Regime switches and eligibility tests:** a source can cross a profile,
  approval, desk-eligibility, hedge-eligibility, bucket, or modellability
  threshold.
- **Bucketing and classification moves:** attribution on one bucket assignment
  does not explain a result after the source migrates to another bucket or
  classification.
- **Scenario selection:** selected stress windows, selected SBM scenarios, and
  selected up/down branches need explicit selected-branch metadata.
- **Curvature and default aggregation:** asymmetric shocks, `max(..., 0)`,
  default-risk HBR, bucket floors, and CTP recognition factors can make a
  smooth global Euler decomposition inappropriate.
- **Residual-risk behavior:** RRAO is additive at line level in the current
  implementation, but unsupported residual-risk evidence paths must fail before
  attribution rather than emitting placeholder capital.
- **Missing lineage:** exact attribution is unsupported if the result does not
  retain source ids, risk weights, correlations, selected branch data, or
  intermediate totals needed to compute the contribution.

## Fallback Rules

When analytical Euler is not defensible, use the narrowest honest fallback:

1. **Standalone contribution:** use when the component already has an additive
   or standalone charge, such as a line add-on or standalone netting-set charge.
   Label it as standalone or allocated contribution if it is not a derivative
   through the full capital formula.
2. **Branch residual:** use when a contribution set is otherwise meaningful but
   the selected branch leaves a known, explicit remainder. The residual record
   must carry the amount, branch reason, source level, and reconciliation status.
3. **Unsupported attribution:** use when no exact or limited explain view is
   available for the active branch. Carry the unattributed amount in `residual`
   where the shared `CapitalContribution` contract is used.
4. **Finite-difference impact:** use only for baseline-versus-candidate run
   comparison. The delta is:

   ```text
   impact = candidate_total - baseline_total
   ```

   It must be labelled as finite difference and must not be presented as a
   marginal source contribution inside one run.

Silent pro-rata allocation is not an acceptable fallback unless the package doc
states why it is the implemented method, what capital total it reconciles to,
and why it does not imply Euler precision.

## Required Documentation Per Package

Each package-level `ATTRIBUTION.md` should state:

- what capital result is attributed;
- the implemented method labels;
- the input fields and audit records used;
- the supported attribution grain;
- reconciliation behavior and tolerance;
- unsupported branches and explicit reasons;
- limitations where the method is additive, allocated, residual, or impact
  analysis rather than exact Euler attribution;
- tests or evidence that cover reconciliation and unsupported behavior.

The suite matrix for current implementation status is:

- [Attribution implementation matrix](ATTRIBUTION_IMPLEMENTATION_MATRIX.md)

The current package guides are:

- [frtb-common attribution contract](../packages/frtb-common/ATTRIBUTION.md)
- [frtb-ima attribution](../packages/frtb-ima/ATTRIBUTION.md)
- [frtb-sbm attribution](../packages/frtb-sbm/ATTRIBUTION.md)
- [frtb-drc attribution](../packages/frtb-drc/ATTRIBUTION.md)
- [frtb-rrao attribution and allocation](../packages/frtb-rrao/ATTRIBUTION.md)
- [frtb-cva attribution](../packages/frtb-cva/ATTRIBUTION.md)
- [frtb-orchestration attribution aggregation](../packages/frtb-orchestration/ATTRIBUTION.md)
- [frtb-result-store attribution storage](../packages/frtb-result-store/ATTRIBUTION.md)

## Shared Record Expectations

Where a package projects into `frtb_common.CapitalContribution`, records should
make the method explicit:

- `ANALYTICAL_EULER` requires `base_amount`, `marginal_multiplier`, and
  `contribution`.
- `STANDALONE` carries additive or standalone explain amounts in
  `contribution` and must not be described as a marginal derivative.
- `RESIDUAL` carries the residual amount and reason.
- `UNSUPPORTED` carries the unsupported reason and, when applicable, the full
  unattributed amount as residual.
- `ReconciliationStatus` states whether the record set reconciles, partially
  reconciles through residuals, is unreconciled, or has not been evaluated.

For component bundles, orchestration must preserve component records unchanged
and add only explicit suite-level residual records needed to reconcile to
top-of-house capital.

## References

- [ADR 0012: Capital impact and attribution readiness](decisions/0012-capital-impact-attribution.md)
- [ADR 0031: DRC attribution method contract](decisions/0031-drc-attribution-method-contract.md)
- [ADR 0037: Analytical Euler decomposition framework](decisions/0037-analytical-euler-decomposition-framework.md)
- [ADR 0038: Suite-wide attribution and impact contract](decisions/0038-suite-wide-attribution-impact-contract.md)
