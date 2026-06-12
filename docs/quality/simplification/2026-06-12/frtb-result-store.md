# frtb-result-store simplification audit

Date: 2026-06-12  
Audit-only - no runtime code changes in this report.

## Scope

`frtb-result-store` owns storage and serving infrastructure for immutable run artifacts, DuckDB/Parquet persistence, row codecs, marts, and APIs. It is not a capital calculation package.

## Hotspot map

| Module | Lines (approx.) | Notes |
| --- | ---: | --- |
| `frtb_result_store/artifacts.py` | 466 | Largest runtime module; below audit threshold. |
| `frtb_result_store/api.py` | 447 | Route registration and API helpers. |
| `frtb_result_store/_model_run_records.py` | 374 | Model records. |
| `frtb_result_store/capital_graph.py` | 343 | Capital graph identity and edges. |

## Duplicated code

- One mixed duplicate group includes `_RouteRegistrar.get`; this is low signal because the group also matches SBM property accessors.

## Dead or storage-only code

- No high-confidence dead-code finding in the changed-code dead-code guard.

## `frtb-common` candidates

| Finding | Scope | Priority |
| --- | --- | --- |
| None from this audit | audit-only | P3 |

## Package-local factoring candidates

- Continue result-store IO/mart splits only when they clarify storage lifecycle or query ownership; no urgent P1 from current size metrics.

## Over-complexity

- `capital_node_identity_payload` remains a large function and should be watched before new identity fields are added.

## Wrappers and readability

- Prior row-codec and mart split work left small compatibility modules. Keep those shims until a dedicated public surface trim.

## What must not move

- Storage schema evolution, artifact identity, DuckDB/Parquet IO, and serving API concerns remain result-store-owned.

## Recommended sequence

1. No immediate #850 follow-up beyond drift monitoring.
2. Reassess if `api.py`, `artifacts.py`, or IO query modules cross 500 LOC.

## Validation required

- `uv run pytest packages/frtb-result-store/tests`
- `make quality-control`

## Tracking

GitHub issue: none opened from this audit.
