# U.S. NPR 2.0 equity delta fixture v1

Synthetic proposed-rule comparison fixture for the U.S. NPR 2.0 equity delta SBM cell.

The fixture reuses the Basel equity delta row shape for buckets 5, 6, and 11, but runs under `US_NPR_2_0` with profile-owned citation ids for equity delta factors, buckets, weights, intra-bucket correlations, other-sector absolute aggregation, and inter-bucket correlations. It is proposed-rule comparison material only and is not final regulatory capital.

Negative cases cover duplicate sensitivity ids, unsupported equity vega and curvature cells, invalid bucket ids, invalid risk factors, and missing issuer qualifiers.
