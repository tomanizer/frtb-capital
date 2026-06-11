# frtb-result-store simplification audit

Date: 2026-06-04

## Scope

Append-only storage and query for calculation evidence. Not a capital package.

## Hotspot map

| Module | Lines (approx.) | Notes |
| --- | ---: | --- |
| `io.py` | 1291 | DuckDB/Parquet backend monolith |
| `model_entities.py` | 1091 | Entity graph |
| `marts.py` | 595 | Mart builders |
| `api.py` | 396 | Public API surface |
| `artifacts.py` | 423 | Artifact staging |

## Duplicated code

| Finding | Scope | Priority |
| --- | --- | --- |
| Good: widespread `stable_json_hash` / `stable_json_dumps` usage | — | positive |
| JSON column encode/decode patterns repeated across row IO | package-local | P2 |

## Dead or storage-only code

None flagged; catalog is derived state per ADR 0034 (documented).

## `frtb-common` candidates

Already uses common hashing appropriately.

## Package-local factoring candidates

- Split `io.py`: connection lifecycle, writes, reads/queries, manifest/checksum.
- Split `model_entities.py` by aggregate (run, capital tree, artifacts).
- Keep `api.py` thin over internal modules.

## Over-complexity

God modules make onboarding hard; no regulatory formula excuse for 1k+ line files.

## Wrappers and readability

Watch for API → IO one-liners; run `check_simplification_drift.py` after refactors.

## What must not move

Capital formulas, sibling capital imports, mutable run semantics.

## Recommended sequence

1. Map `io.py` responsibilities and split with tests unchanged.
2. Group entities by file with stable public imports.
3. Drift-check pass-through wrappers.

## Validation required

`test_result_store_public_api.py`, `test_duckdb_parquet_store.py`.

## Tracking

Consolidation: [#724](https://github.com/tomanizer/frtb-capital/issues/724) (ADR 0045 epic [#725](https://github.com/tomanizer/frtb-capital/issues/725)).
