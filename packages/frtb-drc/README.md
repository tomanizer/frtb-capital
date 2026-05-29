# frtb-drc

Standardised Approach default risk charge component.

The package is importable and exposes a partial public runtime for supported
U.S. NPR 2.0 non-securitisation canonical inputs. `calculate_drc_capital`
calculates gross JTD, maturity scaling, net JTD, bucket/category capital, and
run-level reconciliation with stable ids, citations, and branch metadata.

Securitisation non-CTP, CTP, and unmapped profiles fail closed through explicit
input or unsupported-feature errors; the package must not emit zero or
placeholder capital for unsupported scope.
