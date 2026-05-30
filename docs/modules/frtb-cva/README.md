# frtb-cva

`frtb-cva` is the scaffolded Credit Valuation Adjustment capital package.

## Package Status

- Package directory: `packages/frtb-cva`
- Import name: `frtb_cva`
- Implementation status: scaffolded; calculation not implemented
- Validation status: not started

The package is importable and exposes a public calculation boundary, but
`calculate_cva_capital` raises an explicit unimplemented-component error until
counterparty exposure, credit-spread, and hedge contracts are implemented.

## Planning Documents

- [Product requirements](PRD.md)
- [Detailed requirements](DETAILED_REQUIREMENTS.md)
- [Architecture and data design](ARCHITECTURE_AND_DATA_DESIGN.md)
- [Decisions and implementation plan](DECISIONS_AND_PLAN.md)
- [Workable issue breakdown](ISSUE_BREAKDOWN.md)
- [Regulatory requirements](REGULATORY_REQUIREMENTS.md)
- [Workable requirements](requirements/BASEL_FRTB_CVA.yml)

Implementation order is governed by [ISSUE_BREAKDOWN.md](ISSUE_BREAKDOWN.md).
