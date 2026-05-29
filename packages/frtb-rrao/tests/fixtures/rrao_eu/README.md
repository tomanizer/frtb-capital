# RRAO EU comparison fixture

This fixture is synthetic. It contains no proprietary market data and is not a
statement of final regulatory capital.

## Coverage

The fixture exercises the EU CRR3 comparison profile for Article 325u and
Delegated Regulation (EU) 2022/2328:

| Case | Position ids | Expected treatment | Citation ids |
| --- | --- | --- | --- |
| Article 1 exotic underlying | `eu-exotic-future-realised-volatility` | 1.0% add-on | `eu_rts_2022_2328_article_1`, `eu_crr_325u_3_a` |
| Article 2 Annex instrument | `eu-path-dependent-option` | 0.1% add-on | `eu_rts_2022_2328_article_2_annex`, `eu_crr_325u_3_b` |
| Article 3 non-presumptive risk | `eu-index-option-correlation` | Zero-capital audit line | `eu_rts_2022_2328_article_3` |

## Files

- `positions.json`: supported canonical-input context, positions, and expected
  fixture-level totals for `tests/test_eu_profile.py`.
