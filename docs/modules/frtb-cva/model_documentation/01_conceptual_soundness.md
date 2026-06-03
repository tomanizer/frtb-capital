# Conceptual Soundness

## Model Design

`frtb-cva` keeps CVA capital assembly separate from exposure simulation,
pricing, and hedge execution. BA-CVA consumes counterparty/netting-set exposure
inputs and eligible hedges. SA-CVA consumes aggregate CVA and hedge
sensitivities, consistent with MAR50.47, then applies weighted-sensitivity and
bucket aggregation mechanics.

## Core Mechanics

| Mechanic | Conceptual basis | Regulatory anchor | Evidence |
| --- | --- | --- | --- |
| Method scope | Route BA-CVA, SA-CVA, and mixed carve-out requests explicitly. | MAR50.8-MAR50.9. | `scope.py`, `test_cva_scope.py`, `test_cva_unsupported_features.py`. |
| Reduced BA-CVA | Portfolio formula aggregates counterparty SCVA terms with supervisory correlation. | MAR50.14-MAR50.16. | `ba_cva.py`, `test_cva_ba_cva_reduced.py`. |
| Full BA-CVA | Eligible hedge recognition and beta floor are applied only through typed hedge records. | MAR50.17-MAR50.26. | `ba_cva.py`, `hedges.py`, `test_cva_ba_cva_full.py`. |
| SA-CVA sensitivities | Weighted sensitivities use CVA and eligible hedge sensitivity inputs. | MAR50.47-MAR50.56. | `weighted_sensitivity.py`, `test_cva_weighted_sensitivity.py`. |
| SA-CVA aggregation | Bucket and risk-class capital use prescribed correlations and hedging-disallowance terms. | MAR50.53, MAR50.55-MAR50.57. | `aggregation.py`, `sa_cva.py`, `test_cva_aggregation.py`. |
| Risk classes | Risk-class modules keep bucket and correlation rules local to the class. | MAR50.54-MAR50.77. | `risk_classes/`, `tests/risk_classes/`. |
| Qualified indexes | Index bucket routing is explicit and metadata-driven. | MAR50.50, MAR50.63, MAR50.72. | `qualified_index.py`, `test_cva_qualified_index.py`. |

## Suitability

The formulas are suitable for the supported partial-runtime scope because they
preserve the key MAR50 capital drivers: BA-CVA counterparty aggregation,
eligible-hedge treatment, SA-CVA weighted sensitivities, intra-bucket and
inter-bucket aggregation, and method routing. Unsupported comparison profiles
and MAR50.9 fail before capital is emitted.
