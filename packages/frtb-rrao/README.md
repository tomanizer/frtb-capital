# frtb-rrao

Scaffold package for the Standardised Approach residual risk add-on component.

The package is importable and exposes its planned public boundary, but it does
not calculate RRAO capital yet. Public calculation entry points raise
`NotImplementedCapitalComponentError` from `frtb-common`; they must not emit
zero or placeholder capital.

The planned v1 implementation is a canonical-input RRAO slice covering U.S. NPR
2.0 proposed section `__.211` and Basel MAR23 additive line-capital mechanics,
with classification evidence and exclusions recorded in audit output.

Planning documents:

- `docs/modules/frtb-rrao/DETAILED_REQUIREMENTS.md`
- `docs/modules/frtb-rrao/ARCHITECTURE_AND_DATA_DESIGN.md`
- `docs/modules/frtb-rrao/DECISIONS_AND_PLAN.md`
- `docs/modules/frtb-rrao/ISSUE_BREAKDOWN.md`
