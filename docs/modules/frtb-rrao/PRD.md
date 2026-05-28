# FRTB RRAO Product Requirements Document

## Objective

Build `frtb-rrao`, a focused package that classifies residual-risk positions
and calculates the residual risk add-on for the FRTB standardised approach.

## Users

- Quant developers validating RRAO mechanics.
- Risk controllers reviewing exotic and residual-risk classification.
- Model risk reviewers tracing classification evidence.
- Suite orchestration combining RRAO with SBM and DRC.

## Non-Goals

- No exotic payoff modelling.
- No pricing-model validation.
- No automated legal classification from trade terms beyond explicit inputs.
- No capital diversification or offsetting.

## Functional Scope

1. Canonical residual-risk input contracts.
2. Rule-profile classification into exotic, other residual risk, excluded, or
   unsupported.
3. Gross effective notional validation.
4. Additive capital calculation at 1 percent, 0.1 percent, or zero for cited
   exclusions.
5. Supervisor-directed inclusion.
6. Audit and reconciliation records.
7. Synthetic fixtures for exotic, other residual, exclusions, and forced
   inclusion.

## Architecture

| Layer | Responsibility |
| --- | --- |
| `data_models.py` | Frozen RRAO input, classification, and result dataclasses. |
| `classification.py` | Pure classification and exclusion checks. |
| `reference_data.py` | Risk-type weights and profile-specific labels. |
| `capital.py` | Weighted notional and total add-on calculation. |
| `crif.py` | CRIF/Axiom-style mapping into canonical fields. |
| `audit.py` | Contribution and exclusion explain output. |

## Delivery Slices

1. **Skeleton and source register**.
2. **Data model and risk weights**: 1 percent, 0.1 percent, zero/excluded.
3. **Classification and exclusion engine**.
4. **Capital calculation and audit result**.
5. **Input mapping and examples**.
6. **Suite integration and report output**.

## Acceptance Criteria

- Additive capital reconciles exactly to line contributions.
- Exclusions are explicit and cited.
- Classification reason is present for every position.
- Synthetic tests cover exotic, other residual risk, excluded, and forced
  inclusion cases.
- Unsupported classification inputs raise explicit errors.

