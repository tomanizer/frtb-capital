# FRTB Default Risk Charge (DRC) — Product Requirements Document (PRD)

**Version:** 1.0  
**Date:** 2026-05-28  
**Status:** Draft for Implementation  
**Owner:** FRTB Capital Suite Team  
**Related Issues:** #25 (Core Data Models), #26–#32 (chained implementation)

## 1. Executive Summary

This PRD defines the scope, regulatory basis, data model, functional requirements, and acceptance criteria for the `frtb-drc` package — the Default Risk Charge (DRC) capital component of the frtb-capital suite.

DRC is the FRTB capital charge for jump-to-default (JTD) risk on credit exposures (non-securitisation, securitisation CTP, and non-CTP). It is architecturally separate from IMA (scenario ES), SA (sensitivities), and CVA (counterparty credit).

The package will:
- Consume issuer-level JTD exposures (long/short, by seniority, rating/credit quality, bucket).
- Apply regulatory risk weights, LGD, seniority netting, and bucket-level aggregation.
- Produce audit-grade capital results with full decomposition for SR 11-7 / PRA SS 1/23 validation.
- Support U.S. NPR 2.0 / FRB, Basel, CRR3/PRA, and EU regimes via policy configuration.
- Maintain zero runtime dependencies beyond numpy (matching frtb-ima).

**Out of scope (per ADR 0003):** firm-level aggregation, SA/IMA floors, redesignation, CVA, raw market data sourcing, pricing, regulatory submission packaging.

## 2. Regulatory Basis (Exact Citations)

- **Basel Framework:** MAR22 (Default risk capital requirement), MAR22.1–MAR22.39 (non-securitisation), MAR22.40–MAR22.59 (securitisation), MAR22.60–MAR22.72 (CTP).
- **U.S. NPR 2.0:** Federal Register Vol. 91, No. 59 (27 Mar 2026), sections __.212 (DRC), __.213 (backtesting/PLA cross-references), Appendix B (risk weights, buckets for FRB).
- **EU CRR3:** Articles 325ba–325bk (DRC under FRTB SA), Commission Delegated Regulations.
- **UK PRA:** CRR rules and SS 1/23 market risk.

All numerical thresholds, risk weights, and netting rules cite the above. No "working assumptions" without explicit citation.

## 3. Scope and Phasing (Issues #25–#32)

See linked GitHub issues for detailed acceptance criteria. High-level:

- **#25 Core Data Models + Reference Data Loader** (this issue): Enums (CreditQuality, Seniority, RiskClassDRC, FRTBBucket), frozen Position / JTDExposure dataclasses, reference_data.py with RW tables (BCBS/CRR2/FRB/PRA), LGD defaults, bucket mappings, get_risk_weight(), YAML/JSON loader for jurisdiction overrides.
- **#26 JTD Calculation + Seniority Netting:** Gross JTD, maturity scaling (if applicable), per-issuer per-seniority long/short netting per MAR22.8–22.14.
- **#27 Bucket Aggregation + DRC Formula:** Per-bucket capital (long/short hedge benefit, correlations), full DRC non-sec formula, CTP/NCTP stubs.
- **#28 CRIF Mapping + Input Contracts:** CRIF column mapping (matching reference drc_crif_mapping), DataContract validation, synthetic + CSV loaders.
- **#29 Capital Assembly + Audit/Logging:** DRCResult, DeskDRCResult frozen dataclasses, audit columns, JSON logging, integration with frtb-orchestration handoff.
- **#30 Tests + Basel Vectors:** Unit tests vs Basel MAR22 examples, reference implementation vectors from drc.zip, edge cases, invalid input validation.
- **#31 Documentation + Traceability:** README, REGULATORY_TRACEABILITY.md, model documentation scaffold, requirement registry entries.
- **#32 Integration + Release:** Workspace membership, CI, draft PRs per issue, release readiness.

## 4. Data Model Requirements (Detailed in #25)

See `src/frtb_drc/data_models.py` and `reference_data.py`.

Key entities (must be frozen dataclasses or enums, pure, no Pydantic per suite standard):

- `RiskClassDRC`: NONSEC, SEC_CTP, SEC_NCTP
- `Seniority`: COVERED, SENIOR, NON_SENIOR, EQUITY (maps to Zinc/ Axiom codes in reference)
- `CreditQuality`: IG / SG / SSG (FRB/NPR), or numeric CQS 1-7 / UNRATED / DEFAULTED (BCBS/CRR)
- `FRTBBucket`: NON_US_SOVEREIGNS, PSE_GSE_DEBT, CORPORATES, ... plus sec buckets
- `Position` / `JTDInput`: issuer, bucket, seniority, credit_quality, long_amount, short_amount, notional or JTD gross, maturity, etc.
- Reference tables: risk_weight tables per RulesVersion (FRB special 2-tuple keys), LGD (0.75 non-senior, 0.25? senior? per reg), default LGD by seniority.

Support jurisdiction overrides via policy or config dict/JSON (e.g. different RW for PRA vs FED).

## 5. Functional Requirements

- Pure functions only for calculations (no classes with mutable state in calc path).
- Vectorised where possible (numpy).
- Explicit ValueError / TypeError at all public boundaries.
- Sign convention: positive = loss / exposure at risk.
- Full breakdown for audit: per-issuer, per-seniority, per-bucket marginals, hedging benefit.
- Deterministic; no random; fixed seeds only where explicitly documented for tests.

## 6. Non-Functional / Engineering Requirements

- Match frtb-ima exactly: dataclasses+enums in data_models.py, functional helpers, audit/logging columns, minimal deps (numpy only), same Makefile targets, same test layout.
- Package version independent (0.1.0 initial).
- 85%+ coverage target.
- `make check` clean (lint, typecheck, test).
- No sibling imports; shared abstractions to go in future frtb-common (for now duplicate minimal or import from frtb-ima only via explicit re-export if needed — prefer copy for boundary clarity).
- Every regulatory threshold has precise citation in docstring or REGULATORY_TRACEABILITY.md.

## 7. Acceptance Criteria (Cross-Cutting)

- All issues #25–#32 closed with tests passing.
- Synthetic data only.
- Basel MAR22.10–22.14 example calculations reproduced exactly in tests.
- Reference vectors from drc.zip (ported logic) match within 1e-10.
- Draft PR opened for each issue; all merged to main before declaring complete.
- `frtb-drc` importable from workspace root after `uv sync`.
- No new runtime dependencies (ADR required for any addition).

## 8. Risks & Mitigations

- Regulatory interpretation risk: mitigated by explicit citations + future independent validation.
- Cross-package drift: enforced by CLAUDE.md review checklist and import linter (future).
- Numerical divergence from production: reference impl + Basel examples as golden tests.

## 9. References

- Basel Framework MAR22 (Default risk capital requirement)
- U.S. NPR 2.0 proposed rule text (91 FR 14952)
- Reference reconstruction: `drc.zip` (non-production video-derived constants and CRIF mapping)
- Suite ADR 0003 (SA/DRC/CVA scope)
- frtb-ima CLAUDE.md / AGENTS.md (style contract)

---

**Approval:** Implementation proceeds issue-by-issue with draft PRs. Material changes require ADR per CONTRIBUTING.md.
