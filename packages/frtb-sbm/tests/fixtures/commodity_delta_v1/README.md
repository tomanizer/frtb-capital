# Commodity delta fixture v1

Synthetic Basel MAR21 commodity delta replay bundle exercising:

- MAR21.81 commodity bucket assignment for buckets 2 and 5;
- MAR21.82 uniform bucket risk weights;
- MAR21.83 intra-bucket correlations across commodity, tenor, and location;
- MAR21.85 20% inter-bucket correlation across energy-liquid and metals buckets;
- low, medium, and high correlation scenario selection.

Negative cases cover duplicate sensitivity ids, unsupported commodity vega,
missing tenor or location qualifiers, and invalid bucket ids.
