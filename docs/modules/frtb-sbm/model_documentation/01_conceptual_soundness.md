# Conceptual Soundness

## Model Design

`frtb-sbm` keeps risk-engine responsibilities separate from capital assembly.
Upstream systems provide canonical sensitivities, source lineage, and any
sub-feature evidence. The package validates the inputs, applies Basel MAR21
risk weights and correlations, evaluates correlation scenarios, and emits
auditable capital records.

## Core Mechanics

| Mechanic | Conceptual basis | Regulatory anchor | Evidence |
| --- | --- | --- | --- |
| Delta weighting | Sensitivities are bucketed and risk-weighted before aggregation. | MAR21.8, MAR21.40-MAR21.89. | `weighted_sensitivity.py`, `tests/risk_classes/`, fixture packs. |
| Vega scaling | Vega uses prescribed liquidity horizons, option tenors, and risk-class rules. | MAR21.90-MAR21.95. | `weighted_sensitivity.py`, `risk_classes/vega.py`, vega tests. |
| Curvature branch selection | Curvature keeps separate up/down shock records and selects prescribed branch outcomes. | MAR21.5, MAR21.96-MAR21.101. | `curvature.py`, `test_curvature.py`, curvature batch/Arrow tests. |
| Intra-bucket aggregation | Bucket capital uses risk-class correlation matrices and floors. | MAR21.4 and risk-class paragraph tables. | `aggregation.py`, `test_sbm_aggregation.py`. |
| Inter-bucket scenarios | Low, medium, and high correlation scenarios are evaluated and the maximum capital is selected. | MAR21.6-MAR21.7. | `capital.py`, `test_sbm_correlation_scenarios.py`. |
| Audit/replay | Results carry deterministic hashes, reconciliation metadata, and branch records. | ADR 0012; SBM-FUNC-022. | `audit.py`, `replay.py`, audit/replay tests. |

## Suitability

The implementation is suitable for the supported partial-runtime scope because
it preserves the main MAR21 capital drivers: risk-class bucket assignment,
weighted sensitivities, intra-bucket aggregation, inter-bucket correlation
scenarios, curvature branch records, and fail-closed unsupported behavior.
