# frtb-cva

Scaffold package for Credit Valuation Adjustment capital.

The package is importable and exposes its planned public boundary, but it does
not calculate CVA capital yet. Public calculation entry points raise
`NotImplementedCapitalComponentError` from `frtb-common`; they must not emit
zero or placeholder capital.
