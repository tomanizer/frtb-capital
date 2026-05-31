# CVA regulatory traceability

## Purpose

This document maps `frtb-cva` package code to Basel MAR50 and planned comparison
profiles. It is a traceability aid for implementation and review; it is not legal
advice and it does not make unsupported features capital-producing.

Companion source manifest: [`regulatory_sources.yml`](regulatory_sources.yml).

## Status taxonomy

| Status | Meaning |
| --- | --- |
| Scaffold | Importable boundary with explicit failure for unsupported paths. |
| Planned | Issue-backed and source-mapped, but not yet capital-producing. |
| Partial | Delivered slice with cited behaviour; broader MAR50 scope still unsupported. |
| Implemented | Tested code produces cited behaviour for supported inputs. |
| Unsupported | Fail closed until profile or feature has cited rules and fixtures. |

## Delivered slice (implemented modules)

| Module | Responsibility | Basel reference | Status |
| --- | --- | --- | --- |
| `data_models.py` | Frozen CVA inputs and result records | MAR50.1-MAR50.9 | Implemented |
| `validation.py` | Input invariants and `CvaInputError` | MAR50.15 exposure inputs | Implemented |
| `reference_data.py` | Table 1 RW, alpha, rho, D_BA-CVA, GIRR delta tables | MAR50.14-MAR50.16, MAR50.54-MAR50.57 | Implemented |
| `regimes.py` | Profile lookup and deterministic profile hash | MAR50 profile context | Implemented |
| `scope.py` | Method selection and carve-out policy | MAR50.8-MAR50.9 | Implemented |
| `ba_cva.py` | Stand-alone and reduced portfolio BA-CVA | MAR50.14-MAR50.15 | Implemented |
| `weighted_sensitivity.py` | SA-CVA weighted sensitivity assembly | MAR50.56 | Implemented |
| `aggregation.py` | SA-CVA intra- and inter-bucket capital | MAR50.53, MAR50.55-MAR50.57 | Implemented |
| `hedges.py` | SA-CVA hedge eligibility assessment | MAR50.37-MAR50.39 | Partial |
| `risk_classes/girr.py` | GIRR delta bucket routing | MAR50.54-MAR50.57 | Implemented |
| `sa_cva.py` | SA-CVA GIRR delta orchestration | MAR50.53-MAR50.57 | Implemented |
| `capital.py` | Public `calculate_cva_capital` | MAR50.14 reduced, MAR50.53 SA-CVA | Implemented |
| `audit.py` | Input hash, serialization, reconciliation | Audit traceability | Implemented |

July 2020 calibration revision notes: `m_CVA = 1.0`, `D_BA-CVA = 0.65`.

## Unsupported in the delivered slice

- Full BA-CVA hedge recognition (MAR50.17-MAR50.26)
- SA-CVA risk classes other than GIRR delta (MAR50.40-MAR50.52, MAR50.58+)
- Mixed carve-out assembly (MAR50.8 with SA-CVA)
- Materiality-threshold alternative (MAR50.9)
- U.S., EU, and UK comparison profiles
