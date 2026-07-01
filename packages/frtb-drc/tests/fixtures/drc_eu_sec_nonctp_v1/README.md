# drc_eu_sec_nonctp_v1

Deterministic EU CRR3 securitisation non-CTP fixture for `frtb-drc`.

The fixture uses Article 325aa typed upstream banking-book securitisation
risk-weight evidence for every position, Article 325aa fair-value-cap evidence
for every position, and explicit offset-group evidence for every position. The
two CLO positions share an offset group and net to a single long JTD. The RMBS
positions have different offset groups, so the short is audited as rejected
offset evidence. The long RMBS fair-value cap is binding.
