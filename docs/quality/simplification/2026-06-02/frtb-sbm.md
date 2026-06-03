# frtb-sbm simplification audit

## Scope

`frtb-sbm` owns Sensitivities-Based Method capital. SA composition remains in
`frtb-orchestration`; DRC, RRAO, CVA, and IMA logic must not be imported here.

## Hotspot map

| Module | Lines | Notes |
| --- | ---: | --- |
| `batch.py` | 2503 | Batch construction, hashing, dispatch, and array helpers. |
| `arrow_batch.py` | 1951 | Large Arrow-to-batch boundary. |
| `curvature.py` | 1897 | Curvature calculation and unsupported-feature branches. |
| `capital.py` | 1759 | Portfolio/risk-class capital assembly. |
| `reference_data.py` | 1599 | GIRR and generic reference data. |
| `weighted_sensitivity.py` | 1429 | Risk-class weighting dispatch. |
| `aggregation.py` | 1043 | Scenario aggregation and correlations. |
| `crif.py` | 994 | CRIF adapter. |
| `validation.py` | 800 | Sensitivity validation and unsupported guards. |

## Duplicated code

- `_require_text` has exact duplicate bodies in six reference-data modules and
  near-duplicates in validation, weighted-sensitivity, and vega modules.
- `_merge_citation_ids` appears in aggregation, curvature, factor-grid,
  reference-data, weighted-sensitivity, and vega modules.
- `_hash_payload` is duplicated between audit and regimes.
- `_batch_text_by_id` appears in batch, capital, and vega modules; risk-class
  modules also reach into private batch helpers.
- Arrow conversion helpers duplicate package-neutral code also present in DRC,
  RRAO, and CVA.
- Batch hash entrypoints for each risk-class/measure largely wrap the same
  generic batch hash machinery.

## Dead or storage-only code

- `attribution.py` and `impact.py` are explicit unsupported placeholders. They
  are not dead code, but their placeholder naming should remain visibly
  unsupported until real attribution/impact behavior lands.
- `accepted_row_dataclasses_materialized` is meaningful in SBM; tests cover both
  zero and non-zero paths.

## `frtb-common` candidates

- Stable hash helpers and SHA256 validation.
- Arrow conversion helpers for handoff modules.
- Possibly unique text/citation merging as a package-neutral utility, but only
  if it does not carry citation semantics beyond stable de-duplication.

## Package-local factoring candidates

- Add `frtb_sbm._text` for `_require_text` and related validation primitives.
- Add `frtb_sbm._citations` for `_merge_citation_ids`.
- Add `frtb_sbm._batch_lookup` for `_batch_text_by_id` and optional lookups so
  risk-class modules do not import private helpers from `batch.py`.
- Split `arrow_batch.py` by supported input family or by conversion mechanics
  versus semantic batch construction.
- Split `batch.py` into construction, hashing, dispatch, and array helper
  modules.

## Over-complexity

- `weighted_sensitivity.py`, `curvature.py`, and `capital.py` have broad
  risk-class branching. Table-driven helpers may reduce repetition, but
  regulatory formulas and unsupported-feature gates must stay explicit.
- `reference_data.py` and the risk-class reference modules repeat basic profile
  coercion and text validation. Consolidate helpers before changing rule tables.

## What must not move

Do not move risk weights, correlations, bucket definitions, scenario-selection
rules, curvature formulas, or BASEL_MAR21 support decisions into `frtb-common`.

## Recommended sequence

1. Extract `_citations`, `_text`, and `_batch_lookup` locally.
2. Migrate hashing to a future common stable-hash helper after shared tests land.
3. Migrate Arrow conversion helpers to common handoff helpers.
4. Split `batch.py` and `arrow_batch.py`.
5. Only then consider deeper risk-class dispatch simplification.

## Validation required

- Full SBM package tests if touching capital, aggregation, curvature, weighting,
  batch, or Arrow batch.
- Hash and audit replay tests must remain stable unless an ADR records an
  intentional hash contract change.
- `make quality-control`.

