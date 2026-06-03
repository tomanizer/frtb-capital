# Regulatory traceability

## Purpose

This document is the cross-reference between the prototype code and the regulatory
frameworks it is trying to illustrate.

It is intentionally a traceability map, not legal advice and not a statement of
regulatory compliance. The project remains a transparent prototype for testing
calculation mechanics from synthetic inputs.

The companion machine-readable source manifest is
[`docs/regulatory_sources.yml`](regulatory_sources.yml). It keeps official
source URLs, section hints, linked modules, linked requirement IDs, source
status, and reuse notes without vendoring the full regulatory texts into the
package.

Use it in two directions:

- **Code to regulation:** start from a module and see which Basel, U.S. NPR, and
  EU references motivated the implementation.
- **Regulation to code:** start from a regulatory topic and see where the
  prototype implements, simplifies, or excludes it.

## Quick navigation

From code to regulation:

1. Open the module docstring.
2. Follow its `Regulatory traceability` pointer to the **Code to regulation**
   table.
3. Use the source register links below to inspect the relevant Basel, U.S. NPR,
   or EU source.

From regulation to code:

1. Start with the **Regulation to code** table.
2. Find the regulatory topic.
3. Open the listed prototype entry points and their tests.
4. Check the coverage status before treating a calculation as implemented.

## Status taxonomy

Canonical UK/PRA profile coordination:
[`docs/regulatory/profiles/pra-uk-crr-source-mapping-status.md`](../../../docs/regulatory/profiles/pra-uk-crr-source-mapping-status.md).

| Status | Meaning in `frtb-ima` |
| --- | --- |
| Implemented | Tested code produces the cited behavior for supported inputs under the default Fed NPR profile or an explicitly supported comparison slice. |
| Partial comparison profile | Policy parameters and selected metrics (for example EU/PRA PLA mechanics) are exposed with documented gaps; not a complete jurisdictional own-funds calculator. |
| `placeholder_reference` | Link-only source manifest entry without section-level UK mapping. |
| Unsupported fail-closed | Capital-producing `*_for_policy` entrypoints raise `UnsupportedRegulatoryFeatureError` until UK mapping and fixtures exist. |
| Out of scope | Deliberately deferred beyond the package boundary (SBM/DRC/RRAO stack, approvals, consolidation). |

## Source register

| Source family | Primary references used by this prototype | Status in this project |
| --- | --- | --- |
| Basel FRTB IMA | Basel Committee, *Minimum capital requirements for market risk*, January 2019, integrated into the Basel Framework as MAR30-MAR33 and MAR99. Key chapters: MAR30 general IMA provisions, MAR31 model requirements and RFET, MAR32 backtesting and P&L attribution, MAR33 ES/IMA capital calculation and NMRFs. | Baseline conceptual framework. |
| U.S. NPR 2.0 | Federal Register, 91 FR 14952, March 27, 2026, *Regulatory Capital Rule: Category I and II Banking Organizations, Banking Organizations With Significant Trading Activity, and Optional Adoption for Other Banking Organizations*. | Proposed-rule material only. Outputs are not final U.S. regulatory capital. |
| EU CRR / CRR3 | Regulation (EU) No 575/2013 as amended by CRR2 and CRR3, especially Articles 325ba, 325bb, 325bc, 325bd, 325be, 325bf, 325bg, and 325bk. | EU comparison framework. The code does not implement a full CRR own-funds requirement. |
| EU RTS / EBA | Commission Delegated Regulation (EU) 2022/2059 for backtesting and P&L attribution technical details; Commission Delegated Regulation (EU) 2022/2060 for risk-factor modellability; EBA final draft RTS updates under CRR3. | Used to identify documentation gaps and EU-specific refinements, not fully implemented. |
| UK CRR / PRA | UK CRR and PRA rulebook market-risk implementation. | `placeholder_reference` in the source manifest; `unsupported_fail_closed` for IMA capital runtime. PRA-specific deltas are not source-mapped or formally calibrated yet. |

Use `docs/regulatory_sources.yml` for topic-level links and section hints.

## Primary-source links

- Basel Committee, *Minimum capital requirements for market risk*, January 2019:
  https://www.bis.org/bcbs/publ/d457.htm
- Basel Framework chapter MAR31, internal models approach model requirements:
  https://www.bis.org/basel_framework/chapter/MAR/31.htm
- Basel Framework chapter MAR32, backtesting and P&L attribution:
  https://www.bis.org/basel_framework/chapter/MAR/32.htm
- Basel Framework chapter MAR33, IMA capital requirements calculation:
  https://www.bis.org/basel_framework/chapter/MAR/33.htm
- U.S. NPR 2.0 / Federal Register 91 FR 14952, March 27, 2026:
  https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959
- OCC PDF copy of 91 FR 14952:
  https://www.occ.gov/news-issuances/federal-register/2026/91fr14952.pdf
- Regulation (EU) 2024/1623 (CRR3):
  https://eur-lex.europa.eu/eli/reg/2024/1623/oj/eng
- Regulation (EU) 2019/876 (CRR2):
  https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32019R0876
- Delegated Regulation (EU) 2022/2059, backtesting and P&L attribution RTS:
  https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022R2059
- Delegated Regulation (EU) 2022/2060, risk-factor modellability RTS:
  https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022R2060
- EBA final draft technical standards update under CRR3:
  https://www.eba.europa.eu/publications-and-media/press-releases/eba-publishes-final-draft-technical-standards-market-risk-part-its-roadmap-implementation-banking

## Regime switching model

Regime switching is implemented as a run-level immutable policy configuration in
`regimes.py`. Top-level workflows select a `CalculationContext`, which holds the
`RegulatoryPolicy`, `as_of_date`, and optional run metadata. Lower-level
calculation functions keep scalar APIs where possible; policy-specific wrappers
extract the policy parameters and raise explicit unsupported-feature errors when
a profile requires a method this prototype does not implement.

Fed NPR 2.0 is the default and priority profile. It remains proposed-rule
material, not final U.S. regulatory capital.

| Profile | Enum value | Status | Implemented / parameterized | Placeholder / unsupported |
| --- | --- | --- | --- | --- |
| Fed NPR 2.0 | `FED_NPR_2_0` | Default profile; most complete. | 97.5% ES with weighted interpolated tail estimation, 10/20/40/60/120 LHA weights, 50/50 IMCC blend, RFET count thresholds with optional exact business-calendar windows, stress-period selection from supplied historical risk-class loss series, Type A / Type B NMRF taxonomy, NMRF method evidence, valuation-run specifications and artifact reconciliation, Type A zero-correlation SES aggregation, Type B rho 0.36, KS-only PLA over a 250-business-day policy window, 97.5%/99.0% backtesting gates with 30/12 exception limits, Basel-style multiplier schedule. | Final U.S. rule calibration, supervisory overrides, raw market-data sourcing, formal stress-period approval governance, SBM/DRC/RRAO fallback stack, firm consolidation. |
| ECB CRR3 | `ECB_CRR3` | Partial profile with honest gaps. | Basel/FRTB ES, LHA, IMCC, backtesting, and NMRF concepts share the same prototype mechanics where terminology aligns. EU/PRA PLA computes both KS and Spearman and applies the worse joint zone. | Full EU RFET RTS details, vendor/data-pooling rules, and EU-specific own-funds assembly are explicitly unsupported. Type A / Type B labels are not treated as native EU terminology. |
| PRA UK CRR | `PRA_UK_CRR` | Partial profile with `mapped_and_cited` RFET/NMRF slice and `tests/fixtures/ima_pra` replay. | UK CRR Articles 325be and 325bk with retained DR 2022/2059/2060 PLA thresholds; BASEL_EU_NMRF capital routing (modellable factors in IMCC, NMRF statuses in SES only). | `pra_specific_calibration`, `eu_rfet_rts_detail`, and U.S. Type A / Type B taxonomy remain unsupported. |

## Code to regulation

| Module | Prototype responsibility | Basel reference | U.S. NPR 2.0 reference | EU reference | Current implementation boundary |
| --- | --- | --- | --- | --- | --- |
| `regimes.py` | Immutable run-level policy config for Fed NPR 2.0, ECB CRR3, and PRA UK CRR profiles, desk IMA eligibility status, per-parameter citation metadata, plus explicit unsupported-feature errors. | MAR31-MAR33 common IMA concepts, including MAR32 backtesting eligibility context. | Fed NPR 2.0 proposed-rule defaults, Type A / Type B NMRF modelling choices, and proposed section `__.213` eligibility gates. | CRR3 / EU RTS profile parameters where currently shared; PRA profile treated separately as UK CRR / PRA-rulebook placeholder. | Parameter and status selection only; does not make partial ECB/PRA profiles complete calculators or implement approval workflows. |
| `calendar.py` | Dependency-free business-calendar and observation-window contracts for supplied business dates, official holidays, source/version metadata, exact 12-month windows, shifted windows, and most-recent business-day windows. | MAR31 RFET observation periods and MAR32 PLA/backtesting business-day windows. | Proposed RFET, PLA, backtesting, and stress-period dated observation-window evidence. | EU RTS backtesting, PLA, and RFET observation-window concepts. | Validates caller-supplied calendars; does not source holiday calendars, vendor calendars, or supervisory shifted-period approvals. |
| `data_models.py` | Shared enums and dataclasses for risk classes, liquidity horizons, modellability status, risk factors, real-price observations with source/vendor/feed/venue/date-normalisation metadata, scenario P&L, and desk results. | MAR31 risk factors and RFET; MAR33 liquidity horizons and ES inputs. | Proposed market-risk framework risk classes, liquidity horizons, model-eligible desks, Type A/B NMRFs. | CRR Articles 325bb-325be and 325bd risk-factor/liquidity-horizon concepts. | Data containers only; no legal classification or supervisory approval workflow. |
| `_array_utils.py` | Package-local NumPy array validation, read-only string/date array construction, equal-length checks, and date conversion used by scenario, RFET, PLA, backtesting, and NMRF support modules. | Supports MAR31-MAR33 input-shape and dated-observation traceability in consuming modules. | Supports proposed RFET, PLA, backtesting, and ES input validation in consuming modules. | Supports CRR/FRTB comparison profile input validation in consuming modules. | Utility module only; regulatory calculation logic remains in the consuming modules. |
| `_mapping_utils.py` | Package-local immutable mapping helpers for audit records, run contracts, stress-period selections, and valuation-run metadata. | Supports MAR31-MAR33 audit and input-lineage immutability concepts in consuming modules. | Supports proposed market-risk governance and audit-trail metadata in consuming modules. | Supports CRR/FRTB comparison profile governance metadata in consuming modules. | Utility module only; does not define regulatory policy or calculation semantics. |
| `_observation_utils.py` | Package-local optional observation-date validation shared by PLA and backtesting diagnostics. | Supports MAR32 dated PLA and backtesting observation-window inputs. | Supports proposed 250-business-day PLA/backtesting observation-window evidence. | Supports EU RTS backtesting and PLA dated-observation concepts. | Utility module only; PLA and backtesting thresholds remain in `pla.py` and `backtesting.py`. |
| `data_contracts.py` | Validated run-level contracts for positions, risk-factor definitions, RFET evidence packages, RFET representativeness/data-pooling/new-issuance evidence, scenario cubes, desk runs, and capital run results. | MAR31-MAR33 input lineage and scenario consistency expectations. | Supports model-eligible desk inputs, RFET evidence, scenario P&L cubes, and audit traceability. | Supports CRR/FRTB comparison profiles at the data-contract layer. | Contracts and validation only; does not generate scenarios, connect to vendor systems, or make supervisory approval decisions. |
| `scenario.py` | Canonical scenario metadata and vector container. | MAR32/MAR33 rely on aligned historical observations for PLA, backtesting, and ES. | 250-business-day PLA/backtesting vectors and current/stress ES windows. | Articles 325bc, 325bf, 325bg and RTS data-alignment expectations. | Carries metadata and validates alignment; does not generate market shocks. |
| `scenario_validation.py` | Validates nested liquidity-horizon vector structure before LHA ES/IMCC use. | MAR33 liquidity-horizon ES aggregation depends on common scenario ordering and nested risk-factor sets. | Proposed LHA ES calculation for all risk factors with liquidity horizon at least as long as each bucket. | Article 325bc partial ES and Article 325bd liquidity horizons. | Checks structure and optional nesting evidence; does not validate business calendars or stress-window governance. |
| `stress_periods.py` | Selects common stress windows by risk class from supplied historical loss/severity vectors before valuation and capital runs. | MAR33 stress-period and NMRF stress-scenario concepts, including common risk-class stress periods. | Proposed-rule basis for stressed ES / SES calibration and Type A / Type B NMRF stress-period inputs. | Article 325bc partial ES and Article 325bk stress scenario risk measure comparison concepts. | Vectorized window scoring and NMRF stress-period spec bridge implemented. Results record whether the window used an observation-count proxy or caller-supplied exact 12-month business calendar. Raw market-data sourcing, trade pricing, and formal approval evidence remain upstream. |
| `lha_builder.py` | Builds all-class and per-risk-class nested LH scenario vectors from validated scenario cubes. | MAR33 nested liquidity-horizon scenario construction. | Proposed LHA ES inputs for risk factors with liquidity horizon at least as long as each cutoff. | Articles 325bc and 325bd partial ES and liquidity horizons. | Vector construction implemented; assumes risk factors already carry assigned liquidity horizons. |
| `liquidity_horizon_mapping.py` | Provides the regulatory risk-factor category to 10/20/40/60/120-day liquidity-horizon table plus short-maturity and weighted-average multi-underlying helpers. | MAR33.12 Table 2 risk-factor category liquidity horizons. | Proposed section `__.215(b)(11)` assignment of liquidity horizons, short-maturity rule, and credit/equity index weighted-average rule. | Article 325bd liquidity-horizon mapping comparison concepts. | Mapping is category-based; trade/vendor/instrument classification into those categories remains upstream. |
| `expected_shortfall.py` | Empirical expected shortfall at configurable confidence level with explicit estimator selection. | MAR33 requires 97.5% one-tailed ES for IMA ES calculation. | Proposed expected-shortfall-based measures use a 10-day base horizon and liquidity-horizon adjustment. | Article 325bc calls for daily partial ES at 97.5% one-tailed confidence. | Implements discrete ceil-tail and weighted-interpolated estimators; Fed NPR 2.0 policy uses the ADR 0004 weighted-interpolated convention. |
| `liquidity_horizon.py` | Liquidity-horizon-adjusted ES from nested scenario vectors, with component decomposition. | MAR33 liquidity-horizon adjustment using 10, 20, 40, 60, 120 day horizons. | Proposed Section V.A.8.b.i / proposed section `__.215` LHA ES mechanics. | Articles 325bc and 325bd partial ES and liquidity-horizon mapping. | Uses nested vectors; category-to-horizon lookup lives in `liquidity_horizon_mapping.py`. |
| `rfet.py` | RFET-style modellability classification from real-price observation counts and qualitative pass/fail, with optional exact 12-month or shifted business-calendar windows. | MAR31 RFET and real-price evidence for modellability. | Proposed Type A / Type B NMRF distinction and inclusion logic. | Article 325be and Delegated Regulation (EU) 2022/2060. | Scalar classification path; use `rfet_evidence.py` for audit-grade evidence assessment. |
| `rfet_evidence.py` | RFET evidence assessment with eligible/excluded observation audit trail, source/vendor/feed/venue lineage checks, vendor audit/data-pooling controls, timestamp normalisation evidence, verifiability checks, explicit representativeness methodologies, one-count-per-date/source-vendor de-duplication, official-holiday/non-business-date exclusions, calendar metadata, and policy-governed new-issuance prorating. | MAR31 RFET and real-price evidence for modellability. | Proposed real-price evidence and Type A / Type B NMRF modelling choices. | Article 325be and Delegated Regulation (EU) 2022/2060 comparison gap. | Evidence engine only; external vendor APIs, legal/vendor-contract review, and supervisor overrides remain open. |
| `nmrf_method_selection.py` | Upfront NMRF stress-method selector that converts RFET Type A/B classifications, valuation-capability flags, and optional method evidence into auditable valuation instructions. | MAR33 NMRF stress scenarios must be prudent for non-modellable risks. | Proposed SES methodology must address material nonlinearities and basis/correlation risks. | EU Article 325bk and RTS-style direct/stepwise governance concepts inform design only. | Prototype governance selector and direct-robustness diagnostic; not a supervisor approval workflow and not a pricing-model validator. |
| `nmrf_stress_spec.py` | Upstream valuation-run specifications for direct shocks, stepwise grids, full-revaluation market states, and max-loss fallback candidates. | MAR33 NMRF stress-scenario capital and liquidity horizon floor concepts. | Proposed Type A / Type B NMRF SES modelling choices and stress-scenario methodology. | Article 325bk stress scenario risk measure. | Specifies what the upstream engine must value; does not generate shocks, select stress periods, or price instruments. |
| `nmrf_valuation_run.py` | Run-level NMRF valuation handoff and reconciliation from specs to returned stress artifacts. | MAR33 NMRF stress-scenario capital requires stress artifacts before capital aggregation. | Proposed NMRF SES workflow, common stress-period identifiers, liquidity horizon floor, and max-loss fallback controls. | Article 325bk and RTS controls for stress scenario risk measure inputs. | Validates artifact completeness, method, liquidity horizon, stress-period, scenario-count, and scenario-id alignment; does not price trades or generate shocks. |
| `nmrf.py` | NMRF stress artifacts, vectorized SES extraction, Type A/B capital routing, and SES aggregation with audit decomposition. | MAR33 NMRF capital requirement using stress scenarios calibrated at least as prudently as ES. | Proposed SES treatment, including Type A in IMCC and SES, Type B in SES only, Type A zero-correlation aggregation, and Type B rho 0.36. | Article 325bk stress scenario risk measure. | Capital layer consumes upstream direct/stepwise/full-revaluation artifacts and fails hard when Type A/B artifacts are missing. Institutional pricing/revaluation remains upstream; the labelled linear helper is approximation-only. |
| `imcc.py` | Unconstrained/constrained IMCC blend, component decomposition, and reduced-set stress-scaling audit result. | MAR33 IMA capital calculation, current/stress ES, reduced-set scaling concepts. | Proposed IMCC, LHA ES across and within risk classes, and reduced/full set floor at one. | Articles 325ba, 325bb, 325bc. | Scalar and decomposition APIs implemented; consumes numeric current/stress ES values produced upstream. Reduced-set governance remains open. |
| `reduced_set.py` | Reduced risk-factor set selection and current-period variation-explained diagnostic for the indirect IMCC stress approach. | MAR33 current/stress ES reduced-set concepts. | Proposed 60-business-day, 75 percent out-of-sample R-squared coverage test for reduced-set current LHA ES. | Article 325bc subset of modellable risk factors. | Deterministic selector and diagnostic implemented for caller-supplied contribution series; source data-quality evidence remains upstream. |
| `pla.py` | Kolmogorov-Smirnov PLA comparing HPL and RTPL vectors over the policy window, plus EU/PRA Spearman rank-correlation PLA and worse-zone aggregation, with optional date-window diagnostics and supplied-calendar validation. | MAR32 PLA test requirement and MAR32.42 green/amber/red PLA thresholds. | Proposed PLA metric uses KS over HPL and RTPL over the most recent 250 business days, with proposed section `__.213` eligibility gates. | Article 325bg and Delegated Regulation (EU) 2022/2059 Articles 4-5, including Article 5(2) PLA zone thresholds. | NPR KS path implemented with cited KS thresholds; `spearman_correlation`, `SpearmanPlaResult`, and `spearman_pla_assessment` implement the EU/PRA comparison metric with cited Spearman thresholds. Calendar sourcing remains upstream. |
| `backtesting.py` | APL/HPL VaR exception counting over a rolling window, including NPR 97.5% and 99.0% trading-desk gates, optional per-observation traces, official-holiday exclusions, and supplied-calendar validation. | MAR32 backtesting requirements for IMA. | Proposed backtesting over the most recent 250 business days against 97.5% and 99.0% VaR-based measures, including missing-data exception treatment. | Article 325bf and Delegated Regulation (EU) 2022/2059. | Exception gates, dated trace output, and calendar metadata are implemented for supplied calendars; calendar sourcing remains upstream. |
| `capital.py` | Desk-level models-based capital assembly, desk eligibility handoff guard, and PLA add-on helper. | MAR33 capital calculation and multiplier concepts; MAR32 desk-level eligibility context. | Proposed models-based measure / non-default capital framework, section `__.213` backtesting and PLA eligibility gates, and PLA add-on mechanics. | Article 325ba own-funds requirement under alternative internal models. | Desk-level formula, `desk_eligibility_from_results`, eligibility-guarded policy wrapper, and PLA add-on helper implemented; excludes SBM, DRC, RRAO, fallback stack calculation, redesignation add-ons, lifecycle remediation, and firm consolidation. |
| `logging.py` | Dependency-free JSON log formatter and structured calculation-boundary log field helper. | MAR31-MAR33 model governance and traceability concepts. | Proposed market-risk governance and auditability basis. | CRR internal-model governance comparison concepts. | Runtime observability only; no metrics backend, OpenTelemetry, or external log collector dependency. |
| `_version.py` | Package code-version identity sourced from installed package metadata for audit records. | MAR31-MAR33 model governance and traceability concepts. | Proposed market-risk governance and auditability basis. | CRR internal-model governance comparison concepts. | Version identity only; does not define model approval status or release signing. |
| `audit_inputs.py` | Canonical input hashing for desk-run audit records and validation packs. | MAR31-MAR33 input lineage and model governance concepts. | Proposed market-risk governance, reproducibility, and audit-trail basis. | CRR internal-model governance comparison concepts. | Produces deterministic input digests only; no replay CLI, storage lineage system, or external attestation. |
| `input_manifest.py` | Production-style input lineage manifest with artifact source system/version, extraction timestamp, schema version, checksum, sign convention, counts, validation status, and fixture-manifest mapping. | MAR31-MAR33 input lineage, completeness, and model governance concepts. | Proposed market-risk governance, reproducibility, and audit-trail basis. | CRR internal-model governance comparison concepts. | Does not connect to enterprise data-quality platforms, object stores, or persistent storage. |
| `arrow_batch.py` | Arrow-backed tabular handoff for capital-run input-manifest artifact lineage. | MAR31-MAR33 input lineage, completeness, and model governance concepts. | Proposed market-risk governance, reproducibility, and audit-trail basis. | CRR internal-model governance comparison concepts. | Accepts tabular manifest evidence only; scenario cubes and scenario-vector kernels remain NumPy-native and upstream risk-engine outputs remain outside this adapter. |
| `audit.py` | Desk-level audit records, run audit collection, optional input-lineage summaries, NDJSON serialization, and deterministic Markdown report rendering. | MAR31-MAR33 input/output traceability concepts. | Proposed reporting, governance, and audit-trail basis. | CRR internal-model governance comparison concepts. | Serialisable post-run artifacts and prototype report only; no final regulatory disclosure template, streaming large-run writer, Parquet, or DuckDB backend. |
| `capital_run_fixture.py` | Importable loader and checksum verifier for the committed synthetic capital-run fixture used by validation packs, notebooks, tests, and replay. | MAR31-MAR33 input lineage and reproducibility concepts. | Proposed market-risk governance and audit-trail basis. | CRR internal-model governance comparison concepts. | Synthetic fixture support for `tests/fixtures/capital_run_v1` and `tests/fixtures/ima_pra`; not a proprietary input adapter or market-data sourcing layer. |
| `replay.py` | Dependency-free replay CLI that recomputes the committed fixture capital run from input artifacts and compares identity, hashes, scalar outputs, and categorical outputs against audit NDJSON. | MAR31-MAR33 model governance, reproducibility, and audit-trail concepts. | Proposed market-risk governance, reproducibility, and audit-trail basis. | CRR internal-model governance comparison concepts. | Supports the committed synthetic fixture first; no remote object storage, proprietary bank input adapters, or cryptographic signing. |
| `demo_data.py` | Synthetic risk factors, observations, scenario vectors, P&L, and VaR series for examples. | Not a regulatory method; supports demonstrations of MAR31-MAR33 concepts. | Not a regulatory method; supports NPR-style examples. | Not a regulatory method; supports CRR/FRTB examples. | Fabricated data only; not evidence, not market data, not calibration. |

## Regulation to code

| Regulatory topic | Basel anchor | U.S. NPR 2.0 anchor | EU anchor | Prototype entry points | Coverage status |
| --- | --- | --- | --- | --- | --- |
| IMA desk eligibility context | MAR30 general IMA provisions; MAR32 desk-level PLA/backtesting. | Model-eligible trading desks, model-ineligible fallback concepts, and proposed section `__.213` eligibility gates. | Article 325az permission context, plus Articles 325bf/325bg. | `DeskEligibilityStatus`, `desk_eligibility_from_results`, `models_based_capital_for_policy`, `capital.py`, `regimes.py`. | Implemented as a two-state handoff guard before models-based capital; no approval lifecycle, remediation workflow, or SBM/DRC/RRAO fallback stack calculation. |
| Regime switching / profile selection | MAR31-MAR33 common IMA concepts. | Fed NPR 2.0 proposed-rule material as the default profile. | CRR3 / EU RTS and UK CRR / PRA-rulebook partial profiles. | `regimes.py`, `CalculationContext`, policy-aware wrapper functions. | Implemented as configuration; ECB and PRA profiles carry explicit unsupported gaps. |
| Run input contracts | MAR31-MAR33 scenario alignment, RFET evidence, capital input consistency, and data-quality lineage. | Position, risk-factor, RFET evidence, scenario cube, desk-run input boundaries, and production-style input lineage manifests. | CRR/FRTB input traceability concepts. | `data_contracts.py`, `input_manifest.py`. | Implemented as validated dataclasses; workflow generation and enterprise data-quality platforms remain upstream. |
| Expected shortfall confidence level | MAR33 97.5% one-tailed ES. | Expected-shortfall-based measures for model-eligible positions. | Article 325bc 97.5% one-tailed partial ES. | `expected_shortfall.expected_shortfall`, `ESEstimator`. | Implemented with explicit estimator selection; Fed NPR 2.0 policy uses weighted interpolation while the discrete ceil estimator remains available for comparisons and backwards compatibility. |
| Base 10-day scenario vectors | MAR33 base horizon and liquidity-horizon adjustment. | Proposed 10-day base horizon for LHA ES mechanics. | Article 325bc base time horizon T = 10 days. | `scenario.py`, `expected_shortfall.py`, `liquidity_horizon.py`. | Implemented as input semantics; scenario generation is upstream. |
| Liquidity horizons | MAR33 10/20/40/60/120 day horizons and MAR33.12 Table 2 category mapping. | Proposed LHA ES formula, proposed section `__.215(b)(11)` risk-factor liquidity horizons, short-maturity rule, and multi-underlying weighted-average rule. | Articles 325bc and 325bd. | `LiquidityHorizon`, `liquidity_horizon_mapping.py`, `lha_builder.py`, `liquidity_horizon.py`, `scenario_validation.py`. | Scenario cube to nested-vector construction, LHA calculation, category-to-horizon table, short-maturity helper, and weighted-average helper implemented. Trade/vendor category assignment remains upstream. |
| Risk-factor modellability / RFET | MAR31 risk-factor eligibility test and real-price observations. | Proposed Type A / Type B NMRF modelling choices. | Article 325be and Delegated Regulation (EU) 2022/2060. | `rfet.py`, `rfet_evidence.py`, `calendar.py`, `RealPriceObservation`, `ModellabilityStatus`. | Quantitative thresholds, exact/shifted supplied-calendar windows, source/vendor/data-pooling evidence, representativeness evidence, and new-issuance policy evidence are implemented; external vendor connectivity and supervisor overrides remain open. |
| Stress-period selection | MAR33 stressed ES and NMRF common stress-period concepts. | Proposed-rule basis for stressed ES / SES calibration before valuation and capital aggregation. | Article 325bc and Article 325bk comparison concepts. | `stress_periods.py`, `calendar.py`, `NMRFStressPeriodSpec`. | Partial: selects windows from supplied historical loss/severity vectors with vectorized NumPy scoring and emits NMRF stress-period specs. Results distinguish observation-count proxy and exact supplied-calendar windows. Raw market-data sourcing, source-completeness proof, and supervisory approval governance remain upstream. |
| NMRF method selection | MAR33 NMRF stress scenarios and prudent methodology expectations. | Proposed NMRF SES methodology must address material nonlinearities, basis, and correlation risks. | Article 325bk and direct/stepwise RTS concepts as comparison material. | `nmrf_method_selection.py`, `nmrf_stress_spec.py`, `nmrf_valuation_run.py`. | Implemented as auditable prototype governance logic after RFET and before valuation, including valuation-run specifications and artifact reconciliation; not a final regulatory approval framework. |
| NMRF stress capital / SES | MAR33 NMRF stress scenarios. | Proposed SES treatment for Type A/Type B NMRFs, including Type A zero-correlation aggregation and Type B rho 0.36. | Article 325bk. | `nmrf.py`, `nmrf_method_selection.py`, `nmrf_stress_spec.py`, `nmrf_valuation_run.py`. | Implemented for valuation-run contracts, handoff reconciliation, capital-layer artifact validation, vectorized SES extraction, Type A/B routing, and aggregation. Pricing/revaluation generation is an upstream responsibility. |
| IMCC constrained/unconstrained aggregation | MAR33 IMA capital calculation. | Proposed all-risk-class and per-risk-class LHA ES inputs. | Articles 325ba and 325bb. | `imcc.py`, `liquidity_horizon.py`. | Scalar result and audit decomposition implemented. |
| Reduced-set stress scaling | MAR33 current/stress ES reduced-set concepts. | Proposed reduced/full set scaling floor at one and 75 percent variation-explained coverage test over 60 business days. | Article 325bc subset of modellable risk factors. | `imcc.scale_stress_es`, `imcc.scale_stress_es_breakdown`, `reduced_set.select_reduced_risk_factor_set`, `reduced_set.reduced_set_variation_explained`. | Scaling ratio, floor audit detail, deterministic reduced-set selection, and coverage diagnostic implemented for supplied series; source data-quality evidence remains upstream. |
| PLA | MAR32 PLA test and MAR32.42 PLA traffic-light thresholds. | Proposed KS comparison of RTPL and HPL over 250 business days, with proposed section `__.213` eligibility gates. | Article 325bg and Delegated Regulation (EU) 2022/2059 Articles 4-5, including Article 5(2) threshold treatment. | `pla.py`, `calendar.py`, `ks_statistic`, `spearman_correlation`, `SpearmanPlaResult`, `pla_assessment`, `spearman_pla_assessment`, `PlaPolicyAssessmentResult`. | NPR KS implemented with policy window, date diagnostics, and optional supplied-calendar validation; EU/PRA Spearman and worse-zone joint PLA are implemented with cited Spearman thresholds. |
| Backtesting | MAR32 backtesting. | Proposed APL/HPL backtesting over 250 business days at 97.5% and 99.0% VaR levels. | Article 325bf and Delegated Regulation (EU) 2022/2059. | `backtesting.py`, `calendar.py`. | Dual-level exception gate, optional dated trace, official-holiday exclusions, and optional supplied-calendar validation implemented. |
| Models-based capital / own funds | MAR33 capital calculation. | Proposed models-based market-risk measure, NDCR components, and PLA add-on. | Article 325ba. | `capital.py`. | Desk-level capital and PLA add-on helper implemented; firm consolidation not implemented. |
| Run observability and audit artifacts | MAR31-MAR33 governance and traceability concepts. | Proposed market-risk reporting and model governance basis. | CRR internal-model governance comparison concepts. | `logging.py`, `audit.py`, `input_manifest.py`, `replay.py`, result-object `as_dict()` methods, `make audit`, `make replay-fixture`. | JSON runtime logs, NDJSON desk audit records, compact input-lineage summaries, deterministic Markdown report rendering, and fixture replay are implemented; streaming large-run writers, external telemetry, Parquet/DuckDB analytics, remote input bundles, and final disclosure templates remain orchestration-layer future scope. |

## Module docstring convention

Every calculation module should include a short `Regulatory traceability` block
that names:

1. the Basel topic,
2. the U.S. NPR 2.0 topic,
3. the EU/CRR topic,
4. the relevant row in this document.

Do not paste long regulatory text into module docstrings. Keep module docstrings
short and route reviewers here for the full cross-reference.

## Maintenance rules

When adding or changing a calculation module:

1. Update the **Code to regulation** table.
2. Update the **Regulation to code** table if the change implements a new topic.
3. Add or update module docstring traceability.
4. If the implementation deliberately diverges from Basel, U.S. NPR, or EU CRR,
   document the divergence in `docs/REGULATORY_ASSUMPTIONS.md`.
5. Keep proposed U.S. NPR content labelled as proposed-rule material.

## Known cross-jurisdiction differences and gaps

- The U.S. NPR 2.0 proposal includes Type A and Type B NMRF terminology used by
  this prototype. Basel and EU materials use NMRF/stress-scenario concepts but
  do not map one-to-one to this prototype's Type A / Type B labels.
- Stress-period selection assumes historical risk-class loss/severity vectors
  are supplied before valuation. It does not source raw market data, prove data
  completeness, or approve calibration governance.
- The NMRF selector assumes RFET classifications are available before valuation
  and emits valuation instructions/specifications. The valuation-run handoff
  reconciles returned artifacts to those specifications before SES capital, but
  does not perform live pricing; upstream engines must produce the required
  stress artifacts.
- EU PLA RTS uses both Spearman correlation and Kolmogorov-Smirnov metrics. This
  prototype implements an EU/PRA comparison path using both metrics and the
  worse joint zone, while full EU own-funds assembly remains out of scope.
- EU RFET RTS contains richer criteria for modellability, observation periods,
  data-pooling, and third-party vendor reliance. This prototype implements
  source/vendor lineage, data-pooling metadata, representativeness evidence, and
  date-normalisation checks as package-level evidence contracts, but does not
  connect to vendor systems or perform legal/vendor-contract review.
- PRA-specific market-risk source mapping remains partial. `PRA_UK_CRR` is a
  separate profile so future UK/PRA deltas do not silently fall back to ECB
  behavior where the rules diverge. RFET/NMRF capital for supported synthetic
  inputs is replay-tested under `tests/fixtures/ima_pra`; remaining gaps are
  listed as explicit unsupported features on the policy object.
- The prototype does not implement SBM, default risk charge, residual risk
  add-on, fallback capital, redesignation add-ons, legal-entity consolidation,
  formal model approval, or supervisor override processes.
