# FRTB CVA Product Requirements Document

## Objective

Build `frtb-cva`, a package that calculates CVA risk capital through BA-CVA and
SA-CVA paths from synthetic counterparty, exposure, hedge, and sensitivity
inputs.

## Users

- CVA desk/risk developers validating capital mechanics.
- Market risk teams comparing CVA capital with SBM and IMA outputs.
- Model risk reviewers tracing hedge eligibility and exposure inputs.
- Suite orchestrators aggregating top-of-house capital.

## Non-Goals

- No exposure simulation engine.
- No accounting CVA production.
- No live hedge management.
- No supervisor approval workflow.
- No dependency on pandas or proprietary systems.

## Functional Scope

1. CVA scope and method selection.
2. Counterparty/netting-set exposure input validation.
3. Eligible CVA hedge classification and internal transfer flags.
4. BA-CVA counterparty-level calculation.
5. SA-CVA delta and vega risk-class calculations.
6. CVA/hedge sensitivity netting.
7. Aggregation and multiplier application.
8. Audit and benchmark report outputs.

## Architecture

| Layer | Responsibility |
| --- | --- |
| `data_models.py` | Counterparty, netting set, hedge, sensitivity, and result dataclasses. |
| `regimes.py` | BA/SA method policy, multiplier, eligible hedge rules. |
| `ba_cva.py` | Basic approach capital mechanics. |
| `sa_cva.py` | SA-CVA orchestration and total aggregation. |
| `risk_classes/*` | GIRR, FX, CCS, RCS, equity, and commodity delta/vega components. |
| `hedges.py` | Eligible hedge checks and CVA/hedge netting. |
| `audit.py` | Reportable audit records and reconciliation. |

## Delivery Slices

1. **Skeleton and source map**.
2. **Data contracts and method policy**.
3. **BA-CVA MVP**: counterparty/netting set exposure, maturity, hedge fields,
   capital total.
4. **SA-CVA common aggregation**: weighted sensitivities, CVA/hedge tags,
   risk-class result structure.
5. **SA-CVA risk classes**: GIRR, FX, CCS, RCS, equity, commodity.
6. **Hedge eligibility and internal transfer support**.
7. **Audit, examples, and suite integration**.

## Acceptance Criteria

- BA-CVA and SA-CVA are separately selectable.
- CVA hedge benefit is never applied unless eligibility is explicit.
- Exposure-at-default inputs are validated and traceable.
- SA-CVA risk-class totals reconcile to overall total.
- Unsupported profile features fail explicitly.
- Synthetic fixtures cover at least one counterparty, one hedge, and each
  SA-CVA risk class.

