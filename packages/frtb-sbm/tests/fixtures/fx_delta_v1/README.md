# FX delta fixture v1

Synthetic Basel MAR21 FX delta replay bundle exercising:

- MAR21.86 currency buckets versus USD reporting currency;
- MAR21.87 uniform 15% risk weight;
- MAR21.88 sqrt(2) reduction for EUR and GBP specified pairs;
- MAR21.89 60% inter-bucket correlation across EUR, GBP, and MYR buckets;
- low, medium, and high correlation scenario selection.

Negative cases cover duplicate sensitivity ids, missing FX vega option tenor,
invalid bucket currency codes, and bucket/risk_factor mismatches.
