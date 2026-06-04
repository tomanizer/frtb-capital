# CVA regulation summary

This note summarises the regulation that `frtb-cva` implements or tracks. It is
an implementation guide, not legal advice and not evidence that outputs are
final regulatory capital. For code-level traceability, see
[`REGULATORY_TRACEABILITY.md`](REGULATORY_TRACEABILITY.md). For source metadata,
see [`regulatory_sources.yml`](regulatory_sources.yml).

## What CVA risk capital is for

Credit valuation adjustment (CVA) risk capital covers mark-to-market losses that
can arise when regulatory CVA changes because a derivative or SFT counterparty's
credit spread, or market risk factors that drive exposure, move adversely.
Basel MAR50 defines regulatory CVA separately from accounting CVA, excludes own
default effects, and requires CVA risk-weighted assets to equal CVA capital
requirements multiplied by 12.5.

The capital charge sits beside counterparty credit risk default capital. CCR
capital addresses default exposure; CVA risk capital addresses deterioration in
the value of the counterparty-facing portfolio before default.

## Basel MAR50 core requirements

Basel MAR50 is the package's current capital-producing profile. The main
requirements are:

- **Scope and methods:** covered derivative and material fair-valued SFT
  transactions form a standalone CVA portfolio with eligible CVA hedges
  (MAR50.1-MAR50.7). BA-CVA is the default method; SA-CVA requires supervisory
  approval. Approved SA-CVA banks may carve out netting sets to BA-CVA
  (MAR50.8). A materiality-threshold alternative may use CCR capital instead of
  BA-CVA or SA-CVA, but hedge recognition is not allowed (MAR50.9).
- **Hedges and internal transfers:** eligible hedge criteria differ by method.
  BA-CVA recognises counterparty credit-spread hedges under MAR50.17-MAR50.26.
  SA-CVA recognises broader CVA hedges under MAR50.37-MAR50.39. Internal CVA
  hedges must satisfy the internal-transfer treatment in MAR50.11.
- **Reduced BA-CVA:** calculates counterparty stand-alone CVA capital from
  sector/credit-quality risk weights, effective maturity, EAD, discount factor,
  and alpha, then aggregates systematic and idiosyncratic components using the
  supervisory correlation parameter (MAR50.14-MAR50.16).
- **Full BA-CVA:** starts from reduced BA-CVA and recognises eligible
  single-name and index credit hedges, subject to supervisory floors and hedge
  eligibility constraints (MAR50.17-MAR50.26).
- **SA-CVA:** uses sensitivities of aggregate regulatory CVA and eligible hedge
  values to prescribed risk factors (MAR50.42-MAR50.53). Risk classes are GIRR,
  FX, counterparty credit spread, reference credit spread, equity, and
  commodity. Delta and vega requirements are defined in MAR50.54-MAR50.77; MAR50
  defines no counterparty-credit-spread vega path.
- **Calibration:** BCBS d507 revised the Basel CVA framework in July 2020,
  including `m_CVA = 1.0` for SA-CVA and `D_BA-CVA = 0.65` for BA-CVA.

## Jurisdiction variants

| Variant | Status | What differs or needs mapping |
| --- | --- | --- |
| Basel MAR50 / BCBS d507 | Implemented under audit as `BASEL_MAR50_2020`. | This is the reference profile for reduced BA-CVA, full BA-CVA, SA-CVA, mixed carve-out, qualified-index routing, attribution, impact, and audit evidence. |
| U.S. NPR 2.0 / 91 FR 14952 section V.B | Comparison profile only, fail closed as `US_NPR20_VB`. | The March 27, 2026 NPR proposes CVA risk requirements for covered U.S. banking organizations, including covered positions, CVA hedges, internal CVA risk transfers, and a standardized measure for CVA risk. It is proposed-rule material and needs a section-by-section profile crosswalk, fixtures, and final-rule review before any capital-producing path. |
| EU CRR3 / Regulation (EU) 2024/1623 | Comparison profile only, fail closed as `EU_CRR3_CVA`. | EU implementation is through amended CRR provisions, especially Articles 382-386 and related EBA technical standards. ECB-supervised firms apply the EU CRR framework; the package does not treat ECB supervision as a separate CVA formula. EU exclusions, SFT scope, eligible hedges, and approach permissions need their own article-level mapping. |
| UK PRA Basel 3.1 / PS1/26 and CP16/22 | Comparison profile only, fail closed as `UK_PRA_CVA`. | PRA PS1/26 finalises Basel 3.1 rules effective from 1 January 2027. The PRA framework introduces AA-CVA, BA-CVA, and SA-CVA and removes internal models for CVA capital. UK rulebook references, AA-CVA, permissions, reporting, and disclosure differences are not implemented. |

## How `frtb-cva` implements the regulation

The package is a capital layer. Upstream systems provide counterparties, netting
sets, EAD/effective maturity/discount inputs, eligible-hedge evidence, and
SA-CVA sensitivities. `frtb-cva` validates those inputs and applies cited capital
mechanics; it does not simulate exposures, calculate accounting CVA, source
market data, price trades, or obtain supervisory approvals.

Implemented Basel paths:

- `BA_CVA_REDUCED`: MAR50.14-MAR50.16 stand-alone and portfolio aggregation with
  Table 1 risk weights, alpha, rho, discount factor policy, and `D_BA-CVA`.
- `BA_CVA_FULL`: MAR50.17-MAR50.26 hedge recognition, including eligible
  single-name and index credit hedges, beta floor, and rejection records.
- `SA_CVA`: MAR50.42-MAR50.77 sensitivity-based capital for supported delta and
  vega paths across GIRR, FX, RCS, equity, commodity, and CCS delta.
- `MIXED_CARVE_OUT`: MAR50.8 SA-CVA with BA-CVA netting-set carve-outs.
- Qualified-index routing under MAR50.50 where required index metadata is
  supplied.
- Audit, replay, attribution, impact, CRIF/vendor adapters, and Arrow batch
  handoff helpers that do not change capital totals.

## Known gaps

- `US_NPR20_VB`, `EU_CRR3_CVA`, and `UK_PRA_CVA` fail closed until comparison
  profiles have paragraph/article-level mappings and fixtures.
- MAR50.9 materiality-threshold alternative is unsupported because it requires
  CCR capital inputs and orchestration outside this package.
- Counterparty-credit-spread vega is a regulatory absence under Basel MAR50 and
  fails explicitly.
- SA-CVA approval, model governance, monthly regulatory CVA model operation,
  stress testing, reporting templates, and disclosure production are outside the
  package.
- Exposure simulation, IMM permission evidence, accounting CVA model adjustment,
  and live hedge execution remain upstream responsibilities.

## Primary sources

- Basel Framework MAR50: <https://www.bis.org/basel_framework/chapter/MAR/50.htm>
- BCBS d507, July 2020 targeted CVA revisions:
  <https://www.bis.org/bcbs/publ/d507.pdf>
- U.S. NPR 2.0, 91 FR 14952:
  <https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959>
- Regulation (EU) 2024/1623:
  <https://eur-lex.europa.eu/eli/reg/2024/1623/oj/eng>
- PRA PS1/26 final Basel 3.1 rules:
  <https://www.bankofengland.co.uk/prudential-regulation/publication/2026/january/implementation-of-the-basel-3-1-final-rules-policy-statement>
- PRA CP16/22 CVA chapter:
  <https://www.bankofengland.co.uk/prudential-regulation/publication/2022/november/implementation-of-the-basel-3-1-standards/credit-valuation-adjustment>
