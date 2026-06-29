Synthetic hand-checked fixture for the EU CRR3 GIRR delta comparison slice.

The fixture uses the same three-row shape as `girr_delta_v1`, but runs under
`EU_CRR3` with profile-owned citation ids and reference payload hashing.
It is comparison material only and is not final regulatory capital.

| Sensitivity | Purpose | Citation ids |
| --- | --- | --- |
| `eu-crr3-eur-1y` | EUR 1y GIRR delta sensitivity in bucket 1. | `eu_crr3_art_325r_girr_buckets`, `eu_crr3_art_325r_girr_delta_weights` |
| `eu-crr3-eur-5y` | Same-bucket EUR tenor diversification. | `eu_crr3_art_325r_girr_intra` |
| `eu-crr3-usd-5y` | Cross-bucket GIRR aggregation against USD bucket 2. | `eu_crr3_art_325r_girr_inter` |