# frtb-cva

`frtb-cva` is the Credit Valuation Adjustment capital package.

## Package Status

- Package directory: `packages/frtb-cva`
- Import name: `frtb_cva`
- Implementation status: partial runtime
- Validation status: pending

Supported public paths:

- Reduced BA-CVA stand-alone and portfolio capital
- Full BA-CVA hedge recognition and beta-floor mechanics
- SA-CVA across supported delta and vega risk-class paths
- Mixed SA-CVA plus BA-CVA netting-set carve-out assembly
- Qualified-index routing where MAR50.50 metadata is supplied
- Optional CRIF adapter, Arrow/batch handoff, attribution, impact, audit, and
  replay helpers

Comparison profiles and the MAR50.9 materiality-threshold alternative remain
unsupported and fail closed via explicit errors.

## Integration journey

End-to-end client flow (Arrow handoff, batch capital, attribution, orchestration
and result-store boundaries) is documented in
[`packages/frtb-cva/docs/PACKAGE_JOURNEY.md`](../../packages/frtb-cva/docs/PACKAGE_JOURNEY.md).

## Planning Documents

- [AUDIT-IMP-005 design — profile/method coverage and MAR50.9](DESIGN_AUDIT_IMP_005.md)
- [Product requirements](PRD.md)
- [Detailed requirements](DETAILED_REQUIREMENTS.md)
- [Architecture and data design](ARCHITECTURE_AND_DATA_DESIGN.md)
- [Decisions and implementation plan](DECISIONS_AND_PLAN.md)
- [Workable issue breakdown](ISSUE_BREAKDOWN.md)
- [Regulatory requirements](REGULATORY_REQUIREMENTS.md)
- [Workable requirements](requirements/BASEL_FRTB_CVA.yml)
- [Model documentation promotion plan](../MODEL_DOCUMENTATION_PROMOTION_PLAN.md)

The historical implementation order is retained in
[ISSUE_BREAKDOWN.md](ISSUE_BREAKDOWN.md); current runtime status is tracked in
[requirements/BASEL_FRTB_CVA.yml](requirements/BASEL_FRTB_CVA.yml).

Outputs are synthetic engineering and validation evidence, not final regulatory
capital.
