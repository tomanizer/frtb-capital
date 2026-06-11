# frtb-orchestration simplification audit

Date: 2026-06-04

## Scope

Suite-level IMA + SA + CVA aggregation. Consumes public handoffs only; no sibling
capital imports.

## Hotspot map

| Module | Lines (approx.) | Notes |
| --- | ---: | --- |
| `suite.py` | 666 | `calculate_suite_capital`, attribution |
| `standardised.py` | 555 | SA composition (was ~158 in 2026-06-02 audit) |
| `manifest.py` | 438 | Run manifest |
| `ima_summary.py` | 304 | IMA projection |
| `cva_summary.py` | 159 | CVA projection |

## Duplicated code

| Finding | Scope | Priority |
| --- | --- | --- |
| Handoff field validation overlap `standardised.py` / `cva_summary.py` | package-local | P2 |
| Jurisdiction family maps in `suite.py` vs SA internal table | package-local | P2 |

## Dead or storage-only code

`scaffold.py` legacy entry — verify exports vs `suite.py` (audit-only P3).

## `frtb-common` candidates

Optional shared CVA handoff type if multiple consumers need it — not urgent.

## Package-local factoring candidates

- `_suite_validation.py` — date/currency/family consistency.
- `_attribution.py` — tolerance and bundle normalization from `suite.py`.

## Over-complexity

`SuiteCapitalResult.__post_init__` is long but mostly explicit validation — extract
helpers rather than shorten regulatory checks.

## Wrappers and readability

Code reads professional; complexity reflects real suite semantics post–ADR 0039.

## What must not move

SA composition routing, IMA fallback policy, top-of-house aggregation decisions.

## Recommended sequence

1. Extract validation helpers from `suite.py` (no behavior change).
2. Re-audit when manifest-driven client paths grow.

## Validation required

`test_suite_capital.py`, orchestration boundary tests, `make quality-control`.

## Tracking

Consolidation: [#723](https://github.com/tomanizer/frtb-capital/issues/723) (ADR 0045 epic [#725](https://github.com/tomanizer/frtb-capital/issues/725)).
