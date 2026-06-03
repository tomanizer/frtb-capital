# FRTB-CVA Model Documentation Pack

This pack documents the current partial-runtime `frtb-cva` scope for model
validation, engineering review, and audit planning. It complements the planning
documents under `docs/modules/frtb-cva/` and package evidence under
`packages/frtb-cva/docs/`.

Outputs are synthetic validation and engineering evidence for supported Basel
MAR50 paths. They are not final regulatory capital.

## Contents

| Section | Purpose |
| --- | --- |
| [`00_intended_use.md`](00_intended_use.md) | Intended use, supported paths, and out-of-scope uses. |
| [`01_conceptual_soundness.md`](01_conceptual_soundness.md) | Conceptual basis and paragraph-level regulatory anchors. |
| [`02_derivation.md`](02_derivation.md) | BA-CVA, SA-CVA, hedge, and mixed-method derivation summary. |
| [`03_assumptions_and_limitations.md`](03_assumptions_and_limitations.md) | Unsupported paths and validation limits. |
| [`04_validation_evidence.md`](04_validation_evidence.md) | Fixture, property, public API, and comparator evidence. |
| [`05_monitoring_plan.md`](05_monitoring_plan.md) | CI, drift, and change-review monitoring plan. |
| [`06_change_history.md`](06_change_history.md) | Model-documentation and material-change history. |
