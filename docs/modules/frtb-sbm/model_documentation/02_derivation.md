# Derivation

## Delta

Delta paths validate canonical sensitivities, apply risk-class bucket and risk
weight rules, then aggregate weighted sensitivities within and across buckets.
Implemented Basel MAR21 anchors include GIRR MAR21.40-MAR21.42, CSR
non-securitisation MAR21.51-MAR21.57, CSR securitisation MAR21.58-MAR21.70,
equity MAR21.71-MAR21.80, commodity MAR21.81-MAR21.85, and FX
MAR21.86-MAR21.89.

## Vega

Vega paths use MAR21.90-MAR21.95, including liquidity-horizon scaling, option
tenor treatment, and non-GIRR vega correlations. Inputs missing required option
tenor, underlying tenor, volatility, or supported factor metadata fail
validation before capital is emitted.

## Curvature

Curvature paths use separate up/down shock inputs and branch metadata rather
than forcing curvature into delta/vega weighted-sensitivity records. The core
anchors are MAR21.5 and MAR21.96-MAR21.101. The FX curvature scalar required by
MAR21.98 is applied only when explicit row evidence is present.

## Scenario Selection

For delta and vega risk classes, the package evaluates low, medium, and high
correlation scenarios under MAR21.6-MAR21.7, then selects the maximum capital.
Scenario totals and pairwise-correlation evidence are retained for audit.

## Audit And Reconciliation

Every supported result carries profile hash, input hash, reconciliation
metadata, source lineage, and branch details. Attribution and impact are
explicitly unsupported for SBM-FUNC-022 until analytical or finite-difference
methods are implemented and tested.
