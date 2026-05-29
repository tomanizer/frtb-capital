# AGENTS.md — frtb-drc

`frtb-drc` owns the Standardised Approach default risk charge component.

## Current status

The package has a capital-producing partial implementation for
non-securitisation DRC. Unsupported securitisation and CTP paths must still fail
explicitly before producing capital.

## Rules

- May depend on `frtb-common`.
- Must not import from `frtb-ima`, `frtb-sbm`, `frtb-rrao`, or `frtb-cva`.
- Do not emit successful placeholder capital.
- Preserve attribution-ready lineage for capital-producing paths: stable record
  ids, deterministic grouping, input citations, and branch metadata.
