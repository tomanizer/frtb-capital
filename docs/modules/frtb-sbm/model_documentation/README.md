# FRTB-SBM Model Documentation Pack

This pack documents the current partial-runtime `frtb-sbm` scope for model
validation, engineering review, and audit planning. Package-local traceability
remains under `packages/frtb-sbm/docs/`.

Outputs are synthetic validation and engineering evidence for supported Basel
MAR21 paths. They are not final regulatory capital.

## Contents

| Section | Purpose |
| --- | --- |
| [`00_intended_use.md`](00_intended_use.md) | Intended use, supported slices, and exclusions. |
| [`01_conceptual_soundness.md`](01_conceptual_soundness.md) | Conceptual basis and paragraph-level regulatory anchors. |
| [`02_derivation.md`](02_derivation.md) | Delta, vega, curvature, scenario, and audit derivation summary. |
| [`03_assumptions_and_limitations.md`](03_assumptions_and_limitations.md) | Risk-class scope matrix and unsupported paths. |
| [`04_validation_evidence.md`](04_validation_evidence.md) | Fixture, benchmark, and fail-closed evidence. |
| [`05_monitoring_plan.md`](05_monitoring_plan.md) | CI, drift, and change-review monitoring plan. |
| [`06_change_history.md`](06_change_history.md) | Model-documentation and material-change history. |
