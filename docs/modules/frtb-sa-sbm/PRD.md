# FRTB SA SBM Product Requirements Document

## Objective

Build `frtb-sa-sbm`, a package that calculates FRTB standardised approach
sensitivities-based capital from synthetic sensitivity inputs across all
prescribed risk classes, risk measures, buckets, and correlation scenarios.

## Users

- Market risk quant developers validating SBM mechanics.
- Risk controllers comparing standardised and internal-model outputs.
- Model risk reviewers checking risk weights, correlations, and audit lineage.
- Suite orchestrators combining SBM with DRC and RRAO.

## Non-Goals

- No pricing engine.
- No market data sourcing.
- No trade-level risk-factor classification beyond explicit CRIF/canonical
  mapping helpers.
- No database persistence.
- No final regulatory submission packaging.

## Functional Scope

1. Canonical sensitivity input model.
2. Risk-class and risk-measure enums.
3. Reference tables for risk weights, tenors, buckets, and correlations.
4. Delta, vega, and curvature calculation kernels.
5. Intra-bucket and inter-bucket aggregation.
6. Low/medium/high correlation scenarios.
7. CRIF mapping and synthetic examples.
8. Audit and Euler-compatible reporting.

## Architecture

| Layer | Responsibility |
| --- | --- |
| `data_models.py` | Frozen sensitivity, bucket, risk-class, and result dataclasses. |
| `reference_data.py` | Risk weights, buckets, tenors, correlations, and profile tables. |
| `weighted_sensitivity.py` | Risk-weighting and input normalisation. |
| `aggregation.py` | Generic intra/inter-bucket formulas. |
| `risk_classes/*` | GIRR, CSR non-sec, CSR sec CTP, CSR sec non-CTP, equity, commodity, FX. |
| `curvature.py` | Curvature-specific scenario and floor handling. |
| `crif.py` | CRIF-to-canonical mapping. |
| `audit.py` | Reconciliation, Euler, and report records. |

## Delivery Slices

1. **Skeleton and source register**.
2. **Common models and reference data**.
3. **Generic weighted-sensitivity and aggregation engine**.
4. **GIRR and FX delta MVP**.
5. **Equity and commodity delta/vega/curvature**.
6. **CSR non-sec and securitisation paths**.
7. **CRIF mapping and examples**.
8. **Audit, Euler reconciliation, and suite integration**.

## Acceptance Criteria

- All seven risk classes are represented in enums and reference tables.
- Delta, vega, and curvature are explicitly supported or explicitly
  unsupported per risk class.
- Correlation scenarios reconcile and final selected scenario is auditable.
- Risk-class totals sum to total SBM according to profile rules.
- No sibling imports.
- Synthetic fixtures cover each risk class and at least one curvature case.

