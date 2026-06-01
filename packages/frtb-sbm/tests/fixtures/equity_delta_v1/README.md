# Equity delta fixture v1

Synthetic Basel MAR21 equity delta replay bundle exercising:

- MAR21.72 equity bucket assignment for buckets 5, 6, and 11;
- MAR21.77 spot and repo risk weights;
- MAR21.78 intra-bucket correlations including same-issuer spot/repo;
- MAR21.79 absolute-weight aggregation for bucket 11 (other sector);
- MAR21.80 inter-bucket correlations across buckets 5, 6, and 11;
- low, medium, and high correlation scenario selection.

Negative cases cover duplicate sensitivity ids, unsupported equity vega,
unsupported repo curvature, invalid bucket ids, invalid risk factors, and
missing issuer qualifiers.
