# Change History

This file records material `frtb-ima` model-documentation history and points to
the authoritative change logs. It is maintained manually until audit issue #16
defines the full material-change control workflow.

## Authoritative Logs

- Suite release notes:
  [`CHANGELOG.md`](../../../CHANGELOG.md)
- Package release notes:
  [`packages/frtb-ima/CHANGELOG.md`](../../../packages/frtb-ima/CHANGELOG.md)
- ADRs:
  [`docs/decisions/`](../../decisions/)
- IMA regulatory traceability:
  [`REGULATORY_TRACEABILITY.md`](../../../packages/frtb-ima/docs/REGULATORY_TRACEABILITY.md)
- IMA assumptions:
  [`REGULATORY_ASSUMPTIONS.md`](../../../packages/frtb-ima/docs/REGULATORY_ASSUMPTIONS.md)

## Material Model Changes

| Date | Change | Evidence | Model-risk note |
| --- | --- | --- | --- |
| 2026-05-28 | Migrated `frtb-ima` into the `frtb-capital` monorepo with full git history. | Root and package changelogs; ADR 0002. | No calculation logic changed during bootstrap; package boundary changed. |
| 2026-05-28 | Added explicit expected shortfall estimator selection with weighted interpolation as policy default. | ADR 0004; package changelog; reference-vector tests. | Material estimator convention. Requires validation sign-off before production use. |
| 2026-05-28 | Added policy citation metadata and removed uncited numeric defaults from lower-level helpers. | Package changelog; `RegulatoryPolicy.cited_by`; traceability docs. | Strengthens audit traceability for numeric thresholds. |
| 2026-05-28 | Added deterministic input hashing and version identity to audit records and validation-pack reports. | Package changelog; audit tests; validation-pack docs. | Improves reproducibility evidence and run identity controls. |
| 2026-05-28 | Added reduced risk-factor set selection, Hypothesis properties, mutation baseline, coverage floor, and independent reference vectors. | Root and package changelogs; quality docs; PR history. | Expands numerical assurance; does not by itself complete independent validation. |
| 2026-05-28 | Added this formal model documentation pack scaffold. | Issue #15; root changelog. | Establishes SR 11-7 / PRA SS 1/23 documentation structure for future validation evidence. |

## Maintenance Rules

Record a change here when it:

- changes numerical output;
- changes policy parameters, thresholds, estimator conventions, or regulatory
  interpretation;
- changes supported package boundaries or requirement status;
- changes reproducibility, audit-record, or validation-pack semantics;
- adds, removes, or reclassifies a material limitation.

Each entry should link to the ADR, PR, issue, release note, and validation
evidence when those exist.
