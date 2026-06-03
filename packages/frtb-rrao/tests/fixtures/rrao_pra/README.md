# RRAO PRA UK CRR fixture

This fixture is synthetic. It contains no proprietary market data and is not a
statement of final regulatory capital.

## Coverage

The fixture exercises the `PRA_UK_CRR` profile for UK CRR Article 325u and UK
retained Delegated Regulation (EU) 2022/2328:

| Case | Position ids | Expected treatment | Citation ids |
| --- | --- | --- | --- |
| Article 1 exotic underlying | `pra-exotic-future-realised-volatility` | 1.0% add-on | `uk_rts_2022_2328_article_1`, `uk_crr_325u_3_a` |
| Article 2 Annex instrument | `pra-path-dependent-option` | 0.1% add-on | `uk_rts_2022_2328_article_2_annex`, `uk_crr_325u_3_b` |
| Article 3 non-presumptive risk | `pra-index-option-correlation` | Zero-capital audit line | `uk_rts_2022_2328_article_3` |

## Files

- `positions.json`: supported canonical-input context, positions, and expected
  fixture-level totals for `tests/test_rrao_pra_profile.py`.
