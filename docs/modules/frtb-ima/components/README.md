# IMA Component Map

The Internal Models Approach is documented as one package with internal
components. The components have separate modules, tests, traceability rows, and
validation evidence, but they share one package version and one IMA capital
contract.

| Component | Role | Package evidence |
| --- | --- | --- |
| [RFET](rfet.md) | Classifies risk factors as modellable or non-modellable before capital routing. | `rfet.py`, `rfet_evidence.py`, requirement IDs `NPR-MR-RFET-*`. |
| [Stress-period selection](stress-period.md) | Selects and validates stress windows and stress artifacts used by IMA calculations. | `stress_periods.py`, `nmrf_stress_spec.py`. |
| [Expected shortfall and IMCC](expected-shortfall-imcc.md) | Computes ES, liquidity-horizon adjusted ES, reduced-set ES, and IMCC. | `expected_shortfall.py`, `liquidity_horizon.py`, `lha_builder.py`, `imcc.py`, `reduced_set.py`. |
| [NMRF and SES](nmrf-ses.md) | Routes non-modellable risk factors and computes stress-scenario capital. | `nmrf.py`, `nmrf_method_selection.py`, `nmrf_valuation_run.py`. |
| [PLA](pla.md) | Calculates profit-and-loss attribution diagnostics for desk eligibility. | `pla.py`, `regimes.py`. |
| [Backtesting](backtesting.md) | Calculates VaR exceptions and supervisory multiplier inputs. | `backtesting.py` public path, focused `backtesting_*` modules. |
| [Capital assembly](capital-assembly.md) | Combines IMCC, SES, multiplier, and PLA add-on into IMA capital. | `capital.py`, `audit.py`, `audit_inputs.py`. |

The suite orchestrator sees IMA through package-level outputs, not through these
internal steps. This keeps package ownership stable while allowing targeted
component documentation and tests.
