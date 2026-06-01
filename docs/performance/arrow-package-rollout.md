# Arrow Package Batch Rollout

Issue: #302
Parent: #271
Architecture: #262

## Decision Summary

The DRC, RRAO, and CVA rollout is complete for the scope of #271. Each package now
has a package-owned Arrow handoff -> immutable NumPy batch -> regulatory kernel
path, plus checked-in triage evidence that explains the package-specific data
shape and hotspot decisions.

The row/dataclass APIs remain compatibility and audit surfaces. The high-volume
paths are the package-owned batch entrypoints exported by each package. Regulatory
branching and capital formulas remain in package code rather than in pandas,
Polars, or Arrow dataframe expressions.

## Delivered Coverage

| Package | Issue | PR | Triage Evidence | Batch Entrypoints | Validation Evidence |
| --- | --- | --- | --- | --- | --- |
| DRC | [#299](https://github.com/tomanizer/frtb-capital/issues/299) | [#303](https://github.com/tomanizer/frtb-capital/pull/303) | `frtb-drc-arrow-batch-triage.md` | `build_drc_nonsec_batch_from_handoff`, `build_drc_nonsec_batch_from_columns`, `calculate_drc_capital_from_batch`, `input_hash_for_drc_batch` | PR #303 CI passed; local `packages/frtb-drc/tests` reported 106 tests; broad `make check` reported 1336 tests. |
| RRAO | [#300](https://github.com/tomanizer/frtb-capital/issues/300) | [#304](https://github.com/tomanizer/frtb-capital/pull/304) | `frtb-rrao-arrow-batch-triage.md` | `build_rrao_batch_from_handoff`, `build_rrao_batch_from_columns`, `calculate_rrao_capital_from_batch`, `input_hash_for_rrao_batch` | PR #304 CI passed; local `packages/frtb-rrao/tests` reported 256 tests; broad `make check` reported 1385 tests. |
| CVA | [#301](https://github.com/tomanizer/frtb-capital/issues/301) | [#305](https://github.com/tomanizer/frtb-capital/pull/305) | `frtb-cva-arrow-batch-triage.md` | `build_cva_counterparty_batch_from_handoff`, `build_cva_netting_set_batch_from_handoff`, `build_cva_hedge_batch_from_handoff`, `build_sa_cva_sensitivity_batch_from_handoff`, `calculate_cva_capital_from_batches`, `input_hash_for_cva_batches` | PR #305 CI passed; local `packages/frtb-cva/tests` reported 151 tests after review fixes; broad `make check` reported 1398 tests before review fixes and the final PR CI test job passed. |
| IMA | [#319](https://github.com/tomanizer/frtb-capital/issues/319) | this PR | `frtb-ima-arrow-handoff-triage.md` | `build_scenario_metadata_batch_from_handoff`, `build_rfet_observation_batch_from_handoff`, `assess_rfet_observation_batch`, `input_hash_for_scenario_metadata_batch`, `input_hash_for_rfet_observation_batch` | Local `make quality-control` and `make check` passed; PR CI pending. Dense scenario P&L kernels remain NumPy-backed. |

## Compatibility and Kernel Boundaries

The delivered package APIs keep accepted-row dataclass materialization off the
high-volume calculation path:

- DRC reports zero accepted `DrcPosition` dataclass materialization for batch
  calculations.
- RRAO reports zero accepted `RraoPosition` dataclass materialization for batch
  calculations.
- CVA reports zero accepted `CvaCounterparty`, `CvaNettingSet`, `CvaHedge`, and
  `SaCvaSensitivity` dataclass materialization for batch calculations.

The package-local row builders remain available for compatibility tests and
smaller integrations. They are not the intended high-volume ingestion boundary.

The import audit for this rollout found `pyarrow` only in package
`arrow_handoff.py` modules for DRC, RRAO, and CVA. The new package kernels do not
import pandas or Polars and do not encode regulatory capital logic as dataframe
expressions.

## Closure Checks

The child issues were closed directly by their package PR bodies:

- PR #303 includes `Closes #299`.
- PR #304 includes `Closes #300`.
- PR #305 includes `Closes #301`.

No DRC, RRAO, or CVA scope from #271 is intentionally deferred. Remaining Arrow
transition work is tracked outside #271, including the SBM migration and final
public API/deprecation transition.
