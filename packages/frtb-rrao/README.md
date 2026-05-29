# frtb-rrao

Scaffold package for the Standardised Approach residual risk add-on component.

The package is importable and exposes its planned public boundary, but it does
not calculate RRAO capital yet. Public calculation entry points raise
`NotImplementedCapitalComponentError` from `frtb-common`; they must not emit
zero or placeholder capital.
