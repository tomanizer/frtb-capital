# DRC CTP v1 Fixture

Synthetic CTP fixture for the U.S. NPR 2.0 DRC path.

The book has one explicitly replicated CDX.NA.IG S18 10-15 tranche exposure:

- long 10-15 market value 100
- short 10-12 market value 40
- short 12-15 market value 25

The three positions share the same `ctp_offset_group`, so the expected net
long exposure in the CDX_NA_IG bucket is 35. A second CDX_HY short index hedge
has market value 80. The CTP-wide HBR is therefore 35 / (35 + 80).

Hand-checked capital:

- CDX_NA_IG bucket: 35 x 20% = 7
- CDX_HY bucket: 0 - HBR x (80 x 30%) = -7.304347826086957
- CTP total: 7 + 0.5 x -7.304347826086957 = 3.3478260869565215
