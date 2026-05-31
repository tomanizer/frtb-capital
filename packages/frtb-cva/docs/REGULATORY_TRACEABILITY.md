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
| Partial | Reduced BA-CVA slice implemented; SA-CVA and full BA-CVA remain unsupported. |
| Implemented | Tested code produces cited behaviour for supported inputs. |
| Unsupported | Fail closed until profile or feature has cited rules and fixtures. |

## Phase 1 implemented slice

| Module | Responsibility | Basel reference | Status |
| --- | --- | --- | --- |
| `data_models.py` | Frozen CVA inputs and result records | MAR50.1-MAR50.9 | Implemented |
| `validation.py` | Input invariants and `CvaInputError` | MAR50.15 exposure inputs | Implemented |
| `reference_data.py` | Table 1 RW, alpha, rho, D_BA-CVA, GIRR delta tables | MAR50.14-MAR50.16, MAR50.54-MAR50.57 | Implemented |
| `regimes.py` | Profile lookup and deterministic profile hash | MAR50 profile context | Implemented |
| `scope.py` | Method selection and carve-out policy | MAR50.8-MAR50.9 | Implemented |
| `ba_cva.py` | Stand-alone and reduced portfolio BA-CVA | MAR50.14-MAR50.15 | Implemented |
| `capital.py` | Public `calculate_cva_capital` | MAR50.14 reduced path | Implemented |
| `audit.py` | Input hash, serialization, reconciliation | Audit traceability | Implemented |

July 2020 calibration revision notes: `m_CVA = 1.0`, `D_BA-CVA = 0.65`.

## Unsupported in phase 1

- Full BA-CVA hedge recognition (MAR50.17-MAR50.26)
- SA-CVA capital calculation (MAR50.40-MAR50.77)
- Mixed carve-out assembly (MAR50.8 with SA-CVA)
- Materiality-threshold alternative (MAR50.9)
- U.S., EU, and UK comparison profiles
