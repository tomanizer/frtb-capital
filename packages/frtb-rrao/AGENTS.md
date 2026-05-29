# AGENTS.md — frtb-rrao

`frtb-rrao` owns the Standardised Approach residual risk add-on component.

## Current status

The package has an implemented v1 canonical-input RRAO calculation path for
Basel MAR23, U.S. NPR 2.0 proposed section `__.211`, and the EU CRR3 Article
325u comparison profile. It must still fail explicitly for unsupported profiles,
unsupported evidence paths, and ambiguous classification evidence.

## Rules

- May depend on `frtb-common`.
- Must not import from `frtb-ima`, `frtb-sbm`, `frtb-drc`, or `frtb-cva`.
- Do not emit successful placeholder capital for unmapped regulatory paths.
- Preserve zero-capital exclusion records as auditable lines rather than
  dropping input rows.
