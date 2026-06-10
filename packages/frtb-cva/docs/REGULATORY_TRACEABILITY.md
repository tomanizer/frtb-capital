# CVA regulatory traceability

## Purpose

This document maps `frtb-cva` package code to Basel MAR50 and comparison
profiles. It is a traceability aid for implementation and review; it is not
legal advice and it does not make outputs final regulatory capital.

Companion source manifest: [`regulatory_sources.yml`](regulatory_sources.yml).

## Status taxonomy

| Status | Meaning |
| --- | --- |
| Scaffold | Importable boundary with explicit failure for unsupported paths. |
| Planned | Issue-backed and source-mapped, but not yet capital-producing. |
| Partial | Delivered slice with cited behaviour; broader MAR50 scope still unsupported. |
| Implemented | Tested code produces cited behaviour for supported inputs. |
| Unsupported | Fail closed until profile or feature has cited rules and fixtures. |

Runtime support-matrix rows use lower-case status values:

| Runtime status | Meaning |
| --- | --- |
| `implemented_under_audit` | Capital-producing path with cited runtime code and package-local tests. |
| `unsupported_fail_closed` | Requested path is recognised but raises before capital is produced. |
| `regulatory_absence` | No capital path is defined by the cited rule text. |
| `out_of_scope` | Boundary item belongs to upstream systems, governance, or orchestration rather than the CVA capital kernel. |

Runtime profile status values:

| Profile status | Meaning |
| --- | --- |
| `capital_producing` | Profile has package-local reference data, tests, and audit evidence for capital-producing CVA methods. |
| `comparison_fail_closed` | Profile is source-mapped for comparison, but capital-producing support is blocked until profile-specific fixtures or an explicit equivalence decision exist. |

## Delivered slice (implemented modules)

| Module | Responsibility | Basel reference | Status |
| --- | --- | --- | --- |
| `data_models.py` | Frozen CVA inputs and result records | MAR50.1-MAR50.9 | Implemented |
| `validation.py` | Input invariants and `CvaInputError` | MAR50.15 exposure inputs | Implemented |
| `reference_data.py` | BA-CVA Table 1 RW, alpha, rho, beta, D_BA-CVA, SA-CVA multipliers, risk weights, and correlation tables | MAR50.14-MAR50.26, MAR50.42-MAR50.77 | Implemented |
| `regimes.py` | Profile lookup and deterministic profile hash | MAR50 profile context | Implemented |
| `scope.py` | Method selection and carve-out policy | MAR50.8-MAR50.9 | Implemented |
| `ba_cva.py` | Stand-alone and reduced portfolio BA-CVA | MAR50.14-MAR50.15 | Implemented |
| `weighted_sensitivity.py` | SA-CVA weighted sensitivity assembly | MAR50.56 | Implemented |
| `aggregation.py` | SA-CVA intra- and inter-bucket capital | MAR50.53, MAR50.55-MAR50.57 | Implemented |
| `hedges.py` | SA-CVA and BA-CVA hedge eligibility | MAR50.18-MAR50.19, MAR50.37-MAR50.39 | Implemented |
| `ba_cva.py` | Full BA-CVA hedge recognition | MAR50.17-MAR50.26 | Implemented |
| `qualified_index.py` | MAR50.50 index-bucket routing | MAR50.50, MAR50.63, MAR50.72 | Implemented |
| `crif.py` | Vendor-to-canonical adapter | CVA-FUNC-026 | Implemented |
| `attribution.py` | Analytical attribution (supported branches) | ADR 0012 | Partial |
| `impact.py` | Baseline-vs-candidate impact | ADR 0012 | Implemented |
| `risk_classes/girr.py` | GIRR delta and vega bucket routing | MAR50.54-MAR50.58 | Implemented |
| `risk_classes/fx.py` | FX delta and vega bucket routing | MAR50.59-MAR50.62 | Implemented |
| `risk_classes/ccs.py` | Counterparty credit spread delta and qualified-index bucket routing | MAR50.45, MAR50.50, MAR50.63-MAR50.65 | Implemented; CCS vega fail-closed |
| `risk_classes/rcs.py` | Reference credit spread delta and vega bucket routing | MAR50.50, MAR50.66-MAR50.69 | Implemented |
| `risk_classes/equity.py` | Equity delta and vega bucket routing with qualified-index handling | MAR50.50, MAR50.70-MAR50.73 | Implemented |
| `risk_classes/commodity.py` | Commodity delta and vega bucket routing | MAR50.74-MAR50.77 | Implemented |
| `sa_cva.py` | SA-CVA risk-class orchestration across supported delta and vega paths | MAR50.42-MAR50.77 | Implemented |
| `batch.py`, `arrow_batch.py` | Package-owned columnar batches and Arrow batch normalisation | ADR 0023; MAR50 calculation boundary | Implemented |
| `capital.py` | Public `calculate_cva_capital` | MAR50.8, MAR50.14-MAR50.26, MAR50.42-MAR50.77 | Implemented |
| `audit.py` | Input hash, serialization, reconciliation | Audit traceability | Implemented |

July 2020 calibration revision notes: `m_CVA = 1.0`, `D_BA-CVA = 0.65`.

## Profile x method support matrix

Runtime source of truth: `frtb_cva.support_matrix.cva_profile_support_matrix`.
`BASEL_MAR50_2020` is the calibration anchor. `US_NPR20_VB`, `EU_CRR3_CVA`, and
`UK_PRA_CVA` are capital-producing comparison profiles under audit: they use
package-local profile citation maps, deterministic profile hashes, and the
`profile_comparison_v1` fixture to evidence BA-CVA and SA-CVA source ids,
citation ids, support-matrix rows, and crosswalk source refs. These comparison
outputs remain proposed-rule or jurisdiction-specific audit evidence, not final
regulatory capital. ECB shorthand is normalised to `EU_CRR3_CVA`, not a separate
runtime profile. SA-CVA supervisory approval workflow and exposure / sensitivity
generation are out of scope package-boundary rows for every profile.

| Profile | Method or policy | Status | Citation | Blocker |
| --- | --- | --- | --- | --- |
| `BASEL_MAR50_2020` | `BA_CVA_REDUCED` | `implemented_under_audit` | MAR50.14-MAR50.16 | none |
| `BASEL_MAR50_2020` | `BA_CVA_FULL` | `implemented_under_audit` | MAR50.17-MAR50.26 | none |
| `BASEL_MAR50_2020` | `SA_CVA` | `implemented_under_audit` | MAR50.42-MAR50.77 | none |
| `BASEL_MAR50_2020` | `MIXED_CARVE_OUT` | `implemented_under_audit` | MAR50.8 | none |
| `BASEL_MAR50_2020` | `MAR50.9_MATERIALITY_THRESHOLD_CCR` | `unsupported_fail_closed` | MAR50.9 | CCR input and orchestration boundary |
| `US_NPR20_VB` | all CVA methods and supported SA-CVA paths | `implemented_under_audit` | U.S. NPR 2.0 91 FR 14952 section V.B | none |
| `US_NPR20_VB` | materiality / simplified CCR substitution | `unsupported_fail_closed` | U.S. NPR 2.0 91 FR 14952 section V.B | CCR input and orchestration boundary |
| `EU_CRR3_CVA` | all CVA methods and supported SA-CVA paths | `implemented_under_audit` | Regulation (EU) 2024/1623 Articles 381-386 and 383a-383z | none |
| `EU_CRR3_CVA` | materiality / simplified CCR substitution | `unsupported_fail_closed` | Regulation (EU) 2024/1623 Article 385 | CCR input and orchestration boundary |
| `UK_PRA_CVA` | all CVA methods and supported SA-CVA paths | `implemented_under_audit` | PRA PS1/26; PRA Rulebook CVA Risk Part | none |
| `UK_PRA_CVA` | materiality / alternative approach | `unsupported_fail_closed` | PRA Rulebook CVA Risk Part AA-CVA provisions | CCR input and orchestration boundary |
| all supported profiles | `SA_CVA_APPROVAL_GOVERNANCE_WORKFLOW` | `out_of_scope` | profile-specific SA-CVA approval sources | supervisory approval boundary |
| all supported profiles | `EXPOSURE_SIMULATION_AND_SENSITIVITY_GENERATION` | `out_of_scope` | profile-specific CVA exposure and sensitivity sources | upstream exposure/sensitivity boundary |

## BASEL_MAR50_2020 SA-CVA risk-class support matrix

| Risk class | Measure | Status | Citation | Blocker |
| --- | --- | --- | --- | --- |
| `COMMODITY` | `DELTA` | `implemented_under_audit` | MAR50.74-MAR50.77 | none |
| `COMMODITY` | `VEGA` | `implemented_under_audit` | MAR50.74-MAR50.77 | none |
| `COUNTERPARTY_CREDIT_SPREAD` | `DELTA` | `implemented_under_audit` | MAR50.45, MAR50.50, MAR50.63-MAR50.65 | none |
| `COUNTERPARTY_CREDIT_SPREAD` | `VEGA` | `regulatory_absence` | MAR50.45, MAR50.63 | CCS vega is not defined |
| `EQUITY` | `DELTA` | `implemented_under_audit` | MAR50.70-MAR50.73 | none |
| `EQUITY` | `VEGA` | `implemented_under_audit` | MAR50.70-MAR50.73 | none |
| `FX` | `DELTA` | `implemented_under_audit` | MAR50.59-MAR50.62 | none |
| `FX` | `VEGA` | `implemented_under_audit` | MAR50.59-MAR50.62 | none |
| `GIRR` | `DELTA` | `implemented_under_audit` | MAR50.54-MAR50.58 | none |
| `GIRR` | `VEGA` | `implemented_under_audit` | MAR50.54-MAR50.58 | none |
| `REFERENCE_CREDIT_SPREAD` | `DELTA` | `implemented_under_audit` | MAR50.50, MAR50.66-MAR50.69 | none |
| `REFERENCE_CREDIT_SPREAD` | `VEGA` | `implemented_under_audit` | MAR50.50, MAR50.66-MAR50.69 | none |

## Unsupported and out of scope in the delivered slice

- `unsupported_fail_closed`: materiality-threshold alternative (MAR50.9).
- `unsupported_fail_closed`: analogous simplified CCR-substitution alternatives
  in non-Basel profiles.
- `regulatory_absence`: CCS vega capital, because MAR50.45 and MAR50.63 define
  CCS delta but no CCS vega path.
- `out_of_scope`: SA-CVA approval or governance workflow.
- `out_of_scope`: exposure simulation and CVA sensitivity generation.
