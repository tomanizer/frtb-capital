# FRTB-IMA Model Documentation Pack

This is the suite-level model documentation pack for the `frtb-ima` package.
It is written for model validation, engineering review, and audit planning. The
supporting implementation evidence remains in
[`packages/frtb-ima/docs/`](../../../packages/frtb-ima/docs/) and the executed
validation notebooks remain in
[`packages/frtb-ima/notebooks/`](../../../packages/frtb-ima/notebooks/).

This pack is not a regulatory report. U.S. NPR 2.0 references are proposed-rule
material, and no output from this package should be described as final
regulatory capital without legal, risk, model-validation, and supervisory
review.

## Contents

| Section | Purpose |
| --- | --- |
| [`00_intended_use.md`](00_intended_use.md) | Model purpose, boundaries, users, desks, instruments, and exclusions. |
| [`01_conceptual_soundness.md`](01_conceptual_soundness.md) | Rationale for the IMA component design and its regulatory anchors. |
| [`02_derivation.md`](02_derivation.md) | Formula derivations for ES, LHA ES, IMCC, SES, PLA, backtesting, and capital assembly. |
| [`03_assumptions_and_limitations.md`](03_assumptions_and_limitations.md) | Modelling choices, package boundaries, limitations, and open validation gaps. |
| [`04_sensitivity_analysis.md`](04_sensitivity_analysis.md) | Planned validation sensitivity analyses and parameter perturbations. |
| [`05_monitoring_plan.md`](05_monitoring_plan.md) | Operational monitoring, breach response, and evidence cadence. |
| [`06_change_history.md`](06_change_history.md) | Material model-change log and links to ADR, release, and audit history. |

## Primary Evidence

- [`REGULATORY_TRACEABILITY.md`](../../../packages/frtb-ima/docs/REGULATORY_TRACEABILITY.md)
  maps code to Basel MAR31-MAR33, U.S. NPR 2.0 proposed sections, and EU
  CRR/RTS comparison anchors.
- [`REGULATORY_ASSUMPTIONS.md`](../../../packages/frtb-ima/docs/REGULATORY_ASSUMPTIONS.md)
  records the documented modelling basis, deliberate exclusions, and recent
  accuracy-audit corrections.
- [`NPR_2_0_MARKET_RISK.yml`](../../../packages/frtb-ima/docs/requirements/NPR_2_0_MARKET_RISK.yml)
  is the machine-readable requirement inventory and implementation-status map.
- [`VALIDATION_PACK.md`](../../../packages/frtb-ima/docs/VALIDATION_PACK.md)
  explains the deterministic notebook-backed review bundle for the
  `capital_run_v1` synthetic fixture.
- [`DATASET_CONTRACT.md`](../../../packages/frtb-ima/docs/DATASET_CONTRACT.md)
  describes the committed synthetic fixture, sign conventions, golden outputs,
  and regeneration rules.

## How To Read The Pack

Start with intended use and limitations, then read conceptual soundness and
derivation together. Use the traceability and requirements documents as the
source of record for regulatory anchors and implementation status. Use the
validation-pack documentation and notebooks to inspect deterministic evidence
for the committed synthetic fixture.

Open items in this pack are explicit validation tasks. They are not hidden
claims of completeness.
