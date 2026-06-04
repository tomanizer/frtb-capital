# Capital Attribution

`frtb-rrao` does not implement Euler-style capital attribution. RRAO v1 is an
additive line-capital component, so the package exposes deterministic additive
allocation reports and shared `CapitalContribution` projections over a
completed `RraoCapitalResult`.

## Current Support

Public helpers:

```python
from frtb_rrao import (
    build_rrao_allocation_report,
    build_rrao_allocation_reports,
    build_rrao_contribution_bundle,
    calculate_rrao_attribution,
)
```

Supported dimensions are:

- `line`
- `desk_id`
- `legal_entity`
- `evidence_type`

Aliases accepted by the helper include `desk`, `legal-entity`, and
`evidence-type`.

## Method

The allocation method is `additive_line_add_on`. Shared contribution records
use `AttributionMethod.STANDALONE`. Each included line contributes the add-on
already calculated for that line. Excluded lines remain visible in allocation
buckets and shared records with zero add-on so row counts, source ids, and
exclusion evidence reconcile to the public result.

Every report validates that:

- bucket add-ons sum to `allocated_rrao`;
- `allocated_rrao` reconciles to `total_rrao`;
- bucket keys are deterministic and unique;
- each bucket uses the requested dimension.

The canonical `ComponentContributionBundle` view is the line-level projection:
`ComponentContributionBundle(component="frtb_rrao", ...)`. Its component total,
input hash, and profile hash come from the source `RraoCapitalResult`.

## Inputs Used

Allocation consumes:

- `RraoCapitalResult.lines`
- `RraoCapitalResult.excluded_lines`
- run identity, calculation date, base currency, profile id, and input hash
- existing line add-ons, gross effective notionals, desk ids, legal entities,
  evidence types, and position ids

## Allocation Grain

The supported explain grains are line, desk, legal entity, and evidence type.
`calculate_rrao_attribution` supports the same grains. The bundle helper uses
line grain as the canonical orchestration handoff because it preserves
position-level source ids.

## Limitations

- No marginal, analytical Euler, or finite-difference attribution is implemented
  in `frtb-rrao`.
- `STANDALONE` records explain additive line charges only; they are not
  derivatives through SA aggregation or any top-of-house capital formula.
- Classification subtotal allocation is unsupported because classification
  subtotals already exist in the public result.
- Cross-component SA attribution is owned by `frtb-orchestration`, not RRAO.
- Unsupported profiles or evidence paths fail before an allocation report can be
  built.

## Evidence

Tests:

- `packages/frtb-rrao/tests/test_rrao_allocation.py`
- `packages/frtb-rrao/tests/test_rrao_attribution.py`
- `packages/frtb-rrao/tests/test_rrao_reconciliation_tolerance.py`

Documentation and regulatory references:

- `packages/frtb-rrao/docs/ALLOCATION.md`
- `packages/frtb-rrao/docs/REGULATORY_TRACEABILITY.md`
- Basel MAR23.8
- U.S. NPR 2.0 proposed section `__.211(c)`
- EU CRR3 Article 325u(3)
