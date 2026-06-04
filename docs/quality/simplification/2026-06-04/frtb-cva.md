# frtb-cva simplification audit

Date: 2026-06-04

## Scope

CVA capital (BA-CVA, SA-CVA, mixed carve-out). Regulatory formulas and profile
semantics stay package-local.

## Hotspot map

| Module | Lines (approx.) | Notes |
| --- | ---: | --- |
| `batch.py` | 2390 | Largest monolith; down from ~2814 |
| `reference_data.py` | 779 | Profiles and tables |
| `sa_cva_reference_data.py` | 625 | SA-CVA weights |
| `arrow_batch.py` | 612 | Arrow boundary |
| `audit.py` | 556 | Reconciliation (partially staged) |

## Duplicated code

| Finding | Scope | Priority |
| --- | --- | --- |
| `_hash_payload` in `audit.py` and `batch.py` | package-local | P0 |
| Context/counterparty/hedge/sensitivity payloads duplicated audit vs batch | package-local | P1 |
| `_merge_citations`, `_profile_warnings` in capital + batch | package-local | P1 |
| `_hedge_risk_weight` in BA-CVA + batch | package-local | P2 |

## Dead or storage-only code

No dead runtime paths. Keep impact/attribution explicitly unsupported.

## `frtb-common` candidates

`stable_json_hash`; Arrow/batch array helpers at handoff boundary.

## Package-local factoring candidates

- `frtb_cva._payloads` — single source for audit/batch hash inputs.
- `frtb_cva._citations` — merge helpers.
- Split `batch.py`: schema/arrays, validation, BA kernel, SA kernel, assembly.

## Over-complexity

`batch.py` mixes unrelated concerns; hardest file to review in suite.

## Wrappers and readability

SA-CVA risk-class micro-closures (`_gamma`, `_intra`) — collapse to table-driven
helpers inside package.

## What must not move

MAR50 profiles, BA-CVA/SA-CVA formulas, hedge eligibility, carve-out rules.

## Recommended sequence

1. Unify payloads + hashes (tests first).
2. Extract citations/warnings helpers.
3. Migrate to `stable_json_hash`.
4. Split `batch.py`.

## Validation required

CVA public API, BA/SA fixtures, Arrow batch, hash compatibility tests; `make quality-control`.

## Tracking

GitHub issue: [#538](https://github.com/tomanizer/frtb-capital/issues/538)
