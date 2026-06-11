# frtb-cva simplification audit

Date: 2026-06-04 (updated 2026-06-11 for batch split)

## Scope

CVA capital (BA-CVA, SA-CVA, mixed carve-out). Regulatory formulas and profile
semantics stay package-local.

## Hotspot map

| Module | Lines (approx.) | Notes |
| --- | ---: | --- |
| `_batch_*` modules (total) | ~3200 | Informal stage split landed |
| `batch.py` | 46 | Public compatibility facade (re-exports) |
| `reference_data.py` | 1146 | Profiles and tables |
| `sa_cva_reference_data.py` | 1032 | SA-CVA weights |
| `arrow_batch.py` | 398 | Arrow boundary |
| `audit.py` | — | Reconciliation (partially staged) |

## Duplicated code

| Finding | Scope | Priority |
| --- | --- | --- |
| `_hash_payload` via `_payloads.hash_payload` → `stable_json_hash` | package-local | done |
| Context/counterparty/hedge/sensitivity payloads | package-local | done (`_payloads.py`) |
| `_merge_citations`, `_profile_warnings` in capital + batch | package-local | done (`_citations.py`, `_profile_warnings.py`) |
| `_hedge_risk_weight` in BA-CVA + batch | package-local | P2 |

## Dead or storage-only code

No dead runtime paths. Keep impact/attribution explicitly unsupported.

## `frtb-common` candidates

Arrow/batch array helpers at handoff boundary.

## Package-local factoring candidates

- Rename `_batch_*` modules to ADR 0045 stage directories (`adapters/`, `validation/`, `kernel/`, `assembly/`).
- Add `registry.py` for entity-type dispatch.
- Collapse `_ba_batch_kernel.py` re-export shim if no longer needed.

## Over-complexity

Stage logic is navigable across `_batch_*` modules; remaining cost is naming
alignment with ADR 0045 and registry collapse.

## Wrappers and readability

SA-CVA risk-class micro-closures (`_gamma`, `_intra`) — collapse to table-driven
helpers inside package.

## What must not move

MAR50 profiles, BA-CVA/SA-CVA formulas, hedge eligibility, carve-out rules.

## Recommended sequence

1. ~~Unify payloads + hashes (tests first).~~ done
2. ~~Extract citations/warnings helpers.~~ done
3. ~~Migrate to `stable_json_hash`.~~ done
4. Rename informal `_batch_*` split to ADR 0045 stage layout; add registry.

## Validation required

CVA public API, BA/SA fixtures, Arrow batch, hash compatibility tests; `make quality-control`.

## Tracking

Consolidation: [#719](https://github.com/tomanizer/frtb-capital/issues/719) (ADR 0045 epic [#725](https://github.com/tomanizer/frtb-capital/issues/725)).
