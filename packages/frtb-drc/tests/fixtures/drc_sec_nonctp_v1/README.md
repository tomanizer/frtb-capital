# DRC securitisation non-CTP fixture v1

Synthetic hand-checked fixture for the U.S. NPR 2.0 securitisation non-CTP path.

- `SEC_CLO_NORTH_AMERICA`: one long and one shorter-maturity short in the same
  pool/tranche offset to an 80.0 net long JTD at a 20% risk weight, giving
  16.0 bucket capital.
- `SEC_RMBS_EUROPE`: one long and one short in different pools do not offset.
  The bucket HBR is `100 / (100 + 60) = 0.625`; weighted long is `100 * 0.05`,
  weighted short is `60 * 0.05`, and bucket capital is `5 - 0.625 * 3 = 3.125`.

Expected total DRC is `16.0 + 3.125 = 19.125`.
