# ADR 0047: SBM comparison-profile runtime gates

Date: 2026-06-29

## Status

Accepted

## Context

`frtb-sbm` already supports the full `BASEL_MAR21` phase-1 SBM matrix across
seven risk classes and three risk measures. Before this decision,
`US_NPR_2_0` was limited to the GIRR delta comparison fixture and `EU_CRR3` /
`PRA_UK_CRR` failed closed for capital-producing paths.

ADR 0005 treats supported-regime changes, requirement-status changes, fixture
output changes, profile hashes, and reproducibility claims as material changes.
Opening comparison-profile runtime gates therefore needs explicit decision
evidence even when the numerical tables intentionally mirror Basel.

## Decision

`US_NPR_2_0`, `EU_CRR3`, and `PRA_UK_CRR` may expose the full 7 x 3 SBM runtime
matrix as a **comparison slice under audit**.

The comparison slice has these constraints:

- Runtime gates are open for all 21 risk-class/measure cells per profile.
- Numerics mirror the implemented `BASEL_MAR21` reference tables.
- Citation ids are owned by the active profile and must not leak Basel ids into
  comparison-profile audit payloads.
- Each comparison profile has deterministic GIRR delta fixture replay evidence.
- The remaining 20 cells per profile do not yet have per-cell fixture packs and
  must be described as comparison material, not independently validated
  regulatory capital.
- U.S. NPR 2.0 content remains proposed-rule comparison material.

Unsupported sub-features inside the Basel implementation boundary, such as
equity repo vega and curvature, remain fail-closed under every profile.

## Consequences

The `frtb-sbm` package version advances because supported runtime profile
semantics and profile content hashes change.

Documentation and traceability must distinguish runtime-gate coverage from
fixture-backed coverage. Future work may replace Basel-mirrored rows with
independently transcribed NPR, EU, or UK values only through a separate material
change with fixtures and source mapping.

## References

- [ADR 0005](0005-material-change-policy.md)
- [SBM non-Basel profile design](../modules/frtb-sbm/NON_BASEL_PROFILE_DESIGN.md)
- [SBM non-Basel profile requirements](../modules/frtb-sbm/NON_BASEL_PROFILE_REQUIREMENTS.md)
- [SBM regulatory traceability](../../packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md)
