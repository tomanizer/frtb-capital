# frtb-common simplification audit

Date: 2026-06-04

## Scope

Shared package-neutral primitives (hashing, Arrow handoff, CRIF, component
summaries). Must not absorb capital-component regulatory semantics.

## Hotspot map

| Module | Lines (approx.) | Notes |
| --- | ---: | --- |
| `frtb_common/crif.py` | 1211 | CRIF normalization |
| `frtb_common/arrow_table.py` | 438 | Handoff + table hash |
| `frtb_common/arrow_conversion.py` | — | Shared Arrow primitives |
| `frtb_common/batch_arrays.py` | — | Batch coercion |
| `frtb_common/hashing.py` | 46 | `stable_json_hash` — underused by capital pkgs |

## Duplicated code

| Finding | Scope | Priority |
| --- | --- | --- |
| Capital packages reimplement `_hash_payload` instead of `stable_json_hash` | `frtb-common` + consumers | P1 |
| Arrow conversion duplicated in SBM/DRC/RRAO/CVA handoff layers | `frtb-common` | P1 |

## Dead or storage-only code

None identified in common itself.

## `frtb-common` candidates

Add or promote (with tests): stable hash, SHA256 validation, Arrow column readers,
batch array coercion — only where behavior matches across three+ packages.

## Package-local factoring candidates

Split `crif.py` into schema / coercion / diagnostics if it grows past ~1500 LOC.

## Over-complexity

Risk is scope creep: every “small shared helper” request lands here. Reject
regulatory semantics at review.

## Wrappers and readability

Keep specialized exports in submodules; avoid bloating `frtb_common.__init__`.

## What must not move

Component risk weights, buckets, profiles, capital lines, unsupported-feature
policy.

## Recommended sequence

1. Document migration guide from `_hash_payload` to `stable_json_hash`
   ([hash-migration-guide.md](hash-migration-guide.md)).
2. Add Arrow helper tests mirroring one package’s null/chunk behavior.
3. Split `crif.py` only when a fourth major CRIF feature lands.

## Validation required

`packages/frtb-common/tests`; consumer hash tests after each migration.

## Tracking

Consolidation: [#714](https://github.com/tomanizer/frtb-capital/issues/714), [#722](https://github.com/tomanizer/frtb-capital/issues/722) (ADR 0045 epic [#725](https://github.com/tomanizer/frtb-capital/issues/725)).
