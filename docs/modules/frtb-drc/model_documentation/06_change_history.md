# Change History

| Date | Change | Evidence |
| --- | --- | --- |
| 2026-06-03 | Completed DRC model-documentation sections for conceptual soundness, derivation, assumptions/limitations, validation evidence, monitoring, and change history. | Issue #410; `docs/modules/MODEL_DOCUMENTATION_PROMOTION_PLAN.md`. |
| 2026-05 to 2026-06 | Expanded partial runtime beyond the original non-securitisation slice to include U.S. NPR 2.0 securitisation non-CTP and CTP row/batch paths plus Basel MAR22 non-securitisation row/batch paths. | `docs/modules/frtb-drc/DECISIONS_AND_PLAN.md`; package tests under `packages/frtb-drc/tests/`. |
| Earlier phase | Established the DRC planning pack, public API, requirements registry, synthetic fixtures, audit/replay, and explicit unsupported gates. | `docs/modules/frtb-drc/README.md`; `packages/frtb-drc/docs/requirements/BASEL_FRTB_DRC.yml`. |

Material changes to capital formulas, profile scope, attribution methods, or
audit/result contracts require an ADR or an explicit update to the package
planning documents before promotion to a higher maturity profile.
