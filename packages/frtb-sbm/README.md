# frtb-sbm

Scaffold package for the Standardised Approach sensitivities-based method
component.

The package is importable and exposes its planned public boundary, but it does
not calculate SBM capital yet. Public calculation entry points raise
`NotImplementedCapitalComponentError` from `frtb-common`; they must not emit
zero or placeholder capital.
