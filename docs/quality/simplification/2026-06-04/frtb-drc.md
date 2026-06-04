# frtb-drc simplification audit

Date: 2026-06-04

## Scope

SA default risk charge. Issuer, securitisation, CTP, and HBR semantics remain here.

## Hotspot map

| Module | Lines (approx.) | Notes |
| --- | ---: | --- |
| `batch.py` | 2197 | Batch + hashing + arrays |
| `securitisation.py` | 903 | Sec non-CTP |
| `ctp.py` | 758 | CTP path |
| `regimes.py` | 674 | Profile matrix |
| `arrow_batch.py` | 518 | Arrow boundary |

## Duplicated code

| Finding | Scope | Priority |
| --- | --- | --- |
| `_slug` in eight modules | package-local | P1 |
| `_require_text` / citation merge scattered (SBM has `_text`/`_citations`; DRC does not) | package-local | P1 |
| Rejected-group + risk-weight helpers in batch/CTP/securitisation | package-local | P1 |
| Row vs batch duplicate capital-input helpers | package-local | P0 |
| `_hash_payload` local vs `stable_json_hash` | `frtb-common` | P1 |
| One-line `as_dict` repeats in `data_models.py` | package-local | P3 |

## Dead or storage-only code

`accepted_row_dataclasses_materialized` always 0 — storage-only metric (P2).

## `frtb-common` candidates

Hash, Arrow conversion, batch array coercion (ADR 0023 boundary).

## Package-local factoring candidates

`frtb_drc._ids`, `_text`, `_citations`; shared CTP/securitisation rejected-group module.

## Over-complexity

`batch.py` mirrors row path — extract shared primitives before rewriting kernels.

## Wrappers and readability

Many small hash payload builders (`risk_weight_evidence_hash_payload`) are fine
if kept next to domain types; avoid duplicating shape in batch and row paths.

## What must not move

Risk weights, netting, HBR, fair-value cap evidence, profile fail-closed rules.

## Recommended sequence

1. Decide fate of `accepted_row_dataclasses_materialized`.
2. Extract `_slug`, text, citations.
3. Shared CTP/securitisation helpers.
4. `stable_json_hash` migration.
5. Split `batch.py`.

## Validation required

DRC fixtures (non-sec v2, sec, CTP), Arrow batch, audit replay; Python 3.11 for hash gates.

## Tracking

GitHub issue: [#539](https://github.com/tomanizer/frtb-capital/issues/539)
