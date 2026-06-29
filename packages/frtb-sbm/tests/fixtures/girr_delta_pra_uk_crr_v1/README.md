Synthetic hand-checked fixture for the PRA UK CRR GIRR delta comparison slice.

The fixture uses the same three-row shape as `girr_delta_v1`, but runs under
`PRA_UK_CRR` with profile-owned citation ids and reference payload hashing.
It is comparison material only and is not final regulatory capital.

| Sensitivity | Purpose | Citation ids |
| --- | --- | --- |
| `pra-uk-crr-eur-1y` | EUR 1y GIRR delta sensitivity in bucket 1. | `pra_uk_crr_art_325r_girr_buckets`, `pra_uk_crr_art_325r_girr_delta_weights` |
| `pra-uk-crr-eur-5y` | Same-bucket EUR tenor diversification. | `pra_uk_crr_art_325r_girr_intra` |
| `pra-uk-crr-usd-5y` | Cross-bucket GIRR aggregation against USD bucket 2. | `pra_uk_crr_art_325r_girr_inter` |