# AGENTS.md — frtb-orchestration

`frtb-orchestration` owns suite-level aggregation and routing.

## Current status

The package is scaffolded only. It must fail explicitly for aggregation entry
points until component packages produce typed, audited outputs.

## Rules

- May depend on `frtb-common` and all capital component packages.
- Owns SA composition from `frtb-sbm + frtb-drc + frtb-rrao`.
- Owns fallback routing when IMA eligibility fails.
- Do not emit successful placeholder capital.
