Synthetic hand-checked fixture for the U.S. NPR 2.0 GIRR vega comparison slice.

The fixture mirrors the Basel GIRR vega row shape, but runs under `US_NPR_2_0`
with profile-owned citation ids and reference payload hashing. It is
proposed-rule comparison material only and is not final regulatory capital.

| Sensitivity | Purpose | Citation ids |
| --- | --- | --- |
| `us-npr-eur-vega-1y` | EUR 1y option and underlying tenor vega sensitivity in bucket 1. | `us_npr_91_fr_14952_va7a_girr_buckets`, `us_npr_91_fr_14952_va7a_girr_vega_option_tenors`, `us_npr_91_fr_14952_va7a_girr_vega_lh_rw` |
| `us-npr-eur-vega-5y` | Same-bucket EUR tenor diversification for vega. | `us_npr_91_fr_14952_va7a_girr_vega_intra` |
| `us-npr-usd-vega-5y` | Cross-bucket GIRR vega aggregation against USD bucket 2. | `us_npr_91_fr_14952_va7a_girr_inter` |
