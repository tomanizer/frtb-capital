# FRTB Credit Valuation Adjustment (CVA) Risk Detailed Requirements Specification

**For frtb-in-a-box Python Package (frtb-capital GitHub Repo)**  

**Version**: 1.0 (Draft for PRD)  
**Author**: Grok (with deep research from Harper, Benjamin, Lucas)  
**Date**: 28 May 2026  
**Purpose**: Blueprint for `packages/frtb-cva` – standalone CVA capital charge. Ready for PRD → coding-agent issues. Matches `frtb-ima` + `frtb-drc` style exactly.

## Key Research Summary & Official Sources

- **Basel Core**: BCBS MAR50. Standalone BA-CVA or SA-CVA. https://www.bis.org/basel_framework/chapter/MAR/50.htm
- **US NPR 2.0 (primary)**: Federal Register 2026-05959 – BA-CVA default; client-facing cleared derivatives exempt.
- **PRA**: PS17/23 + PS9/24 – BA-CVA/SA-CVA + AA-CVA fallback, pension-fund relief.
- **ECB/CRR3**: CRR3 (EU) 2024/1623 + EBA RTS.

## Detailed Calculation Requirements

### BA-CVA (Basic Approach)

Primary approach under US NPR 2.0 for most institutions.

Formula:

K_BA-CVA = Σ_c ( RW_c × EAD_c × DF_c × MAT_c ) × (1 - H_full)

Where:
- RW_c : supervisory risk weight for counterparty c (based on rating/sector)
- EAD_c : regulatory exposure at default (SA-CCR or IMM)
- DF_c : discount factor for maturity
- MAT_c : effective maturity
- H_full : hedging benefit for full hedge (0 or 0.5 depending on hedge eligibility)

Variants: Reduced BA-CVA (no hedges) and Full BA-CVA (with eligible CVA hedges).

### SA-CVA (Standardized Approach)

More risk-sensitive. Requires calculation of sensitivities to:
- Credit spread curves (delta)
- Market factors (vega for options on credit)

Aggregation follows a SBM-style approach with specific CVA risk weights, correlations between counterparties and market factors, and capital charge for CVA risk.

K_SA-CVA = sqrt( Σ_b K_b^2 + 2 Σ_{b<c} ho_{b,c} K_b K_c )

With buckets for credit quality, sector, and region.

## Data Model & Module Breakdown (8 GitHub-issue ready – identical structure to DRC)

The implementation will be broken into 8 focused issues mirroring the successful DRC pattern:

1. `data_models.py` – Frozen dataclasses: `CounterpartyCVA`, `NettingSet`, `CVAPosition`, `CVAHedge`, enums for `CVAApproach` (BA_CVA, SA_CVA), `CVARiskClass`, `CVAQuality`. All with `.as_dict()` for audit.
2. `ba_cva.py` – Pure functions for BA-CVA calculation, hedging benefit, regulatory weight lookup.
3. `sa_cva.py` – Sensitivity-based SA-CVA (delta/vega), bucket aggregation, SBM-style formula.
4. `jurisdiction.py` – `RegulatoryCVAPolicy` + adapter for US_NPR (client clearing exemption), PRA (pension relief, AA-CVA fallback), ECB/CRR3.
5. `crif_cva.py` + `data_contracts.py` – CRIF mapping for CVA inputs (EAD, MTM, spreads, hedges). Input validation.
6. `capital.py` + `audit.py` – `CVACapitalResult`, `CVAAuditRecord` frozen dataclasses, structured logging, NDJSON/Markdown reports.
7. `demo_data.py` + examples – Synthetic CVA book generator (counterparties, netting sets, hedges).
8. Tests, README, REGULATORY_TRACEABILITY.md, integration with frtb-orchestration.

## Regulatory Traceability & Citations (US NPR 2.0 Primary)

- US NPR 2.0 §__.220 – CVA risk charge (BA-CVA as default)
- Basel MAR50.1 – 50.30 (BA-CVA and SA-CVA)
- PRA PS17/23 §2.3 – BA-CVA application
- CRR3 Article 381a et seq.

Every numerical threshold and exemption must cite the exact paragraph.

## Non-Functional Requirements (Exact match to frtb-drc / frtb-ima)

- Python 3.11+, numpy only (no pandas/scipy without ADR)
- Frozen dataclasses for all results
- Pure functions for calculations
- Explicit ValueError/TypeError at public boundaries
- Deterministic tests only (synthetic data)
- Full audit decomposition (per-counterparty, per-hedge, marginal capital)
- 85%+ test coverage
- `make check` clean

## Edge Cases & Unsupported Features

- Client-facing cleared derivatives (US NPR exemption)
- Pension scheme arrangements (PRA relief)
- AA-CVA (Advanced Approach) – explicitly UnsupportedRegulatoryFeatureError
- Wrong-way risk detailed treatment

## Acceptance Criteria

- All 8 planned issues closed with passing tests against regulatory examples.
- `uv run python -c "import frtb_cva; print(frtb_cva.__version__)"` works after `uv sync`.
- BA-CVA and SA-CVA example calculations match published regulatory worked examples within 1e-10.
- Full audit records produced for every run.

---

**End of Requirements Specification v1.0**