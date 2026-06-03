# frtb-rrao simplification audit

## Scope

`frtb-rrao` owns residual risk add-on capital. It has a v1 canonical-input path
for Basel MAR23, U.S. NPR 2.0 proposed section `__.211`, and EU CRR3 Article
325u comparison behavior. Unsupported profiles and ambiguous evidence must fail
closed.

## Hotspot map

| Module | Lines | Notes |
| --- | ---: | --- |
| `batch.py` | 1695 | Batch validation, classification, hashing, and result assembly. |
| `reference_data.py` | 781 | Citations, evidence rules, exclusions, and risk weights. |
| `crif.py` | 649 | CRIF/FNet adapter. |
| `arrow_batch.py` | 522 | Arrow-to-batch bridge. |
| `validation.py` | 517 | Dataclass validation. |
| `data_models.py` | 320 | Frozen types/enums. |
| `audit.py` | 274 | Serialization, hashing, reconciliation. |
| `allocation.py` | 234 | Additive allocation reports. |

## Duplicated code

- `_merged_citation_ids` is duplicated in `capital.py`, `classification.py`, and
  `batch.py`.
- `_hash_payload` appears in `audit.py`, `batch.py`, and `regimes.py` with
  slightly different `jsonable` behavior.
- Result assembly helpers are duplicated between `scaffold.py` and `batch.py`:
  `_validate_context`, `_partition_lines`, `_collect_line_citations`, and
  `_profile_warnings`.
- `_position_payload` and `_investment_fund_descriptor_payload` are duplicated
  between audit and batch hashing paths.
- Batch validation reimplements dataclass validation for evidence requirements,
  back-to-back match groups, exact back-to-back pairs, and investment-fund
  fields.
- The batch kernel reimplements classification and capital-line logic instead
  of reusing the dataclass path.
- Basel and U.S. NPR reference-data evidence rules repeat the same "other
  residual" evidence-type tuples with profile-specific citations.

## Dead or storage-only code

- Optional position fields such as `underlying_count`,
  `is_path_dependent`, `has_maturity`, `has_strike_or_barrier`,
  `has_multiple_strikes_or_barriers`, and `is_ctp_hedge` are validated, stored,
  serialized, and hashed but not currently used by classification or capital.
- `accepted_row_dataclasses_materialized` is always zero in RRAO batch and Arrow
  paths and tests assert zero.
- `build_rrao_capital_lines`, `resolve_rrao_profile`, and
  `profile_content_hash` are mostly test-facing or internal; decide whether
  they should remain intentionally non-public.

## `frtb-common` candidates

- Stable hash helpers and SHA256 validation.
- Arrow conversion helpers.
- Batch array coercion helpers.
- CRIF normalization should continue moving toward `frtb_common.crif` with an
  RRAO-specific risk-type mapper, not package-local alias logic.

## Package-local factoring candidates

- Add `frtb_rrao._internal` or narrower modules for citation merge, result
  partitioning, profile warnings, context validation, and payload hashing.
- Add a shared validation-rules module used by both dataclass and batch paths.
- Add small reference-data factory helpers for repeated evidence-rule tables.
- Add a generic package-local grouper for subtotal and allocation grouping if it
  can keep output shapes explicit.

## Over-complexity

- The biggest structural complexity is the dual business-logic path:
  dataclass validation/classification/capital versus vectorized batch
  validation/classification/capital.
- `batch.py` should be split into arrays, validation, classification/kernel, and
  result assembly even if deeper unification is deferred.
- The optional structural fields need a product decision: wire them into cited
  auto-classification behavior or remove/defer them from the canonical schema.

## What must not move

Do not move evidence classifications, exclusion reasons, investment-fund logic,
profile risk weights, citations, RRAO capital result semantics, or allocation
semantics into `frtb-common`.

## Recommended sequence

1. Extract exact duplicated helpers locally.
2. Unify hash and position payload construction.
3. DRY reference-data table builders.
4. Share validation rules between dataclass and batch paths.
5. Decide the fate of storage-only structural fields.
6. Rework CRIF through `frtb_common.crif` with RRAO-specific mapping.
7. Revisit a single calculation kernel only after regression tests are stable.

## Validation required

- RRAO capital, validation, audit, allocation, Arrow batch, CRIF, handoff, and
  performance-control tests.
- Hash compatibility tests between dataclass and batch inputs before and after
  any hashing refactor.
- `make quality-control`.

