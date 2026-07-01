# drc_eu_ctp_v1

Deterministic EU CRR3 CTP fixture for `frtb-drc`.

The fixture uses Article 325ad typed upstream CTP banking-book risk-weight and
decomposition evidence for every position and explicit offset-group evidence
for the replicated CDX.NA.IG tranche package. The CDX.HY short index remains in
a separate bucket, exercising CTP-wide HBR and cross-bucket category
aggregation.
