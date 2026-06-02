# frtb-cva simplification audit

## Scope

`frtb-cva` owns CVA capital. It supports reduced/full BA-CVA, SA-CVA, and mixed
carve-out paths where approved. Comparison profiles and unsupported materiality
alternatives must fail closed.

## Hotspot map

| Module | Lines | Notes |
| --- | ---: | --- |
| `batch.py` | 2814 | Largest package module; batch schema, validation, hashing, and kernels. |
| `reference_data.py` | 779 | CVA profile and reference data. |
| `sa_cva_reference_data.py` | 625 | SA-CVA risk weights and correlations. |
| `arrow_handoff.py` | 612 | Arrow-to-batch conversion. |
| `weighted_sensitivity.py` | 599 | SA-CVA sensitivity weighting. |
| `audit.py` | 556 | Reconciliation, input hashes, payloads. |
| `validation.py` | 489 | CVA input validation. |
| `data_models.py` | 457 | CVA frozen data/result records. |
| `ba_cva.py` | 406 | BA-CVA formulas. |

## Duplicated code

- `_hash_payload` appears in audit, batch, and regimes.
- Audit and batch duplicate payload helpers for context, counterparties,
  netting sets, hedges, sensitivities, and lineage.
- `_merge_citations` is duplicated in capital and batch.
- `_profile_warnings` is duplicated in capital and batch.
- `_hedge_risk_weight` appears in BA-CVA and batch paths.
- `_finite_float` and `_require_text` repeat between validation/reference-data
  and batch helpers.
- Risk-class modules repeat small `_gamma` and `_intra` closures.
- Arrow and batch array helpers duplicate suite-wide mechanics.

## Dead or storage-only code

- No obvious dead runtime code was identified.
- Impact/attribution support should stay explicitly unsupported until real
  methods are implemented; do not present placeholder objects as analytical
  decomposition.

## `frtb-common` candidates

- Stable hash helpers and SHA256 validation.
- Arrow conversion helpers.
- Batch array coercion helpers.
- Possibly generic citation de-duplication if kept semantics-free.

## Package-local factoring candidates

- Add `frtb_cva._payloads` for shared audit/batch input payload construction.
- Add `frtb_cva._citations` for merge helpers.
- Add `frtb_cva._batch_arrays` if common batch helpers are not ready.
- Add a package-local hedge eligibility/risk-weight helper used by BA-CVA and
  batch paths.
- Split `batch.py` into schema/arrays, validation, BA-CVA batch, SA-CVA batch,
  and result assembly.

## Over-complexity

- `batch.py` is the largest module in the suite and mixes several concepts. A
  split will improve reviewability even before line count drops.
- Audit and batch payload duplication is a hash-drift risk.
- SA-CVA risk-class wrappers are already factored through
  `risk_classes._common`; continue that pattern rather than widening common
  package scope.

## What must not move

Do not move MAR50 profile semantics, BA-CVA formulas, SA-CVA risk weights,
correlations, hedge eligibility, mixed carve-out behavior, or CVA result
semantics into `frtb-common`.

## Recommended sequence

1. Extract shared payload builders locally so audit and batch hashes cannot
   drift.
2. Extract citation/profile-warning helpers locally.
3. Migrate hashing and Arrow conversion through future `frtb-common` helpers.
4. Split `batch.py`.
5. Revisit hedge-risk-weight duplication after batch payloads are unified.

## Validation required

- CVA package tests for BA-CVA, SA-CVA, mixed carve-out, hedges, weighted
  sensitivities, audit, Arrow batch, and CRIF.
- Hash compatibility tests before and after payload refactors.
- `make quality-control`.

