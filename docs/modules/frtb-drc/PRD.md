# FRTB DRC Product Requirements Document

## Objective

Build `frtb-drc`, a transparent Python package for default risk capital under
the FRTB standardised approach. The package must accept synthetic issuer,
tranche, and default exposure inputs, calculate gross and net JTD, apply
regime-specific risk weights and hedge benefit rules, and produce audit-grade
capital breakdowns.

## Users

- Quant developers validating capital mechanics.
- Model risk reviewers checking traceability and reproducibility.
- Risk managers comparing Basel, U.S. NPR 2.0, CRR3, and PRA-style policy
  profiles.
- Suite orchestrators combining DRC with SA SBM, RRAO, CVA, and IMA outputs.

## Non-Goals

- No market data sourcing.
- No pricing or P&L generation.
- No proprietary issuer data.
- No final regulatory filing output.
- No silent approximation for unsupported securitisation or CTP cases.

## Functional Scope

1. Core data contracts for DRC positions, gross JTD, net JTD, bucket capital,
   and aggregate capital.
2. Reference data for seniority, buckets, credit quality, LGD, maturity scaling,
   and risk weights by regulatory profile.
3. Non-securitisation DRC calculation path.
4. Securitisation non-CTP DRC calculation path.
5. Correlation trading portfolio DRC calculation path.
6. Regime policy layer for Basel, U.S. NPR 2.0, CRR3, and PRA placeholders.
7. Deterministic audit records and Markdown/JSON-ready outputs.
8. Synthetic fixtures covering long/short offsetting, LGD categories, defaulted
   positions, securitisation tranche cases, and CTP aggregation.

## Architecture

| Layer | Responsibility |
| --- | --- |
| `data_models.py` | Frozen dataclasses and enums only. |
| `reference_data.py` | Pure regime tables and lookup helpers. |
| `gross_jtd.py` | Gross default exposure and long/short direction. |
| `netting.py` | Issuer/tranche netting and maturity scaling. |
| `capital.py` | Hedge benefit ratio, bucket capital, category aggregation. |
| `crif.py` | CRIF-to-canonical mapping. |
| `audit.py` | Serialisable audit records and reconciliation helpers. |
| `regimes.py` | Policy selection and unsupported-feature declarations. |

## Delivery Slices

1. **Package skeleton and source register**: package metadata, docs,
   regulatory source manifest, no calculation yet.
2. **Reference data and data models**: enums, dataclasses, LGD tables, risk
   weights, CRIF mapping, validation tests.
3. **Non-securitisation gross/net JTD**: long/short direction, maturity
   scaling, seniority-aware netting, synthetic tests.
4. **Non-securitisation bucket capital**: hedge benefit ratio, risk weighting,
   category total, audit breakdown.
5. **Securitisation non-CTP**: tranche data, attachment/detachment handling,
   non-CTP buckets, tests.
6. **CTP DRC**: CTP-specific aggregation and hedge recognition, tests.
7. **Run-level result and suite integration**: public API, examples, audit
   report, orchestration contract.

## Acceptance Criteria

- Every calculation has deterministic unit tests.
- Every regulatory threshold has a paragraph or article citation.
- LGD defaults match cited source values.
- No sibling package imports.
- Unsupported regulatory features fail explicitly.
- Results reconcile: sum of bucket/category components equals total DRC.
- Synthetic examples run from workspace root with `uv run`.

## Risks

- Securitisation treatment is more complex than core non-sec DRC. Split it into
  separate delivery slices and fail closed until source mapping is complete.
- U.S. NPR 2.0 is proposed-rule material. Label all U.S. outputs as proposed
  and keep Basel defaults separately selectable.
- The reference implementation is reconstructed from video and has placeholder
  markers. Use it for naming and workflow inspiration only.
