# U.S. NPR 2.0 commodity delta fixture v1

Synthetic proposed-rule comparison fixture for the U.S. NPR 2.0 commodity delta SBM cell.

The fixture reuses the Basel commodity delta row shape and adds NPR-only bucket 12 (`Commodity index`) so bucket definitions, weights, intra-bucket correlations, and inter-bucket correlations are all exercised with profile-owned citation ids. It is proposed-rule comparison material only and is not final regulatory capital.

Negative cases cover duplicate sensitivity ids, unsupported commodity vega and curvature cells, missing tenor and qualifier fields, and invalid bucket ids.
