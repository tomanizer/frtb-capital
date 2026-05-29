# RRAO Sample Book v1

Synthetic deterministic fixture covering 25 positions across 7 desks and 3 legal entities.
Used by the `notebooks/` walkthroughs to demonstrate the analytic model code end-to-end.

## Position groups

| Group | Desk | Evidence types | Positions |
|---|---|---|---|
| A | `desk-exotics` (LE-IB-NY) | `EXOTIC_UNDERLYING` | sb-001–004 |
| B | `desk-structured` (LE-IB-NY) | `GAP_RISK` | sb-005–006 |
| C | `desk-structured` (LE-IB-NY) | `CORRELATION_RISK` | sb-007–008 |
| D | `desk-structured` (LE-IB-NY) | `MULTIPLE_STRIKE_OR_BARRIER_OPTIONALITY` | sb-009 |
| E | `desk-ctp` (LE-IB-LDN) | `CTP_THREE_OR_MORE_UNDERLYINGS` | sb-010–011 |
| F | `desk-ctp` (LE-IB-LDN) | `NON_REPLICABLE_OPTIONALITY` | sb-012 |
| G | `desk-mortgages` (LE-RTL-NY) | `BEHAVIOURAL_RISK` | sb-013–014 |
| H | `desk-supervisory` (LE-IB-NY) | `SUPERVISOR_DIRECTIVE` (US NPR only) | sb-015 |
| I | `desk-funds` (LE-IB-NY) | `INVESTMENT_FUND_EXPOSURE` (US NPR only) | sb-016–017 |
| J | `desk-exclusions` (LE-IB-NY) | Common exclusions (Basel + NPR) | sb-018–022 |
| K | `desk-exclusions` (LE-IB-NY) | US NPR-only exclusions | sb-023–025 |

## Expected outputs (US NPR 2.0)

| Classification | Lines | Add-on |
|---|---|---|
| EXOTIC | 5 | $1,300,000 |
| OTHER_RESIDUAL_RISK | 11 | $1,625,000 |
| SUPERVISOR_DIRECTED | 1 | $75,000 |
| **Total RRAO** | **17** | **$3,000,000** |
| EXCLUDED | 8 | $0 |

## Regenerating

```bash
# From packages/frtb-rrao
python scripts/generate_fixture.py --output tests/fixtures/rrao_sample_book_v1
```

## Profile compatibility

Positions `sb-015` (SUPERVISOR_DIRECTIVE), `sb-016/017` (INVESTMENT_FUND_EXPOSURE),
and `sb-023/024/025` (US NPR-only exclusion reasons) are incompatible with Basel MAR23
and will raise `RraoInputError` if presented to that profile.  See notebook 04 for
the multi-profile comparison.
