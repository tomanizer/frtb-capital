# Methodology And Derivation

## Classification

The model consumes canonical evidence enums rather than free-form product
descriptions. `classification.py` maps validated evidence to cited rule records
from `reference_data.py`.

Classification outcomes are:

- `EXOTIC`, anchored to Basel MAR23.2, proposed `__.211(a)(1)`, Article
  325u(2)(a), and Delegated Regulation (EU) 2022/2328 Article 1;
- `OTHER_RESIDUAL_RISK`, anchored to Basel MAR23.3, proposed
  `__.211(a)(2)`, Article 325u(2)(b), and Delegated Regulation (EU) 2022/2328
  Article 2 and Annex;
- `SUPERVISOR_DIRECTED`, anchored to proposed `__.211(a)(4)`;
- `EXCLUDED`, anchored to Basel MAR23.4-MAR23.7, proposed `__.211(b)`, Article
  325u(4), or Delegated Regulation (EU) 2022/2328 Article 3.

## Formula

For every included line:

```text
line_add_on = gross_effective_notional * risk_weight
```

Risk weights are:

- `0.01` for exotic residual-risk positions, anchored to Basel MAR23.8(2)(a)
  and proposed `__.211(c)(1)(i)`;
- `0.001` for other residual-risk positions, anchored to Basel MAR23.8(2)(b)
  and proposed `__.211(c)(1)(ii)`;
- `0.0` for cited exclusions, represented as excluded audit lines rather than
  dropped rows.

Total RRAO is the sum of included line add-ons. The package applies no
diversification, correlation aggregation, maturity adjustment, or hedge offset
inside the v1 capital kernel.

## Exact Back-To-Back Exclusion

Exact third-party back-to-back exclusions use `RraoBackToBackMatch` evidence.
`validation.py` requires a two-transaction match group, cross-referenced
position ids, shared exclusion evidence id, matching currency, and matching
gross effective notional before zero-capital lines are emitted.

This supports Basel MAR23.7, proposed `__.211(b)(2)(i)`, and Article 325u(4)
comparison treatment for perfectly offsetting transactions.

## Numerical Tolerance

Reconciliation uses the shared budget in `numeric.py`:

- relative tolerance `1e-12`;
- absolute tolerance `1e-9`;
- excluded-line add-on absolute tolerance `1e-12`.

The hybrid tolerance keeps exact-rational current weights stable while allowing
future non-exact-rational profile weights to reconcile under accumulated
floating-point error. `tests/test_reconciliation_tolerance.py` is the regression
evidence.
