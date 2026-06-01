# sa_cva_girr_delta_v1 fixture pack

Synthetic SA-CVA GIRR delta cases for delivered-slice validation.

| Case | Regulatory intent | Citation ids |
| --- | --- | --- |
| single_usd_5y | Single specified-currency 5y CVA sensitivity | basel_mar50_56, basel_mar50_53 |
| usd_eur_two_bucket | Inter-bucket gamma aggregation | basel_mar50_55, basel_mar50_57 |
| offsetting_hedge | MAR50.55 hedging-disallowance floor | basel_mar50_55, basel_mar50_56 |
| ineligible_hedge_rejected | Ineligible hedge sensitivity receives no SA-CVA benefit | basel_mar50_37, basel_mar50_52 |
| chf_other_currency | 1.4× other-currency risk-weight scalar | basel_mar50_57 |
| invalid_fx_reporting_currency | FX reporting-currency bucket rejected before capital | validation |
| invalid_unknown_girr_tenor | Missing GIRR delta risk-weight lookup rejected | basel_mar50_56 |
| invalid_missing_tenor | Missing GIRR delta tenor rejected | validation |

Amounts use the positive regulatory CVA sign convention: positive CVA and
positive eligible hedge sensitivities offset through `WS_k = WS_k^CVA -
WS_k^Hdg`, consistent with MAR50.32(1) and the MAR50.52 footnote.

These fixtures are synthetic implementation references only; they do not represent final regulatory capital.
