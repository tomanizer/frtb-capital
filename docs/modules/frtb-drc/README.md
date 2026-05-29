# frtb-drc

`frtb-drc` is the scaffolded Standardised Approach default risk charge package.

## Package Status

- Package directory: `packages/frtb-drc`
- Import name: `frtb_drc`
- Implementation status: scaffolded; calculation not implemented
- Validation status: not started

The package is importable and exposes a public calculation boundary, but
`calculate_drc_capital` raises an explicit unimplemented-component error until
issuer, tranche, maturity, seniority, and JTD mechanics are implemented.

## Planning Documents

- [Product requirements](PRD.md)
- [Regulatory requirements](REGULATORY_REQUIREMENTS.md)
- [Detailed implementation requirements](DETAILED_REQUIREMENTS.md)
- [Architecture and data design](ARCHITECTURE_AND_DATA_DESIGN.md)
- [Decisions and implementation plan](DECISIONS_AND_PLAN.md)
- [Workable issue breakdown](ISSUE_BREAKDOWN.md)
- [Workable requirements](requirements/BASEL_FRTB_DRC.yml)
