# frtb-ima simplification audit

Date: 2026-06-04

## Scope

Model-eligible desk IMA capital only. No SBM/DRC/RRAO/CVA calculations here.

## Hotspot map

| Module | Lines (approx.) | Notes |
| --- | ---: | --- |
| `rfet_evidence.py` | 933 | `assess_rfet_evidence` ~280+ lines |
| `stress_periods.py` | 760 | Stress selection |
| `backtesting.py` | 757 | Backtesting traces |
| `nmrf.py` | 743 | NMRF classification |
| `arrow_batch.py` | 688 | Arrow boundary |

## Duplicated code

| Finding | Scope | Priority |
| --- | --- | --- |
| Partially addressed: `_array_utils`, `_mapping_utils`, `_observation_utils` | package-local | P2 done |
| Remaining overlap: observation-date validation across PLA/backtesting | package-local | P2 |
| `as_dict` serialization repetition | package-local | P3 |

## Dead or storage-only code

None significant. Package-local `UnsupportedRegulatoryFeatureError` vs common — review only (P3).

## `frtb-common` candidates

Arrow handoff helpers where null/date behavior matches other packages; hash only
if bytes/NumPy digest behavior is preserved or extended in common.

## Package-local factoring candidates

Split `assess_rfet_evidence` into named audit stages (qualitative gates vs
quantitative windows) per `REFACTOR_HOTSPOTS.md`.

## Over-complexity

Long functions are often regulatory-audit oriented — prefer **named stages** over
generic abstractions.

## Wrappers and readability

Generally more readable than batch-heavy SA components; avoid “template” refactors
that hide citation anchors.

## What must not move

Scenario vectors, LH adjustment, RFET/NMRF, PLA/backtesting thresholds, desk handoff.

## Recommended sequence

1. Split `assess_rfet_evidence` with stage tests.
2. Consolidate remaining observation-window validation.
3. Optional hash alignment with `stable_json_hash` where safe.

## Validation required

RFET, PLA, backtesting, NMRF, scenario, audit hash tests; mutation floor unchanged unless ADR.

## Tracking

GitHub issue: [#540](https://github.com/tomanizer/frtb-capital/issues/540)
