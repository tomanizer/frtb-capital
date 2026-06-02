# AGENTS.md — frtb-drc

`frtb-drc` owns the Standardised Approach default risk charge component.

## Current status

The package has a capital-producing partial implementation for U.S. NPR 2.0
non-securitisation, securitisation non-CTP, and correlation trading portfolio
(CTP) DRC row and batch paths, plus Basel MAR22 non-securitisation row and
batch paths. Basel MAR22 securitisation non-CTP and CTP paths, and all EU CRR3
and PRA UK CRR paths, must fail explicitly until cited profile mappings and
deterministic tests exist.

## Rules

- May depend on `frtb-common`.
- Must not import from `frtb-ima`, `frtb-sbm`, `frtb-rrao`, or `frtb-cva`.
- Do not emit successful placeholder capital.
- Preserve attribution-ready lineage for capital-producing paths: stable record
  ids, deterministic grouping, input citations, and branch metadata.
