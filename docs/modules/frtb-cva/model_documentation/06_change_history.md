# Change History

| Date | Change | Evidence |
| --- | --- | --- |
| 2026-06-03 | Added formal CVA model-documentation pack covering intended use, conceptual soundness, derivation, assumptions, validation evidence, monitoring, and change history. | Issue #410; `docs/modules/MODEL_DOCUMENTATION_PROMOTION_PLAN.md`. |
| 2026-05 to 2026-06 | Expanded partial runtime to reduced/full BA-CVA, supported SA-CVA delta/vega paths, mixed carve-out, qualified-index routing, and audit/replay helpers. | `docs/modules/frtb-cva/DECISIONS_AND_PLAN.md`; `packages/frtb-cva/docs/REGULATORY_TRACEABILITY.md`. |
| Earlier phase | Established CVA planning documents, requirements registry, public API, and fixture workflows. | `docs/modules/frtb-cva/README.md`; `packages/frtb-cva/docs/requirements/BASEL_FRTB_CVA.yml`. |

Material numerical changes require deterministic tests and an ADR when they
change regulatory interpretation, package boundaries, or audit/result contracts.
