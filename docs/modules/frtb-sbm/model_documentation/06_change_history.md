# Change History

| Date | Change | Evidence |
| --- | --- | --- |
| 2026-06-03 | Added formal SBM model-documentation pack and direct attribution/impact unsupported tests. | Issue #410; `packages/frtb-sbm/tests/test_sbm_attribution_impact.py`. |
| 2026-05 to 2026-06 | Expanded partial runtime to the supported Basel MAR21 delta, vega, curvature, batch, Arrow, and adapter matrix. | `packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md`; `docs/modules/frtb-sbm/DECISIONS_AND_PLAN.md`. |
| Earlier phase | Established GIRR delta vertical slice, public API, audit/replay, and fixture workflows. | `docs/modules/frtb-sbm/README.md`; `docs/modules/frtb-sbm/requirements/BASEL_FRTB_SBM.yml`. |

Material changes to capital formulas, supported profiles, audit/result
contracts, or attribution/impact behavior require deterministic tests and an
ADR when they change regulatory interpretation or package boundaries.
