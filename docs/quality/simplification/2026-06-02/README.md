# 2026-06-02 simplification audit summary

This is an audit-only simplification run. It records repeatable evidence and
follow-up recommendations; it does not change runtime code.

Guard result: `python3 scripts/agent_worktree.py guard` passed in a compliant
agent worktree on branch `codex/simplification-audit`.

## Reports

- [`frtb-common`](frtb-common.md)
- [`frtb-ima`](frtb-ima.md)
- [`frtb-sbm`](frtb-sbm.md)
- [`frtb-drc`](frtb-drc.md)
- [`frtb-rrao`](frtb-rrao.md)
- [`frtb-cva`](frtb-cva.md)
- [`frtb-orchestration`](frtb-orchestration.md)
- [`batch-array-coercion-assessment`](batch-array-coercion-assessment.md)
- [`arrow-conversion-migration`](arrow-conversion-migration.md)
- [`hash-migration-plan`](hash-migration-plan.md)

## Suite-level findings

| Priority | Scope | Finding | First follow-up |
| --- | --- | --- | --- |
| P0 | audit-only | Several packages carry parallel row/batch or audit/batch implementations of the same payload and validation concepts. This is the main drift risk. | Add regression tests around hashes, accepted/rejected row counts, and capital totals before consolidation. |
| P1 | `frtb-common` | Deterministic JSON hashing is duplicated in SBM, DRC, RRAO, CVA, IMA, and `frtb-common` handoff helpers. Implementations differ in whether they call `jsonable`. | Design `frtb_common.stable_hash` with shared tests; migrate package helpers one package at a time. |
| P1 | `frtb-common` | Arrow object/float/bool conversion helpers are repeated in SBM, DRC, RRAO, CVA, and IMA handoff modules. | Add package-neutral Arrow conversion utilities under `frtb_common.handoff` or a new handoff submodule. |
| P1 | `frtb-common` | Batch array coercion helpers repeat across RRAO, DRC, and CVA (`_required_text_array`, `_optional_text_array`, `_readonly_array`, `_object_array`, enum/float/bool coercers). | Add a small `frtb_common.batch_arrays` candidate only if ADR 0023 boundaries are preserved. |
| P1 | package-local | SBM, DRC, RRAO, and CVA have repeated private citation, profile-warning, context, and payload helpers inside each package. | Extract package-local internal helpers before suite-wide abstractions. |
| P2 | package-local | Large monoliths are concentrated in `batch.py`, `arrow_handoff.py`, capital, and reference-data modules. | Split by mechanics, validation, kernel, and result assembly while preserving public entrypoints. |
| P2 | audit-only | `accepted_row_dataclasses_materialized` is meaningful in SBM but appears storage-only in DRC and RRAO, where tests assert it stays zero. | Decide whether it is a suite-wide performance metric or remove/defer it in packages that never materialize rows. |

## Important boundary constraints

- ADR 0019 already decided not to extract reconciliation helpers yet. Keep
  package-local reconciliation validation unless that ADR is updated.
- ADR 0023 allows Arrow in handoff and adapter layers, not in calculation
  kernels. Shared Arrow helpers must remain at the handoff boundary.
- `frtb-common` must not import capital packages or carry component-specific
  regulatory semantics.
- One package per implementation PR remains the default. Cross-package common
  extraction should land as a shared-library PR first, then package migrations.

## Recommended implementation order

1. Add shared deterministic hash and SHA256 validation helpers in `frtb-common`
   if maintainers accept the boundary. Migrate audit/batch/regime helpers one
   package at a time.
2. Add shared Arrow conversion helpers for package handoff modules. Keep
   package-specific schemas and semantic interpretation local.
3. Extract package-local internal helpers in RRAO, DRC, CVA, and SBM. Start
   with exact duplicate helpers before changing calculation flow.
4. Split the largest `batch.py` modules into array coercion, validation, kernel,
   and result assembly modules.
5. Revisit row-vs-batch validation and calculation duplication after regression
   tests prove hash, total, warning, and lineage compatibility.

## Evidence commands

The audit used line-count scans, targeted `rg` searches for duplicated helper
patterns, placeholder searches, package-boundary import searches, and an
AST-based exact duplicate private-function scan.
