# frtb-orchestration simplification audit

Date: 2026-06-12  
Audit-only - no runtime code changes in this report.

## Scope

`frtb-orchestration` owns suite-level aggregation, SA composition, IMA eligibility/fallback orchestration, manifest handling, and contribution bundle projection. It is the only package allowed to import multiple capital components.

## Hotspot map

| Module | Lines (approx.) | Notes |
| --- | ---: | --- |
| `frtb_orchestration/manifest.py` | 466 | Largest runtime module; below audit threshold. |
| `frtb_orchestration/_suite_attribution_models.py` | 364 | Attribution model records. |
| `frtb_orchestration/suite_attribution_summary.py` | 319 | Summary projection. |
| `frtb_orchestration/_standardised_validation.py` | 315 | Shared SA validation helpers after prior split. |

## Duplicated code

- No source duplicate-function group requiring immediate orchestration work was identified.

## Dead or storage-only code

- No high-confidence dead-code finding in the changed-code dead-code guard.

## `frtb-common` candidates

| Finding | Scope | Priority |
| --- | --- | --- |
| None from this audit | audit-only | P3 |

## Package-local factoring candidates

- Keep monitoring `manifest.py` and attribution summaries; split only if they cross 500 LOC or mix lifecycle concerns.

## Over-complexity

- `calculate_suite_capital` remains a large function but is below 120 logical LOC and serves as the suite orchestration spine.

## Wrappers and readability

- Existing validation helper extraction has reduced the highest duplication risk.

## What must not move

- Cross-component SA/IMA/CVA orchestration remains here, not in component packages.

## Recommended sequence

1. No immediate #850 follow-up required beyond drift monitoring.
2. If new suite validators are added, place them in focused `_suite_*` helpers.

## Validation required

- `uv run pytest packages/frtb-orchestration/tests`
- `make import-lint`
- `make quality-control`

## Tracking

GitHub issue: none opened from this audit.
