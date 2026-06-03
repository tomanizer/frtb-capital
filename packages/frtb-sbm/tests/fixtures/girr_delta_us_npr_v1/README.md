Synthetic hand-checked fixture for the U.S. NPR 2.0 GIRR delta comparison slice.

The fixture uses the same three-row shape as `girr_delta_v1`, but runs under
`US_NPR_2_0` with profile-owned citation ids and reference payload hashing.
It is proposed-rule comparison material only and is not final regulatory
capital.

| Sensitivity | Purpose | Citation ids |
| --- | --- | --- |
| `us-npr-eur-1y` | EUR 1y GIRR delta sensitivity in bucket 1. | `us_npr_91_fr_14952_va7a_girr_buckets`, `us_npr_91_fr_14952_va7a_girr_delta_weights` |
| `us-npr-eur-5y` | Same-bucket EUR tenor diversification. | `us_npr_91_fr_14952_va7a_girr_intra` |
| `us-npr-usd-5y` | Cross-bucket GIRR aggregation against USD bucket 2. | `us_npr_91_fr_14952_va7a_girr_inter` |

