# AGENTS.md — frtb-drc

`frtb-drc` owns the Standardised Approach default risk charge component.

## Current status

The package is scaffolded only. It must fail explicitly for calculation entry
points until issuer, tranche, maturity, seniority, and JTD contracts are
implemented.

## Rules

- May depend on `frtb-common`.
- Must not import from `frtb-ima`, `frtb-sbm`, `frtb-rrao`, or `frtb-cva`.
- Do not emit successful placeholder capital.
