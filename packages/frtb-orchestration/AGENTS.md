# AGENTS.md — frtb-orchestration

`frtb-orchestration` owns suite-level aggregation and routing.

## Current status

The package has a partial handoff contract for recognising RRAO outputs. It
must still fail explicitly for aggregation entry points until component
packages produce compatible typed, audited outputs.

## Rules

- May depend on `frtb-common` and all capital component packages.
- Owns SA composition from `frtb-sbm + frtb-drc + frtb-rrao`.
- Owns fallback routing when IMA eligibility fails.
- Do not emit successful placeholder capital.
