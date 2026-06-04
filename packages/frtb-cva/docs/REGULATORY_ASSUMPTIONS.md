# CVA regulatory assumptions and implementation boundaries

This document records source-cited implementation decisions for `frtb-cva`.
For a plain-language summary, see
[`REGULATION_SUMMARY.md`](REGULATION_SUMMARY.md). For a bidirectional
code/regulation map, see [`REGULATORY_TRACEABILITY.md`](REGULATORY_TRACEABILITY.md).
For link-only source metadata, see [`regulatory_sources.yml`](regulatory_sources.yml).

`frtb-cva` delivers the package-owned implemented scope for reduced BA-CVA, full
BA-CVA, SA-CVA, mixed carve-out, qualified-index routing, attribution, impact,
adapter, batch, and audit paths under cited Basel MAR50 mechanics, with U.S.
NPR 2.0, EU CRR3, and UK PRA comparison profiles carrying their own citations
and profile hashes. No document or test in this package should describe outputs
as final regulatory capital.

## Phase basis

The current capital-producing slices target canonical inputs for:

1. Basel MAR50.14-MAR50.16 reduced BA-CVA, including Table 1 counterparty risk
   weights, alpha, supervisory discounting, `rho = 50%`, and `D_BA-CVA = 0.65`.
2. Basel MAR50.17-MAR50.26 full BA-CVA, including eligible single-name and
   index credit-spread hedge recognition and method-specific floors.
3. Basel MAR50.42-MAR50.77 SA-CVA, including portfolio-level CVA and hedge
   sensitivities, weighted-sensitivity netting, risk-class aggregation,
   hedging-disallowance scalar `R = 0.01`, and `m_CVA = 1.0`.
4. Basel MAR50.8 mixed carve-out, where SA-CVA is applied to the selected CVA
   portfolio and carved-out netting sets are calculated under BA-CVA.
5. Basel MAR50.50 qualified-index routing for CCS, RCS, and equity where the
   input supplies the required metadata.
6. Explicit fail-closed behavior for unsupported materiality
   alternative, undefined risk measures, incomplete hedge evidence, and
   unsupported method/input combinations.

U.S. NPR 2.0 section V.B is proposed-rule material. EU CRR3 is the runtime
profile for EU/ECB shorthand. UK PRA support references PS1/26 and the PRA
Rulebook CVA Risk Part effective from 1 January 2027. Any future
jurisdiction-specific numeric divergence must update citations, rule-profile
metadata, fixtures, expected results, and support-matrix rows in the same PR
that changes runtime behavior.

## Upstream-input boundary

The package receives prepared capital inputs. It does not simulate exposure
paths, price trades, calculate accounting CVA, source market data, operate a CVA
desk, or generate CVA sensitivities.

Callers are responsible for supplying:

- counterparty sector, credit quality, legal entity, desk, and source lineage;
- netting-set EAD, effective maturity, IMM flag, discount factor, and currency;
- hedge type, reference metadata, eligibility evidence, and internal/external
  transfer indicators;
- SA-CVA portfolio-level CVA and hedge sensitivities by risk class, measure,
  bucket, risk factor, tenor, and tag.

This boundary follows Basel MAR50.31-MAR50.36 for regulatory CVA modelling
principles and the package boundary in `CVA-BOUNDARY-003`.

## Profile-driven parameters

Risk weights, buckets, correlations, hedge eligibility rules, maturity and
discount policies, scalars, support flags, and citation ids belong in versioned
rule profiles and package reference-data helpers. Kernels receive typed values
and must not branch on hard-coded regulator names.

Every rule-driven quantity must carry a citation id linked to a Basel paragraph,
EU article, U.S. NPR section, PRA rule/source, or table in the active profile.

## BA-CVA assumptions

- Reduced BA-CVA applies the Basel MAR50.14 aggregation formula and MAR50.15
  stand-alone counterparty formula.
- `SCVA_c` uses `RW_c`, `M_NS`, `EAD_NS`, `DF_NS`, and `alpha = 1.4` under
  MAR50.15.
- IMM netting sets use `DF_NS = 1.0`; non-IMM netting sets may supply an
  explicit positive discount factor, or the profile helper computes
  `(1 - exp(-0.05 * M)) / (0.05 * M)` when the supplied value is the profile
  default sentinel `1.0`.
- Counterparty sector and credit quality must map to Basel MAR50.16 Table 1.
- Full BA-CVA recognises only eligible hedges with explicit evidence; ineligible
  hedges are rejected or excluded with audit records, never silently treated as
  capital-reducing.

## SA-CVA assumptions

- SA-CVA sensitivities are portfolio-level aggregate sensitivities under
  MAR50.47, not trade-level rows.
- Sensitivity tags distinguish `CVA` and `HDG`; permitted hedge benefit is
  applied through method-specific netting, not by implicit sign conventions.
- Supported SA-CVA vega paths require explicit `volatility_input`; kernels do
  not infer market volatilities from trade metadata.
- CCS vega is not capital-producing because MAR50.45 and MAR50.63 define CCS
  delta but no CCS vega capital path.
- SA-CVA capital calculation accepts sensitivity inputs and eligible hedge
  sensitivities only. Counterparty and netting-set inputs on the pure SA-CVA
  path are rejected unless the caller uses the mixed carve-out method.

## Jurisdiction profile boundary

The runtime profile matrix is explicit:

| Profile | Runtime status | Boundary |
| --- | --- | --- |
| `BASEL_MAR50_2020` | Capital-producing under audit | Basel MAR50 plus July 2020 d507 calibration. |
| `US_NPR20_VB` | Capital-producing comparison profile under audit | U.S. 91 FR 14952 section V.B profile-owned citation map; proposed-rule outputs are comparison evidence only. |
| `EU_CRR3_CVA` | Capital-producing comparison profile under audit | Regulation (EU) 2024/1623 Articles 381-386 and inserted Articles 383a-383z; ECB shorthand routes to this profile. |
| `UK_PRA_CVA` | Capital-producing comparison profile under audit | PRA PS1/26 and PRA Rulebook CVA Risk Part crosswalk; effective-date metadata is 1 January 2027. |

No comparison profile emits Basel citation ids or a Basel profile hash. Unmapped
future profiles must raise an explicit unsupported-feature error before capital
is calculated.

## Fail-closed unsupported scope

Any requested path without cited rule mapping and deterministic test evidence
must raise an explicit unsupported-feature or input error. The package must not
emit zero, empty, or placeholder capital for unsupported profiles, methods,
SA-CVA risk-class/measure combinations, hedge treatments, materiality
alternatives, or partial BA-CVA/SA-CVA combinations.

## Audit, attribution, and orchestration boundary

Successful `CvaCapitalResult` records carry stable ids, input/profile hashes,
method evidence, component totals, and reconciliation data. Optional attribution
and impact records must not change the capital number.

Top-of-house aggregation belongs in `frtb-orchestration`, not `frtb-cva`.
Durable run storage belongs in `frtb-result-store`; this package may expose
handoff and audit payloads but must not import result-store modules.

## Synthetic fixtures only

Tests, notebooks, and examples use synthetic canonical fixtures only. No
proprietary market data, counterparty master data, or adapter-specific
conventions are used in the core runtime path.
