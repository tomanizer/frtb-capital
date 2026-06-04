# Capital Attribution

`frtb-rrao` does not implement Euler-style capital attribution. RRAO v1 is an
additive line-capital component, so the package exposes deterministic additive
allocation reports over a completed `RraoCapitalResult`.

## Current Support

Public helpers:

```python
from frtb_rrao import build_rrao_allocation_report, build_rrao_allocation_reports
```

Supported dimensions are:

- `line`
- `desk_id`
- `legal_entity`
- `evidence_type`

Aliases accepted by the helper include `desk`, `legal-entity`, and
`evidence-type`.

## Method

The allocation method is `additive_line_add_on`. Each included line contributes
the add-on already calculated for that line. Excluded lines remain visible in
allocation buckets with zero add-on so row counts, source ids, and exclusion
evidence reconcile to the public result.

Every report validates that:

- bucket add-ons sum to `allocated_rrao`;
- `allocated_rrao` reconciles to `total_rrao`;
- bucket keys are deterministic and unique;
- each bucket uses the requested dimension.

## Inputs Used

Allocation consumes:

- `RraoCapitalResult.lines`
- `RraoCapitalResult.excluded_lines`
- run identity, calculation date, base currency, profile id, and input hash
- existing line add-ons, gross effective notionals, desk ids, legal entities,
  evidence types, and position ids

## Allocation Grain

The supported explain grains are line, desk, legal entity, and evidence type.
The package does not project these reports to `frtb_common.CapitalContribution`
records today.

## Limitations

- No marginal, analytical Euler, or finite-difference attribution is implemented
  in `frtb-rrao`.
- Classification subtotal allocation is unsupported because classification
  subtotals already exist in the public result.
- Cross-component SA attribution is owned by `frtb-orchestration`, not RRAO.
- Unsupported profiles or evidence paths fail before an allocation report can be
  built.

## Evidence

Tests:

- `packages/frtb-rrao/tests/test_rrao_allocation.py`
- `packages/frtb-rrao/tests/test_rrao_reconciliation_tolerance.py`

Documentation and regulatory references:

- `packages/frtb-rrao/docs/ALLOCATION.md`
- `packages/frtb-rrao/docs/REGULATORY_TRACEABILITY.md`
- Basel MAR23.8
- U.S. NPR 2.0 proposed section `__.211(c)`
- EU CRR3 Article 325u(3)
