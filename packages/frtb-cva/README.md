# frtb-cva

Credit Valuation Adjustment capital for the `frtb-capital` suite.

The package implements a **partial** Basel MAR50 slice:

- **Reduced BA-CVA** (MAR50.14–15): stand-alone and portfolio aggregation with
  cited Table 1 risk weights, `alpha`, `rho`, and `D_BA-CVA`.
- **SA-CVA GIRR delta** (MAR50.53–57): weighted sensitivities, intra- and
  inter-bucket aggregation for the seven specified currencies plus the 1.4×
  other-currency scalar.

Public entry point: `calculate_cva_capital`. Unsupported methods and risk
classes fail closed with `UnsupportedRegulatoryFeatureError` or `CvaInputError`.

This is a prototype calculator, not final regulatory capital. See
[`docs/REGULATORY_TRACEABILITY.md`](docs/REGULATORY_TRACEABILITY.md) for
citations and scope boundaries.
