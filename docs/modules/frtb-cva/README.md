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
- [Regulatory requirements](REGULATORY_REQUIREMENTS.md)
- [Workable requirements](requirements/BASEL_FRTB_CVA.yml)
