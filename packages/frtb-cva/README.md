# frtb-cva

Credit Valuation Adjustment capital for the `frtb-capital` suite.

The package implements a **partial** Basel MAR50 slice:

- **Reduced BA-CVA** (MAR50.14-MAR50.16): stand-alone and portfolio aggregation
  with cited Table 1 risk weights, `alpha`, `rho`, and `D_BA-CVA`.
- **Full BA-CVA** (MAR50.17-MAR50.26): eligible single-name and index hedge
  recognition, beta floor, and cited hedge rejection records.
- **SA-CVA** (MAR50.42-MAR50.77): supported delta and vega risk-class paths
  across GIRR, FX, counterparty credit spread, reference credit spread, equity,
  and commodity where MAR50 defines the risk measure and `sa_cva_approved=True`.
  CCS vega is not defined by MAR50.45/MAR50.63 and fails explicitly.
- **Mixed carve-out** (MAR50.8): SA-CVA plus BA-CVA netting-set carve-outs with
  component totals and reconciliation.
- **Qualified-index routing** (MAR50.50): CCS bucket 8, RCS, and equity
  qualified-index handling when the input supplies required metadata.

Public entry point: `calculate_cva_capital`. Unsupported methods and risk
classes fail closed with `UnsupportedRegulatoryFeatureError` or `CvaInputError`.

Outputs are synthetic engineering and validation evidence, not final regulatory
capital. See
[`docs/REGULATORY_TRACEABILITY.md`](docs/REGULATORY_TRACEABILITY.md) for
citations and scope boundaries.
