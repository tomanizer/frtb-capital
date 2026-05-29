# FRTB-RRAO Model Documentation Pack

This pack records the model-documentation evidence for the `frtb-rrao` residual
risk add-on component. It is written for engineering review, model validation
planning, and audit-readiness review.

This is not a regulatory report. U.S. NPR 2.0 references are proposed-rule
material, and no output from this package should be described as final
regulatory capital without legal, risk, model-validation, and supervisory
review.

## Contents

| Section | Purpose |
| --- | --- |
| [`00_intended_use.md`](00_intended_use.md) | Purpose, users, scope, and out-of-scope boundary. |
| [`01_conceptual_soundness.md`](01_conceptual_soundness.md) | Design rationale and regulatory anchors. |
| [`02_methodology_and_derivation.md`](02_methodology_and_derivation.md) | Formula and classification methodology. |
| [`03_inputs_outputs_lineage.md`](03_inputs_outputs_lineage.md) | Canonical input, output, lineage, and audit records. |
| [`04_validation_evidence.md`](04_validation_evidence.md) | Fixtures, replay, comparator, property, mutation, and reconciliation evidence. |
| [`05_assumptions_limitations_monitoring.md`](05_assumptions_limitations_monitoring.md) | Assumptions, limitations, monitoring, and change control. |
| [`06_change_history.md`](06_change_history.md) | Material documentation and implementation history. |

## Primary Evidence

- [`REGULATORY_TRACEABILITY.md`](../../../../packages/frtb-rrao/docs/REGULATORY_TRACEABILITY.md)
  is the bidirectional code-to-regulation map.
- [`REGULATORY_ASSUMPTIONS.md`](../../../../packages/frtb-rrao/docs/REGULATORY_ASSUMPTIONS.md)
  records source-cited boundaries and limitations.
- [`BASEL_FRTB_RRAO.yml`](../requirements/BASEL_FRTB_RRAO.yml) is the
  machine-readable requirement inventory.
- [`PUBLIC_API.md`](../PUBLIC_API.md) defines the stable v1 top-level import
  surface.
- [`PERFORMANCE.md`](../../../../packages/frtb-rrao/docs/PERFORMANCE.md)
  records deterministic benchmark and replay hashes.

Open limitations in this pack are explicit validation tasks, not hidden claims
of completeness.
