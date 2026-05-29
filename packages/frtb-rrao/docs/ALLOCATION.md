# RRAO allocation reports

RRAO v1 allocation reports are additive explain views over an already produced
`RraoCapitalResult`. They do not recalculate capital, apply Euler allocation,
or alter the result payload.

Supported dimensions:

- `line`
- `desk_id`
- `legal_entity`
- `evidence_type`

The helper accepts `desk`, `legal-entity`, and `evidence-type` as aliases for
the corresponding canonical dimension values. Any other requested dimension
raises `RraoInputError` before a report is emitted.

## Method

The report method is `additive_line_add_on`. For each included line, allocated
capital is the existing line add-on from Basel MAR23.8, proposed U.S. section
`__.211(c)`, or EU Article 325u(3), depending on the result profile. Excluded
lines remain visible in allocation buckets with zero add-on, so line counts and
source position ids reconcile to the public result.

Every report validates that:

- bucket add-ons sum to `allocated_rrao`;
- `allocated_rrao` reconciles to `total_rrao`;
- each bucket uses the requested dimension;
- bucket keys are deterministic and unique.

## Unsupported paths

The following allocation paths are intentionally unsupported in v1:

- classification allocation reports, because classification subtotals already
  exist in the public result;
- marginal or Euler-style allocation, because RRAO itself is additive and the
  non-additive SA total is owned by orchestration after SBM and DRC are
  compatible;
- allocation across currencies, scenario runs, or suite-level components;
- unsupported profile or evidence paths that failed before the
  `RraoCapitalResult` was produced.
