# sa_cva_girr_delta_v1 fixture pack

Synthetic SA-CVA GIRR delta cases for delivered-slice validation.

| Case | Regulatory intent | Citation ids |
| --- | --- | --- |
| single_usd_5y | Single specified-currency 5y CVA sensitivity | basel_mar50_56, basel_mar50_53 |
| usd_eur_two_bucket | Inter-bucket gamma aggregation | basel_mar50_55, basel_mar50_57 |
| offsetting_hedge | MAR50.55 hedging-disallowance floor | basel_mar50_55, basel_mar50_56 |
| chf_other_currency | 1.4× other-currency risk-weight scalar | basel_mar50_57 |
| invalid_non_girr | Non-GIRR sensitivity rejected before capital | validation |
| invalid_missing_tenor | Missing GIRR delta tenor rejected | validation |

These fixtures are synthetic implementation references only; they do not represent final regulatory capital.
