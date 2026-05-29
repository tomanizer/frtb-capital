# RRAO v1 synthetic validation fixture

This fixture is synthetic. It contains no proprietary market data and is not a
statement of final regulatory capital.

## Coverage

The fixture exercises the first public `frtb-rrao` capital-producing result
shape for the U.S. NPR 2.0 profile:

| Case | Position ids | Expected treatment | Citation ids |
| --- | --- | --- | --- |
| Exotic underlyings | `exotic-longevity-001`, `exotic-weather-001`, `exotic-natural-disaster-001` | 1.0% add-on | `us_npr_211_a_1`, `us_npr_211_c_1_i` |
| Gap risk | `other-gap-001` | 0.1% add-on | `us_npr_211_a_2`, `us_npr_211_c_1_ii` |
| Correlation risk | `other-correlation-001` | 0.1% add-on | `us_npr_211_a_2`, `us_npr_211_c_1_ii` |
| Behavioural risk | `other-behavioural-001` | 0.1% add-on | `us_npr_211_a_2`, `us_npr_211_c_1_ii` |
| Supervisor-directed inclusion | `supervisor-directed-001` | 0.1% add-on with directive evidence id | `us_npr_211_a_4`, `us_npr_211_c_1_ii` |
| Listed exclusion | `excluded-listed-001` | Zero-capital excluded line | `us_npr_211_b_1` |
| Clearable exclusion | `excluded-clearable-001` | Zero-capital excluded line | `us_npr_211_b_1` |
| Plain option exclusion | `excluded-plain-option-001` | Zero-capital excluded line | `us_npr_211_b_1` |
| Exact back-to-back exclusion | `excluded-back-to-back-001` | Zero-capital excluded line | `us_npr_211_b_2_i`, `us_npr_211_b_1` |
| Government/GSE debt exclusion | `excluded-gov-gse-001` | Zero-capital excluded line | `us_npr_211_b_2_iii`, `us_npr_211_b_1` |
| Fallback-capital exclusion | `excluded-fallback-001` | Zero-capital excluded line | `us_npr_211_b_2_iv`, `us_npr_211_b_1` |
| Invalid evidence | `invalid-investment-fund-001`, `invalid-exclusion-evidence-001`, `invalid-hint-conflict-001` | Explicit validation or classification failure | See `invalid_cases.json` |

## Files

- `positions.json`: supported canonical-input context and positions.
- `expected_outputs.json`: expected classifications, line add-ons, exclusions,
  subtotals, total capital, citations, warnings, and deterministic hashes.
- `invalid_cases.json`: unsupported or invalid evidence cases that must fail
  before a successful result is returned.
- `loader.py`: test-only loader that converts fixture JSON into frozen
  `frtb_rrao` dataclasses.
