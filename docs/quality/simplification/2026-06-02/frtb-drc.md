# frtb-drc simplification audit

## Scope

`frtb-drc` owns SA default risk charge. It must preserve explicit unsupported
boundaries for profiles and paths not yet implemented and must keep issuer,
seniority, securitisation, CTP, and HBR semantics package-local.

## Hotspot map

| Module | Lines | Notes |
| --- | ---: | --- |
| `batch.py` | 2414 | Batch path, context handling, hashing, and array helpers. |
| `securitisation.py` | 903 | Securitisation non-CTP path. |
| `ctp.py` | 758 | CTP path. |
| `demo_data.py` | 715 | Synthetic demo data. |
| `regimes.py` | 674 | Rule profiles and support matrix. |
| `data_models.py` | 674 | Frozen domain records. |
| `reference_data.py` | 607 | Risk weights and bucket definitions. |
| `arrow_handoff.py` | 518 | Arrow-to-batch boundary. |
| `scaffold.py` | 499 | Row calculation orchestration. |

## Duplicated code

- `_slug` appears in eight modules.
- `_require_text`, `_optional_text`, `_require_finite_non_negative`, and
  `_merge_citations` repeat across CTP, securitisation, FX, fair-value-cap, and
  risk-weight evidence modules.
- `_bounded_rejected_group_offsets` is repeated across batch, CTP, and
  securitisation paths.
- `_risk_weights_for_net_jtd` repeats in batch, CTP, and securitisation.
- Batch and row paths duplicate helpers for `_capital_inputs`,
  `_credit_quality_for_net_jtd`, netting-like state consumption, and branch
  citations.
- `data_models.py` has many identical one-line `as_dict` implementations.
- Arrow and batch array helpers duplicate suite-wide mechanics.
- Context/input hashing appears in audit, batch, FX, CTP, securitisation, and
  regimes.

## Dead or storage-only code

- `accepted_row_dataclasses_materialized` is always set to `0` in DRC batch
  calculations and tests assert zero. Treat it as a storage-only performance
  metric unless future DRC paths materialize accepted dataclasses.
- Demo fixture `_read_json` and `_sha256` duplicate IMA fixture helpers but are
  low-risk and not urgent.

## `frtb-common` candidates

- Stable hash helpers and SHA256 validation.
- Arrow conversion helpers.
- Batch array coercion helpers.
- Source-file hashing for fixture utilities, if enough packages use it.

## Package-local factoring candidates

- Add `frtb_drc._text` or `_validation_utils` for repeated text/finite checks.
- Add `frtb_drc._citations` for merge helpers.
- Add `frtb_drc._ids` for `_slug`.
- Add shared package-local rejected-group and risk-weight-context helpers for
  CTP, securitisation, and batch.
- Consider an `as_dict` mixin or common local payload helper for DRC dataclasses.

## Over-complexity

- `batch.py` mirrors significant row-path behavior. The safest simplification is
  to extract shared DRC-local primitives first, not to rewrite the calculation
  path.
- CTP and securitisation share rejected-group and risk-weight evidence patterns.
  A local module can reduce duplication while preserving separate regulatory
  branches.
- `regimes.py` is large because it records unsupported boundaries. Keep those
  explicit.

## What must not move

Do not move DRC risk weights, maturity scaling semantics, issuer aggregation,
seniority netting, HBR ratio logic, securitisation/CTP profile behavior,
fair-value-cap evidence, or unsupported-profile decisions into `frtb-common`.

## Recommended sequence

1. Decide whether `accepted_row_dataclasses_materialized` should remain in DRC.
2. Extract `_slug`, text/finite validation, and citation merging locally.
3. Extract shared CTP/securitisation rejected-group and risk-weight helpers.
4. Migrate hash and Arrow helpers through future `frtb-common` utilities.
5. Split `batch.py` after shared local helpers exist.

## Validation required

- DRC package tests for non-securitisation, securitisation non-CTP, CTP, FX,
  fair-value cap, risk-weight evidence, audit, Arrow batch, and replay.
- Fixture hash gates must be checked with Python 3.11.
- `make quality-control`.

