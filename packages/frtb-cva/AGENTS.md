# AGENTS.md — frtb-cva

`frtb-cva` owns CVA capital.

## Current status

The package is scaffolded only. It must fail explicitly for calculation entry
points until counterparty exposure, credit-spread, and hedge contracts are
implemented.

## Rules

- May depend on `frtb-common`.
- Must not import from `frtb-ima`, `frtb-sbm`, `frtb-drc`, or `frtb-rrao`.
- Do not emit successful placeholder capital.
