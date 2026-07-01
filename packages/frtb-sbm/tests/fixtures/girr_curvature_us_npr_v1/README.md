Synthetic hand-checked fixture for the U.S. NPR 2.0 GIRR curvature comparison slice.

The fixture mirrors the Basel GIRR curvature row shape, but runs under
`US_NPR_2_0` with profile-owned citation ids and reference payload hashing. It
is proposed-rule comparison material only and is not final regulatory capital.

| Sensitivity | Purpose | Citation ids |
| --- | --- | --- |
| `us-npr-usd-ois-curv` | USD OIS up/down curvature branch input in bucket 2. | `us_npr_91_fr_14952_va7a_girr_buckets`, `us_npr_91_fr_14952_va7a_girr_curvature_factors`, `us_npr_91_fr_14952_va7a_girr_curvature_shocks` |
| `us-npr-usd-libor-curv` | Same-bucket USD curve diversification and branch selection. | `us_npr_91_fr_14952_va7a_girr_curvature_intra` |
| `us-npr-eur-ois-curv` | Cross-bucket GIRR curvature aggregation against EUR bucket 1. | `us_npr_91_fr_14952_va7a_girr_curvature_inter` |
