# frtb-rrao

`frtb-rrao` is the scaffolded Standardised Approach residual risk add-on
package.

## Package Status

- Package directory: `packages/frtb-rrao`
- Import name: `frtb_rrao`
- Implementation status: scaffolded; calculation not implemented
- Validation status: not started

The package is importable and exposes a public calculation boundary, but
`calculate_rrao_capital` raises an explicit unimplemented-component error until
residual-risk classification and additive capital mechanics are implemented.

## Planning Documents

- [Product requirements](PRD.md)
- [Regulatory requirements](REGULATORY_REQUIREMENTS.md)
- [Detailed requirements](DETAILED_REQUIREMENTS.md)
- [Architecture and data design](ARCHITECTURE_AND_DATA_DESIGN.md)
- [Decisions and implementation plan](DECISIONS_AND_PLAN.md)
- [Workable issue breakdown](ISSUE_BREAKDOWN.md)
- [Workable requirements](requirements/BASEL_FRTB_RRAO.yml)

## v1 Target

The planned v1 target is a U.S. NPR 2.0 proposed section `__.211` plus Basel
MAR23 canonical-input RRAO slice. It will calculate cited 1.0% exotic and 0.1%
other residual-risk line add-ons, preserve explicit exclusions as zero-capital
audit lines, and fail closed for EU/PRA profile gaps until separately mapped and
tested.
