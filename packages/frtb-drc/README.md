# frtb-drc

Standardised Approach default risk charge component.

The package is importable and exposes a partial public runtime for supported
U.S. NPR 2.0 non-securitisation, securitisation non-CTP, and correlation
trading portfolio (CTP) canonical inputs, plus Basel MAR22
non-securitisation inputs. `calculate_drc_capital` calculates gross JTD,
maturity scaling, net JTD, bucket/category capital, attribution records, and
run-level reconciliation with stable ids, citations, and branch metadata.

The high-volume Arrow/batch API supports the same three DRC row classes through
class-specific handoff builders. Accepted rows stay columnar on the fast path;
only compact net-JTD, bucket, category, and result records are materialized.
The stable client integration surface is documented in
[`docs/modules/frtb-drc/PUBLIC_API.md`](../../docs/modules/frtb-drc/PUBLIC_API.md).

Securitisation non-CTP and CTP risk weights and replication/decomposition offset
evidence are supplied in `DrcCalculationContext` as run-scoped maps:
`securitisation_non_ctp_risk_weights`,
`securitisation_non_ctp_risk_weight_evidence`,
`securitisation_non_ctp_fair_value_cap_evidence`,
`securitisation_non_ctp_offset_groups`, `ctp_risk_weights`,
`ctp_risk_weight_evidence`, and `ctp_offset_groups`. Missing risk weights,
incomplete fair-value cap evidence, unsupported decomposition evidence, and
unmapped profiles fail closed through explicit input or unsupported-feature
errors; the package must not emit zero or placeholder capital for unsupported
scope.
