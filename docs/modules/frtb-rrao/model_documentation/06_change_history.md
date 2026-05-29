# Change History

This file records material `frtb-rrao` model-documentation history and points
to authoritative change logs.

## Authoritative Logs

- Suite changelog: [`CHANGELOG.md`](../../../../CHANGELOG.md)
- Package changelog: [`packages/frtb-rrao/CHANGELOG.md`](../../../../packages/frtb-rrao/CHANGELOG.md)
- ADRs: [`docs/decisions/`](../../../decisions/)
- Requirement registry: [`BASEL_FRTB_RRAO.yml`](../requirements/BASEL_FRTB_RRAO.yml)
- Regulatory traceability:
  [`REGULATORY_TRACEABILITY.md`](../../../../packages/frtb-rrao/docs/REGULATORY_TRACEABILITY.md)

## Material Model Changes

| Date | Change | Evidence | Model-risk note |
| --- | --- | --- | --- |
| 2026-05-29 | Added the v1 RRAO implementation across issues #80-#94 and PRs #95-#114. | `MODEL_DOCUMENTATION.md`, package tests, traceability docs. | Establishes implemented canonical-input mechanics for Basel, U.S. NPR, and EU comparison profiles. |
| 2026-05-29 | Added exact back-to-back match-group validation. | Issue #115; `RraoBackToBackMatch`; `tests/test_exclusions.py`. | Converts a cited exclusion from evidence-id-only to pair-level validation. |
| 2026-05-29 | Reconciled package metadata and v1 validation status. | Issue #116; `PACKAGE_METADATA`; `test_rrao_scaffold.py`. | Status applies only to scoped v1 canonical-input mechanics, not final regulatory approval. |
| 2026-05-29 | Added performance, comparator, property, mutation, public API, and reconciliation-tolerance evidence. | Issues #117, #121, #122, #123, #125; quality docs. | Strengthens engineering assurance without replacing independent validation. |
| 2026-05-29 | Added this formal model documentation pack. | Issue #120. | Gives validators a standalone evidence map and limitations statement. |

## Maintenance Rules

Record a change here when it:

- changes numerical output;
- changes regulatory profile support, risk weights, exclusions, or evidence
  requirements;
- changes replay payload, input hash, profile hash, or audit semantics;
- changes public API compatibility;
- changes documented limitations or validation evidence.
