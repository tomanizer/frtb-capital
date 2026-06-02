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
- Suite orchestrators combining DRC with SBM, RRAO, CVA, and IMA outputs.

## Non-Goals

- No market data sourcing.
- No pricing or P&L generation.
- No proprietary issuer data.
- No final regulatory filing output.
- No silent approximation for unsupported profile, securitisation, or CTP
  cases.

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
9. Attribution records for stable analytical Euler contribution with explicit
   residual or unsupported records, plus audit lineage for future
   baseline-vs-candidate impact assessment.

## Architecture

| Layer | Responsibility |
| --- | --- |
| `data_models.py` | Frozen dataclasses and enums only. |
| `reference_data.py` | Pure regime tables and lookup helpers. |
| `gross_jtd.py` | Gross default exposure and long/short direction. |
| `netting.py` | Issuer/tranche netting and maturity scaling. |
| `capital.py` | Hedge benefit ratio, bucket capital, category aggregation. |
| `attribution.py` | Analytical Euler, residual, and unsupported attribution over capital audit records. |
| `impact.py` | Future baseline-vs-candidate capital delta analysis. |
| `crif.py` | CRIF-to-canonical mapping. |
| `audit.py` | Serialisable audit records and reconciliation helpers. |
| `regimes.py` | Policy selection and unsupported-feature declarations. |

## Implementation Standards

`frtb-drc` owns canonical issuer, tranche, and default-exposure input records.
The public boundary records long/short direction, issuer or tranche identity,
seniority, rating or credit quality, maturity, LGD category, JTD amount,
currency, source row id, and sign convention explicitly. CRIF or vendor-shaped
records must be mapped before calculation starts.

Risk weights, maturity-scaling rules, hedge-benefit rules, bucket definitions,
and securitisation/CTP switches come from a versioned rule profile supplied
through `frtb-common`. Calculation kernels receive typed inputs and profile
data; they do not reach into external data sources or global regime constants.

Results must expose gross JTD, net JTD, hedge-benefit ratio, bucket/category
capital, total DRC, rule profile id and hash, input snapshot hash, source
citation ids, attribution-ready lineage, branch metadata, and
unsupported-feature or fallback status where applicable.
Implemented U.S. NPR 2.0 securitisation non-CTP and CTP paths consume cited
upstream risk-weight evidence rather than deriving banking-book securitisation
weights internally. Basel MAR22 securitisation non-CTP and CTP, EU CRR3, and
PRA UK CRR paths fail closed until their cited rule mappings and fixtures are
complete.

## Delivery Slices

1. **Package skeleton and source register**: package metadata, docs,
   regulatory source manifest, no calculation yet.
2. **Reference data and data models**: enums, dataclasses, LGD tables, risk
   weights, CRIF mapping, validation tests.
3. **Non-securitisation gross/net JTD**: long/short direction, maturity
   scaling, seniority-aware netting, synthetic tests.
4. **Non-securitisation bucket capital**: hedge benefit ratio, risk weighting,
   category total, audit breakdown.
5. **Securitisation non-CTP**: tranche data, fair-value cap evidence,
   replication evidence, non-CTP buckets, row/batch parity, and tests.
6. **CTP DRC**: CTP-specific gross exposure, replication evidence, aggregation,
   hedge recognition, row/batch parity, and tests.
7. **Run-level result and suite integration**: public API, examples, audit
   report, orchestration contract.
8. **Attribution and impact**: analytical Euler contribution where supported,
   explicit fallback or unsupported states, and reconciliation tests are
   implemented; baseline-vs-candidate capital deltas remain future work.

## Acceptance Criteria

- Every calculation has deterministic unit tests.
- Every regulatory threshold has a paragraph or article citation.
- LGD defaults match cited source values.
- No sibling package imports.
- Unsupported regulatory features fail explicitly.
- Results reconcile: sum of bucket/category components equals total DRC.
- Public results carry rule-profile and input-snapshot hashes.
- Calculation kernels are pure and `numpy`-friendly where aggregation size
  matters.
- Synthetic examples run from workspace root with `uv run`.

## Risks

- Securitisation and CTP treatment remains profile-sensitive. U.S. NPR 2.0
  paths rely on cited upstream risk-weight and decomposition evidence; Basel
  securitisation and CTP, EU, and PRA mappings must continue to fail closed
  until implemented with profile-specific citations and tests.
- U.S. NPR 2.0 is proposed-rule material. Label all U.S. outputs as proposed
  and keep Basel defaults separately selectable.
- The reference implementation is reconstructed from video and has placeholder
  markers. Use it for naming and workflow inspiration only.
