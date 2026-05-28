# FRTB DRC Requirements Specification

**Version:** 1.0  
**Date:** 2026-05-28  
**Status:** Implementation Baseline  
**Traceability:** Maps to GitHub issues #25–#32 and Basel / NPR paragraphs.

## Purpose

This machine-readable-style specification provides the detailed, testable requirements for the `frtb-drc` implementation. It is the single source of truth for acceptance criteria. Every requirement has an ID, regulatory citation, implementation target (module), and verification method.

Format borrows from frtb-ima `docs/requirements/NPR_2_0_MARKET_RISK.yml` style (YAML registry planned for v1.1).

## R-DRC-001: Package Bootstrap & Governance

- **ID:** R-DRC-001
- **Title:** frtb-drc package skeleton and suite integration
- **Regulatory:** N/A (engineering)
- **Target Issue:** #32
- **Modules:** pyproject.toml, Makefile, src/frtb_drc/__init__.py
- **Acceptance:**
  - `uv run python -c "import frtb_drc; print(frtb_drc.__version__)"` succeeds after workspace sync.
  - `make check` (workspace) includes frtb-drc tests/lint/typecheck.
  - Independent package version in its pyproject.toml.
  - No runtime deps beyond numpy>=1.26,<2.5.
- **Verification:** CI + manual `uv sync && uv run pytest packages/frtb-drc`

## R-DRC-010: Core Data Models (Issue #25)

- **ID:** R-DRC-010
- **Title:** Enums and frozen dataclasses in data_models.py
- **Regulatory:** Basel MAR22.3–22.7 (definitions of JTD, long/short, seniority, bucket)
- **Target Issue:** #25
- **Modules:** src/frtb_drc/data_models.py
- **Acceptance:**
  - `RiskClassDRC` enum: NONSEC, SEC_CTP, SEC_NCTP (StrEnum or IntEnum matching reference).
  - `Seniority` enum: COVERED=1, SENIOR=2, NON_SENIOR=3, EQUITY=4.
  - `CreditQuality` enum or StrEnum supporting: "IG","SG","SSG" (FRB), "1"–"7", "UNRATED", "DEFAULTED" (BCBS/CRR).
  - `FRTBBucket` or bucket constants: NON_US_SOVEREIGNS, PSE_GSE_DEBT, CORPORATES, DEFAULTED, and full BCBS_SEC_NCTP lists.
  - `Position` frozen dataclass: issuer_id, bucket, seniority, credit_quality, long_jtd, short_jtd, notional (optional), maturity_days (optional), covered_bond_flag.
  - `JTDExposure` or similar for post-netting.
  - All dataclasses support `.as_dict()` for audit serialisation.
  - Input validation raises ValueError on empty/NaN/invalid combinations at construction or helper boundaries.
- **Verification:** tests/test_data_models.py — roundtrip, validation errors, frozen immutability.

## R-DRC-011: Reference Data Loader & Risk Weights (Issue #25)

- **ID:** R-DRC-011
- **Title:** Risk weight tables, LGD, bucket mappings, jurisdiction overrides
- **Regulatory:** Basel MAR22.15–22.20 (non-sec RW), MAR22.41 (sec), NPR 2.0 Appendix (FRB buckets + IG/SG/SSG RW), CRR3 Annex.
- **Target Issue:** #25
- **Modules:** src/frtb_drc/reference_data.py (or data_models + reference)
- **Acceptance:**
  - `get_risk_weight(bucket: str, credit_quality: str = "", rules_version: RulesVersion) -> float` exactly matching reference drc_common.get_risk_weight (ported, pure, no pandas).
  - Tables:
    - BCBS_DRC_JS_RW / CRR2_DRC_JS_RW (rating -> RW)
    - FRB_DRC_JS_RW with (bucket, IG/SG/SSG) tuples for NON_US_SOVEREIGNS (0.005/0.20/0.50), PSE_GSE_DEBT (0.02/0.12/0.50), CORPORATES same, DEFAULTED 1.00.
  - LGD defaults: 0.75 non-senior / equity, 0.25 senior/covered? (confirm vs reg; document citation).
  - `DRC_NS_BUCKETS` and `SEC_*_BUCKETS` per RulesVersion (CRR2/BCBS/FRB/PRA).
  - Loader: `load_reference_data(jurisdiction: str | None = None, overrides: dict | None = None)` returning immutable mapping or frozen dataclass. Supports YAML/JSON seed files (minimal, one example override file committed).
  - RulesVersion enum (reuse or copy from frtb-ima/sbm style; define locally until frtb-common).
- **Verification:** tests/test_reference_data.py — exact match to known values from drc.zip for all 4 regimes + 3 FRB bucket/quality combos; override test.

## R-DRC-020: JTD Gross & Netting (Issue #26)

- **ID:** R-DRC-020
- **Title:** Gross JTD, seniority netting, long/short offset per issuer
- **Regulatory:** Basel MAR22.8–22.14 (net JTD by obligor, seniority, long/short hedge benefit)
- **Target Issue:** #26
- **Modules:** src/frtb_drc/jtd.py
- **Acceptance:**
  - `compute_gross_jtd(position: Position, lgd: float | None = None) -> float` (sign: positive loss exposure).
  - `net_by_seniority_and_direction(exposures: list[Position]) -> dict[Seniority, dict[str, float]]` (L/S per seniority).
  - Seniority netting rules: no cross-seniority netting within issuer (per MAR22.11–12).
  - Output includes audit columns: gross_long, gross_short, net_long, net_short, net_jtd, rw, lgd_applied.
- **Verification:** Basel example reproduction + reference vector comparison (tolerance 1e-12).

## R-DRC-030: Bucket DRC Aggregation (Issue #27)

- **ID:** R-DRC-030
- **Title:** Per-bucket capital charge with hedging benefit and correlations
- **Regulatory:** Basel MAR22.21–22.39 (non-sec DRC formula: max(0, net_long - 0.5*net_short) * RW etc., bucket correlations 0/0.5/1.0? per reg)
- **Target Issue:** #27
- **Modules:** src/frtb_drc/aggregation.py, src/frtb_drc/capital.py
- **Acceptance:**
  - `compute_bucket_drc(netted: dict, rw_table: dict) -> BucketDRCResult`
  - `BucketDRCResult` frozen: bucket, net_long, net_short, rw_net_long, rw_net_short, hedging_benefit, bucket_capital, marginals (dict).
  - Full non-sec DRC = sum over buckets with inter-bucket correlations (table per reg).
  - CTP and non-CTP: stub functions raising UnsupportedRegulatoryFeatureError for now (full in later phase).
- **Verification:** Hand-calculated Basel examples + synthetic 3-bucket case.

## R-DRC-040: CRIF Mapping & Input Layer (Issue #28)

- **ID:** R-DRC-040
- **Title:** CRIF column rename, Position construction from CRIF rows, data contracts
- **Regulatory:** ISDA CRIF v2.0+ DRC fields (RiskType=DRC, Qualifier=Issuer, Label2=Seniority, CreditQuality, etc.)
- **Target Issue:** #28
- **Modules:** src/frtb_drc/crif.py, src/frtb_drc/data_contracts.py
- **Acceptance:**
  - `get_rename_cols(risk_class: RiskClassDRC) -> dict[str, str]` matching reference drc_crif_mapping exactly (QUALIFIER -> issuer_id, etc.).
  - `positions_from_crif(df: pd.DataFrame | list[dict])` — but wait, no pandas in core; accept list[dict] or numpy structured; optional pandas adapter behind flag or separate (ADR note: keep core pandas-free).
  - Strict validation on required columns, value ranges.
  - Synthetic position factory for tests (mirrors frtb-ima/demo_data.py).
- **Verification:** Roundtrip CRIF-like dicts to Position list and back; bad data raises.

**Note on pandas:** Suite policy forbids pandas as runtime dep without ADR. Core path uses list[dict] + numpy. Test helpers may use pandas if optional-dep.

## R-DRC-050: Audit, Logging, Results (Issue #29)

- **ID:** R-DRC-050
- **Title:** Frozen result objects, audit records, structured logging
- **Regulatory:** SR 11-7 auditability, Basel MAR99 (model validation evidence)
- **Target Issue:** #29
- **Modules:** src/frtb_drc/audit.py, src/frtb_drc/logging.py, src/frtb_drc/capital.py
- **Acceptance:**
  - `DRCResult( desk: str, total_drc: float, by_risk_class: dict, by_bucket: list[BucketDRCResult], ... )` frozen with `as_dict()` and `as_audit_record()`.
  - Audit columns match style: issuer, seniority, bucket, rw, jtd_net_long, jtd_net_short, capital_contrib, marginal, euler (future), based_on.
  - NDJSON + Markdown report renderer (copy/adapt frtb-ima/scripts/render_audit_report.py pattern).
  - Structured logging at boundaries (INFO for run start, DEBUG for intermediate vectors).
- **Verification:** tests/test_audit.py, render of synthetic run matches golden.

## R-DRC-060: Tests & Numerical Fidelity (Issue #30)

- **ID:** R-DRC-060
- **Title:** Deterministic unit + integration tests against Basel examples + reference vectors
- **Regulatory:** All cited above
- **Target Issue:** #30
- **Modules:** tests/test_*.py, tests/fixtures/
- **Acceptance:**
  - 100% of implemented requirements have passing tests.
  - Basel MAR22 numerical examples (e.g. single issuer long/short, bucket aggregation) reproduced to 1e-10.
  - Ported reference vectors (from drc.zip logic) match exactly.
  - Edge: zero exposure, all defaulted, mixed seniority, FRB vs CRR2 regime switch, invalid credit quality.
  - Coverage >= 85%.
  - No non-deterministic tests (no unseeded random).
- **Verification:** `pytest packages/frtb-drc -q --cov --cov-fail-under=85`

## R-DRC-070: Documentation & Traceability (Issue #31)

- **ID:** R-DRC-070
- **Title:** README, REGULATORY_TRACEABILITY, model docs, requirement registry
- **Regulatory:** N/A
- **Target Issue:** #31
- **Modules:** README.md, docs/REGULATORY_TRACEABILITY.md, docs/regulatory_sources.yml, docs/model_documentation/
- **Acceptance:**
  - README matches frtb-ima structure and tone exactly (prototype disclaimer, layout table, install, examples).
  - REGULATORY_TRACEABILITY.md has Code-to-Regulation and Regulation-to-Code tables for every MAR22 paragraph implemented.
  - Every threshold cites exact paragraph (no "working assumption").
  - Initial model documentation pack scaffold (intended use, conceptual soundness, limitations).
- **Verification:** Manual review + link check.

## R-DRC-080: End-to-End Integration (Issue #32)

- **ID:** R-DRC-080
- **Title:** Workspace integration, draft PRs, release readiness
- **Target Issue:** #32
- **Acceptance:**
  - All 8 issues have merged PRs.
  - `uv run pytest packages/frtb-drc` clean from root.
  - Example run_demo.py produces plausible non-zero DRC for synthetic credit book.
  - CHANGELOG.md entry per package.
  - No import violations (future importlinter will enforce no frtb-ima sibling import).
- **Verification:** Full `make check`, PR review checklist per CLAUDE.md.

## Open Items / TBD (for later ADRs)

- Exact LGD table (senior vs non-senior) — confirm vs NPR 2.0 text vs Basel MAR22.18.
- CTP tranche thickness scaling (gt_DRC_SEC helper in reference).
- Inter-bucket correlation matrix exact values per regime.
- frtb-common shared calendar / sign convention once it exists.

---

**End of Specification v1.0.** Implementation must not deviate without updated spec + ADR.
