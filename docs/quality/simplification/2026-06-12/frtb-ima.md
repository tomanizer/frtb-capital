# frtb-ima simplification audit

Date: 2026-06-12  
Audit-only - no runtime code changes in this report.

## Scope

`frtb-ima` owns IMA ES, LHA, IMCC, RFET, NMRF, PLA, backtesting, fixture, and audit workflows. It is implemented and should not inherit the Standardised Approach batch-registry shape mechanically; splits should follow RFET, observation-window, stress-period, and NMRF responsibilities.

## Hotspot map

| Module | Lines (approx.) | Notes |
| --- | ---: | --- |
| `frtb_ima/nmrf.py` | 969 | NMRF capital and policy routing hotspot. |
| `frtb_ima/stress_periods.py` | 949 | Stress-period selection remains dense. |
| `frtb_ima/backtesting.py` | 897 | Backtesting trace function is large. |
| `frtb_ima/nmrf_valuation_run.py` | 786 | Near stage ceiling. |
| `frtb_ima/capital_run_fixture.py` | 773 | Fixture workflow; keep deterministic. |

## Duplicated code

- No major source duplicate-function cluster dominates IMA in the current report. The main risk is function/module size rather than exact copy-paste.
- Test and fixture helper duplication is tracked in #898 where applicable.

## Dead or storage-only code

- `_observation_utils.py` and `arrow_batch.py` are tiny compatibility shims; acceptable pending deliberate trim.

## `frtb-common` candidates

| Finding | Scope | Priority |
| --- | --- | --- |
| SHA256 validation can use common helpers where it does not change audit payloads | `frtb-common` | P2 |

## Package-local factoring candidates

- Split stress-period and NMRF functions by validation, candidate generation, policy selection, and result assembly under #897.
- Continue RFET stage work in validation/assembly modules rather than rebuilding a generic batch registry.

## Over-complexity

- `calculate_nmrf_capital_for_policy`, `select_nmrf_method`, `build_nmrf_valuation_specs`, `reconcile_nmrf_valuation_artifacts`, `pla_assessment_for_policy_with_diagnostics`, and `select_stress_periods_by_risk_class` remain large functions.

## Wrappers and readability

- Compatibility wrappers should stay short and tested; avoid broad public API churn in IMA without a dedicated model-doc update.

## What must not move

- RFET/NMRF/PLA/backtesting regulatory thresholds, policy support decisions, and fixture hash semantics remain IMA-local.

## Recommended sequence

1. Use #897 for oversized IMA module splits.
2. Keep RFET qualitative/quantitative and observation-window helpers package-local.
3. Run fixture determinism checks before any material IMA split.

## Validation required

- `uv run pytest packages/frtb-ima/tests`
- `make mutation-score-check` when mutation-relevant paths change
- `make drift-check`
- `make quality-control`

## Tracking

GitHub issue: [#897](https://github.com/tomanizer/frtb-capital/issues/897)
