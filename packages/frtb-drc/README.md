# frtb-drc

Scaffold package for the Standardised Approach default risk charge component.

The package is importable and exposes its planned public boundary, but it does
not calculate DRC capital yet. Public calculation entry points raise
`NotImplementedCapitalComponentError` from `frtb-common`; they must not emit
zero or placeholder capital.
