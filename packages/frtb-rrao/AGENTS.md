# AGENTS.md — frtb-rrao

`frtb-rrao` owns the Standardised Approach residual risk add-on component.

## Current status

The package is scaffolded only. It must fail explicitly for calculation entry
points until residual-risk classification and additive capital mechanics are
implemented.

## Rules

- May depend on `frtb-common`.
- Must not import from `frtb-ima`, `frtb-sbm`, `frtb-drc`, or `frtb-cva`.
- Do not emit successful placeholder capital.
