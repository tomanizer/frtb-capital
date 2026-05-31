# frtb-cva

`frtb-cva` is the Credit Valuation Adjustment capital package.

## Package Status

- Package directory: `packages/frtb-cva`
- Import name: `frtb_cva`
- Implementation status: partial runtime
- Validation status: pending

Supported public paths:

- Reduced BA-CVA stand-alone and portfolio capital
- SA-CVA GIRR delta weighting and aggregation

Full BA-CVA hedge recognition (Basel MAR50.17–26) and SA-CVA risk classes other
than GIRR delta are unsupported and fail closed via explicit errors.

## Planning Documents

- [Product requirements](PRD.md)
- [Detailed requirements](DETAILED_REQUIREMENTS.md)
- [Architecture and data design](ARCHITECTURE_AND_DATA_DESIGN.md)
- [Decisions and implementation plan](DECISIONS_AND_PLAN.md)
- [Workable issue breakdown](ISSUE_BREAKDOWN.md)
- [Regulatory requirements](REGULATORY_REQUIREMENTS.md)
- [Workable requirements](requirements/BASEL_FRTB_CVA.yml)
- [Model documentation promotion plan](../MODEL_DOCUMENTATION_PROMOTION_PLAN.md)

Implementation order is governed by [ISSUE_BREAKDOWN.md](ISSUE_BREAKDOWN.md).

Outputs are prototype model-validation evidence, not final regulatory capital.
