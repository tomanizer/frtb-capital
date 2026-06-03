# frtb-orchestration simplification audit

## Scope

`frtb-orchestration` owns suite-level aggregation and routing. It consumes
public handoff contracts and must not reach into private component modules.

## Hotspot map

| Module | Lines | Notes |
| --- | ---: | --- |
| `standardised.py` | 158 | SA component handoff validation and fail-closed aggregation boundary. |
| `cva_summary.py` | 156 | CVA result projection. |
| `scaffold.py` | 29 | Suite capital fail-closed entrypoint. |

## Duplicated code

- `standardised.py` and `cva_summary.py` both perform required text/hash-like
  attribute validation, but the package is small enough that extraction is not
  urgent.
- `ComponentCapitalSummary` in `frtb-common` already centralizes the SA component
  handoff shape.

## Dead or storage-only code

- No dead code identified. Fail-closed placeholders are intentional until suite
  aggregation arithmetic lands.

## `frtb-common` candidates

- If CVA top-of-house handoff becomes a shared contract, consider a
  `frtb-common` handoff type analogous to `ComponentCapitalSummary`. Do not move
  orchestration routing decisions into common.

## Package-local factoring candidates

- Add a tiny local attribute-validation helper only if more handoff projections
  are added.

## Over-complexity

None at current size. The risk is future coupling: orchestration should continue
to consume public component handoffs rather than private module internals.

## What must not move

Do not move SA composition routing, IMA fallback routing, top-of-house
aggregation decisions, or suite fail-closed behavior into component packages.

## Recommended sequence

1. Leave as-is for now.
2. Re-audit when actual suite aggregation arithmetic lands.
3. Add shared/common CVA handoff only if multiple packages consume it.

## Validation required

- Orchestration package tests.
- Boundary/import checks through `make quality-control`.

