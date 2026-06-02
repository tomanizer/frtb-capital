# frtb-drc

Standardised Approach default risk charge component.

The package is importable and exposes a partial public runtime for supported
U.S. NPR 2.0 non-securitisation, securitisation non-CTP, and correlation
trading portfolio (CTP) canonical inputs. `calculate_drc_capital` calculates
gross JTD, maturity scaling, net JTD, bucket/category capital, and run-level
reconciliation with stable ids, citations, and branch metadata.

Securitisation non-CTP and CTP risk weights and replication/decomposition offset
evidence are supplied in `DrcCalculationContext` as run-scoped maps:
`securitisation_non_ctp_risk_weights`,
`securitisation_non_ctp_offset_groups`, `ctp_risk_weights`, and
`ctp_offset_groups`. Missing risk weights, unsupported decomposition evidence,
and unmapped profiles fail closed through explicit input or unsupported-feature
errors; the package must not emit zero or placeholder capital for unsupported
scope.
