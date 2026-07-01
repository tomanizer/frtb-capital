# FX delta U.S. NPR fixture v1

Synthetic U.S. NPR 2.0 reporting-currency FX delta replay bundle exercising:

- Federal Register 91 FR 15020 section V.A.7.a reporting-currency FX policy;
- U.S. NPR profile-owned currency buckets versus USD reporting currency;
- uniform 15% risk weight;
- sqrt(2) reduction for EUR and GBP specified pairs;
- 60% inter-bucket correlation across EUR, GBP, and MYR buckets;
- low, medium, and high correlation scenario selection.

Negative cases cover duplicate sensitivity ids, unsupported U.S. NPR FX vega
and curvature cells, invalid bucket currency codes, and bucket/risk_factor
mismatches. Runtime tests separately cover fail-closed base-currency treatment.
