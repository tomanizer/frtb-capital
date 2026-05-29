"""Synthetic non-securitisation DRC portfolio for notebooks and integration demos.

Forty positions across all four US NPR 2.0 non-securitisation buckets. The
portfolio is designed to exercise every material mechanic in the non-sec DRC
pipeline:

  - Gross JTD: all seven seniority/LGD tiers, including NOT_RECOVERY_LINKED
    (zero gross JTD) and EQUITY (LGD = 100 %).
  - P&L adjustment branch: positions with non-zero cumulative_pnl, including a
    case where the P&L is large enough to floor the gross JTD to zero.
  - Maturity ladder: beta-tech LONG SENIOR_DEBT at 0.1 Y (floor), 0.5 Y (ramp),
    1.0 Y (full weight), and 5.0 Y (full weight).
  - Netting / seniority constraints: acme-corp and gamma-energy show accepted
    same-seniority or lower-seniority-rank shorts; eta-finance, zeta-metals, and
    freddie-mac show rejected offsets where the short is HIGHER seniority than
    the long (short rank < long rank).
  - HBR mechanics: NON_US_SOVEREIGN and CORPORATE buckets carry both longs and
    shorts, producing hedge-benefit ratios below 1.0.
  - Credit-quality spectrum: IG, SG, sub-SG, and DEFAULTED are all present.
  - Defaulted issuer path: DEFAULTED-bucket positions with is_defaulted=True
    trigger the LGD = 100 % override regardless of recorded seniority.

Sign convention: cumulative_pnl positive = unrealised gain (reduces gross JTD for
LONG; increases for SHORT). Negative = unrealised loss.

Regulatory traceability:
  - Basel:  MAR22.11 (gross JTD), MAR22.12 (LGD), MAR22.13 (maturity weighting)
  - US NPR: § 210(b)(1) LGD rules; § 210(b)(2) netting; § 210(b)(3) HBR/weights
"""

from __future__ import annotations

from datetime import date

from frtb_drc.data_models import (
    CreditQuality,
    DefaultDirection,
    DrcCalculationContext,
    DrcInstrumentType,
    DrcPosition,
    DrcRiskClass,
    DrcSeniority,
    DrcSourceLineage,
)
from frtb_drc.reference_data import US_NPR_2_0_PROFILE_ID

_LEGAL_ENTITY = "bank-na"
_CURRENCY = "USD"
_CITATION = ("US_NPR_210_SCOPE",)
_SOURCE_SYSTEM = "demo"
_SOURCE_FILE = "frtb_drc.demo_data"


def _pos(
    position_id: str,
    desk_id: str,
    bucket_key: str,
    issuer_id: str,
    seniority: DrcSeniority | str,
    credit_quality: CreditQuality | str,
    default_direction: DefaultDirection | str,
    notional: float,
    maturity_years: float,
    cumulative_pnl: float = 0.0,
    instrument_type: DrcInstrumentType | str = DrcInstrumentType.BOND,
    is_defaulted: bool = False,
    is_gse: bool = False,
    is_pse: bool = False,
    is_covered_bond: bool = False,
) -> DrcPosition:
    return DrcPosition(
        position_id=position_id,
        source_row_id=position_id,
        desk_id=desk_id,
        legal_entity=_LEGAL_ENTITY,
        risk_class=DrcRiskClass.NON_SECURITISATION,
        instrument_type=instrument_type,
        default_direction=default_direction,
        issuer_id=issuer_id,
        tranche_id=None,
        index_series_id=None,
        bucket_key=bucket_key,
        seniority=seniority,
        credit_quality=credit_quality,
        notional=notional,
        market_value=None,
        cumulative_pnl=cumulative_pnl,
        maturity_years=maturity_years,
        currency=_CURRENCY,
        lineage=DrcSourceLineage(
            source_system=_SOURCE_SYSTEM,
            source_file=_SOURCE_FILE,
            source_row_id=position_id,
        ),
        citation_ids=_CITATION,
        is_defaulted=is_defaulted,
        is_gse=is_gse,
        is_pse=is_pse,
        is_covered_bond=is_covered_bond,
    )


# ---------------------------------------------------------------------------
# CORPORATE bucket  (credit-desk)
# ---------------------------------------------------------------------------
# acme-corp: IG obligor with seniority stack.
# corp-acme-nsr-s-001 is a SHORT NON_SENIOR_DEBT against a LONG SENIOR_DEBT:
# short seniority rank (2) >= long seniority rank (1) → offset is ACCEPTED.

_CORP_ACME_SR_L_001 = _pos(
    "corp-acme-sr-l-001", "credit-desk", "CORPORATE", "acme-corp",
    DrcSeniority.SENIOR_DEBT, CreditQuality.INVESTMENT_GRADE,
    DefaultDirection.LONG, 1_000_000, 2.0,
)
_CORP_ACME_NSR_S_001 = _pos(
    "corp-acme-nsr-s-001", "credit-desk", "CORPORATE", "acme-corp",
    DrcSeniority.NON_SENIOR_DEBT, CreditQuality.INVESTMENT_GRADE,
    DefaultDirection.SHORT, 300_000, 1.5,
)

# beta-tech: IG obligor, maturity ladder — exercises the 0.25 Y floor,
# the linear ramp, and full-weight at 1 Y and 5 Y.
_CORP_BETA_SR_L_0Y1 = _pos(
    "corp-beta-sr-l-0y1", "credit-desk", "CORPORATE", "beta-tech",
    DrcSeniority.SENIOR_DEBT, CreditQuality.INVESTMENT_GRADE,
    DefaultDirection.LONG, 500_000, 0.1,
)
_CORP_BETA_SR_L_0Y5 = _pos(
    "corp-beta-sr-l-0y5", "credit-desk", "CORPORATE", "beta-tech",
    DrcSeniority.SENIOR_DEBT, CreditQuality.INVESTMENT_GRADE,
    DefaultDirection.LONG, 500_000, 0.5,
)
_CORP_BETA_SR_L_1Y0 = _pos(
    "corp-beta-sr-l-1y0", "credit-desk", "CORPORATE", "beta-tech",
    DrcSeniority.SENIOR_DEBT, CreditQuality.INVESTMENT_GRADE,
    DefaultDirection.LONG, 500_000, 1.0,
)
_CORP_BETA_SR_L_5Y0 = _pos(
    "corp-beta-sr-l-5y0", "credit-desk", "CORPORATE", "beta-tech",
    DrcSeniority.SENIOR_DEBT, CreditQuality.INVESTMENT_GRADE,
    DefaultDirection.LONG, 500_000, 5.0,
)

# gamma-energy: SG obligor, partial hedge.
# Same seniority rank on both legs → offset is ACCEPTED.
_CORP_GAMMA_NSR_L_001 = _pos(
    "corp-gamma-nsr-l-001", "credit-desk", "CORPORATE", "gamma-energy",
    DrcSeniority.NON_SENIOR_DEBT, CreditQuality.SPECULATIVE_GRADE,
    DefaultDirection.LONG, 800_000, 3.0,
)
_CORP_GAMMA_NSR_S_001 = _pos(
    "corp-gamma-nsr-s-001", "credit-desk", "CORPORATE", "gamma-energy",
    DrcSeniority.NON_SENIOR_DEBT, CreditQuality.SPECULATIVE_GRADE,
    DefaultDirection.SHORT, 400_000, 2.0,
)

# delta-retail: sub-SG, single long with positive cumulative P&L.
# Unrealised gain increases gross JTD (bond trading above par).
_CORP_DELTA_NSR_L_001 = _pos(
    "corp-delta-nsr-l-001", "credit-desk", "CORPORATE", "delta-retail",
    DrcSeniority.NON_SENIOR_DEBT, CreditQuality.SUB_SPECULATIVE_GRADE,
    DefaultDirection.LONG, 600_000, 1.5,
    cumulative_pnl=80_000,
)

# eta-finance: IG, seniority-rejection demo.
# SHORT SENIOR_DEBT (rank 1) CANNOT offset LONG NON_SENIOR_DEBT (rank 2):
# short_rank (1) < long_rank (2) → offset REJECTED.
_CORP_ETA_NSR_L_001 = _pos(
    "corp-eta-nsr-l-001", "credit-desk", "CORPORATE", "eta-finance",
    DrcSeniority.NON_SENIOR_DEBT, CreditQuality.INVESTMENT_GRADE,
    DefaultDirection.LONG, 700_000, 2.0,
)
_CORP_ETA_SR_S_001 = _pos(
    "corp-eta-sr-s-001", "credit-desk", "CORPORATE", "eta-finance",
    DrcSeniority.SENIOR_DEBT, CreditQuality.INVESTMENT_GRADE,
    DefaultDirection.SHORT, 200_000, 1.5,
)

# zeta-metals: IG, second seniority-rejection demo.
_CORP_ZETA_NSR_L_001 = _pos(
    "corp-zeta-nsr-l-001", "credit-desk", "CORPORATE", "zeta-metals",
    DrcSeniority.NON_SENIOR_DEBT, CreditQuality.INVESTMENT_GRADE,
    DefaultDirection.LONG, 500_000, 3.0,
)
_CORP_ZETA_SR_S_001 = _pos(
    "corp-zeta-sr-s-001", "credit-desk", "CORPORATE", "zeta-metals",
    DrcSeniority.SENIOR_DEBT, CreditQuality.INVESTMENT_GRADE,
    DefaultDirection.SHORT, 200_000, 2.0,
)

# theta-pharma: IG, NOT_RECOVERY_LINKED → LGD = 0, gross JTD = 0.
_CORP_THETA_NRL_L_001 = _pos(
    "corp-theta-nrl-l-001", "credit-desk", "CORPORATE", "theta-pharma",
    DrcSeniority.NOT_RECOVERY_LINKED, CreditQuality.INVESTMENT_GRADE,
    DefaultDirection.LONG, 1_000_000, 1.0,
)

# mu-industries: IG, large negative P&L floors gross JTD to zero.
# raw_jtd = 0.75 * 500 000 + (-400 000) = 375 000 - 400 000 = -25 000 → 0.
_CORP_MU_SR_L_001 = _pos(
    "corp-mu-sr-l-001", "credit-desk", "CORPORATE", "mu-industries",
    DrcSeniority.SENIOR_DEBT, CreditQuality.INVESTMENT_GRADE,
    DefaultDirection.LONG, 500_000, 2.0,
    cumulative_pnl=-400_000,
)

# lambda-holdings: SG corporate equity — LGD = 100 %.
_CORP_LAMBDA_EQ_L_001 = _pos(
    "corp-lambda-eq-l-001", "credit-desk", "CORPORATE", "lambda-holdings",
    DrcSeniority.EQUITY, CreditQuality.SPECULATIVE_GRADE,
    DefaultDirection.LONG, 400_000, 1.0,
    instrument_type=DrcInstrumentType.EQUITY,
)

CORPORATE_POSITIONS: tuple[DrcPosition, ...] = (
    _CORP_ACME_SR_L_001,
    _CORP_ACME_NSR_S_001,
    _CORP_BETA_SR_L_0Y1,
    _CORP_BETA_SR_L_0Y5,
    _CORP_BETA_SR_L_1Y0,
    _CORP_BETA_SR_L_5Y0,
    _CORP_GAMMA_NSR_L_001,
    _CORP_GAMMA_NSR_S_001,
    _CORP_DELTA_NSR_L_001,
    _CORP_ETA_NSR_L_001,
    _CORP_ETA_SR_S_001,
    _CORP_ZETA_NSR_L_001,
    _CORP_ZETA_SR_S_001,
    _CORP_THETA_NRL_L_001,
    _CORP_MU_SR_L_001,
    _CORP_LAMBDA_EQ_L_001,
)

# ---------------------------------------------------------------------------
# NON_US_SOVEREIGN bucket  (rates-desk)
# ---------------------------------------------------------------------------
# uk-sovereign: IG, long hedged by same-seniority short (offset ACCEPTED).
_SOV_UK_SR_L_001 = _pos(
    "sov-uk-sr-l-001", "rates-desk", "NON_US_SOVEREIGN", "uk-sovereign",
    DrcSeniority.SENIOR_DEBT, CreditQuality.INVESTMENT_GRADE,
    DefaultDirection.LONG, 2_000_000, 5.0,
)
_SOV_UK_SR_S_001 = _pos(
    "sov-uk-sr-s-001", "rates-desk", "NON_US_SOVEREIGN", "uk-sovereign",
    DrcSeniority.SENIOR_DEBT, CreditQuality.INVESTMENT_GRADE,
    DefaultDirection.SHORT, 1_000_000, 3.0,
)

# germany-sovereign: IG, long with positive P&L (premium bond).
# cumulative_pnl = +200 000 → gross_jtd = 0.75 * 2 500 000 + 200 000 = 2 075 000.
_SOV_GERMANY_SR_L_001 = _pos(
    "sov-germany-sr-l-001", "rates-desk", "NON_US_SOVEREIGN", "germany-sovereign",
    DrcSeniority.SENIOR_DEBT, CreditQuality.INVESTMENT_GRADE,
    DefaultDirection.LONG, 2_500_000, 10.0,
    cumulative_pnl=200_000,
)

# japan-sovereign: IG, partial hedge.
_SOV_JAPAN_SR_L_001 = _pos(
    "sov-japan-sr-l-001", "rates-desk", "NON_US_SOVEREIGN", "japan-sovereign",
    DrcSeniority.SENIOR_DEBT, CreditQuality.INVESTMENT_GRADE,
    DefaultDirection.LONG, 1_800_000, 7.0,
)
_SOV_JAPAN_SR_S_001 = _pos(
    "sov-japan-sr-s-001", "rates-desk", "NON_US_SOVEREIGN", "japan-sovereign",
    DrcSeniority.SENIOR_DEBT, CreditQuality.INVESTMENT_GRADE,
    DefaultDirection.SHORT, 600_000, 5.0,
)

# brazil-sovereign: SG, partial hedge — higher risk weight (22 %).
_SOV_BRAZIL_SR_L_001 = _pos(
    "sov-brazil-sr-l-001", "rates-desk", "NON_US_SOVEREIGN", "brazil-sovereign",
    DrcSeniority.SENIOR_DEBT, CreditQuality.SPECULATIVE_GRADE,
    DefaultDirection.LONG, 1_500_000, 3.0,
)
_SOV_BRAZIL_SR_S_001 = _pos(
    "sov-brazil-sr-s-001", "rates-desk", "NON_US_SOVEREIGN", "brazil-sovereign",
    DrcSeniority.SENIOR_DEBT, CreditQuality.SPECULATIVE_GRADE,
    DefaultDirection.SHORT, 500_000, 1.5,
)

# italy-sovereign: SG, unhedged long.
_SOV_ITALY_SR_L_001 = _pos(
    "sov-italy-sr-l-001", "rates-desk", "NON_US_SOVEREIGN", "italy-sovereign",
    DrcSeniority.SENIOR_DEBT, CreditQuality.SPECULATIVE_GRADE,
    DefaultDirection.LONG, 1_200_000, 5.0,
)

# mexico-sovereign: SG, single long.
_SOV_MEXICO_SR_L_001 = _pos(
    "sov-mexico-sr-l-001", "rates-desk", "NON_US_SOVEREIGN", "mexico-sovereign",
    DrcSeniority.SENIOR_DEBT, CreditQuality.SPECULATIVE_GRADE,
    DefaultDirection.LONG, 900_000, 3.0,
)

# argentina-sovereign: sub-SG — highest sovereign risk weight (50 %).
_SOV_ARGENTINA_SR_L_001 = _pos(
    "sov-argentina-sr-l-001", "rates-desk", "NON_US_SOVEREIGN", "argentina-sovereign",
    DrcSeniority.SENIOR_DEBT, CreditQuality.SUB_SPECULATIVE_GRADE,
    DefaultDirection.LONG, 1_000_000, 2.0,
)

# france-sovereign: IG, unhedged — rounds the G7 sovereign exposure to 40 positions.
_SOV_FRANCE_SR_L_001 = _pos(
    "sov-france-sr-l-001", "rates-desk", "NON_US_SOVEREIGN", "france-sovereign",
    DrcSeniority.SENIOR_DEBT, CreditQuality.INVESTMENT_GRADE,
    DefaultDirection.LONG, 1_600_000, 5.0,
)

NON_US_SOVEREIGN_POSITIONS: tuple[DrcPosition, ...] = (
    _SOV_UK_SR_L_001,
    _SOV_UK_SR_S_001,
    _SOV_GERMANY_SR_L_001,
    _SOV_JAPAN_SR_L_001,
    _SOV_JAPAN_SR_S_001,
    _SOV_BRAZIL_SR_L_001,
    _SOV_BRAZIL_SR_S_001,
    _SOV_ITALY_SR_L_001,
    _SOV_MEXICO_SR_L_001,
    _SOV_ARGENTINA_SR_L_001,
    _SOV_FRANCE_SR_L_001,
)

# ---------------------------------------------------------------------------
# PSE_GSE bucket  (structured-desk)
# ---------------------------------------------------------------------------
# fannie-mae: GSE-guaranteed debt (LGD = 25 %), same-seniority short ACCEPTED.
_PSE_FANNIE_GG_L_001 = _pos(
    "pse-fannie-gg-l-001", "structured-desk", "PSE_GSE", "fannie-mae",
    DrcSeniority.GSE_GUARANTEED, CreditQuality.INVESTMENT_GRADE,
    DefaultDirection.LONG, 1_500_000, 5.0,
    is_gse=True,
)
_PSE_FANNIE_GG_S_001 = _pos(
    "pse-fannie-gg-s-001", "structured-desk", "PSE_GSE", "fannie-mae",
    DrcSeniority.GSE_GUARANTEED, CreditQuality.INVESTMENT_GRADE,
    DefaultDirection.SHORT, 500_000, 3.0,
    is_gse=True,
)

# freddie-mac: GSE-issued-not-guaranteed long (LGD = 75 %, rank = 1).
# SHORT GSE_GUARANTEED (rank 0) CANNOT offset LONG GING (rank 1):
# short_rank (0) < long_rank (1) → offset REJECTED.
_PSE_FREDDIE_GING_L_001 = _pos(
    "pse-freddie-ging-l-001", "structured-desk", "PSE_GSE", "freddie-mac",
    DrcSeniority.GSE_ISSUED_NOT_GUARANTEED, CreditQuality.INVESTMENT_GRADE,
    DefaultDirection.LONG, 1_000_000, 5.0,
    is_gse=True,
)
_PSE_FREDDIE_GG_S_001 = _pos(
    "pse-freddie-gg-s-001", "structured-desk", "PSE_GSE", "freddie-mac",
    DrcSeniority.GSE_GUARANTEED, CreditQuality.INVESTMENT_GRADE,
    DefaultDirection.SHORT, 300_000, 3.0,
    is_gse=True,
)

# ipsa-muni: U.S. PSE (LGD = 50 %).
_PSE_IPSA_PSE_L_001 = _pos(
    "pse-ipsa-pse-l-001", "structured-desk", "PSE_GSE", "ipsa-muni",
    DrcSeniority.PSE, CreditQuality.INVESTMENT_GRADE,
    DefaultDirection.LONG, 800_000, 3.0,
    is_pse=True,
)

# tri-county-authority: second PSE obligor.
_PSE_TRICITY_PSE_L_001 = _pos(
    "pse-tricity-pse-l-001", "structured-desk", "PSE_GSE", "tri-county-authority",
    DrcSeniority.PSE, CreditQuality.INVESTMENT_GRADE,
    DefaultDirection.LONG, 400_000, 1.5,
    is_pse=True,
)

# northern-covered-bank: covered bond (LGD = 25 %).
_PSE_COVERED_CB_L_001 = _pos(
    "pse-covered-cb-l-001", "structured-desk", "PSE_GSE", "northern-covered-bank",
    DrcSeniority.COVERED_BOND, CreditQuality.INVESTMENT_GRADE,
    DefaultDirection.LONG, 600_000, 2.0,
    is_covered_bond=True,
)

PSE_GSE_POSITIONS: tuple[DrcPosition, ...] = (
    _PSE_FANNIE_GG_L_001,
    _PSE_FANNIE_GG_S_001,
    _PSE_FREDDIE_GING_L_001,
    _PSE_FREDDIE_GG_S_001,
    _PSE_IPSA_PSE_L_001,
    _PSE_TRICITY_PSE_L_001,
    _PSE_COVERED_CB_L_001,
)

# ---------------------------------------------------------------------------
# DEFAULTED bucket  (structured-desk)
# ---------------------------------------------------------------------------
# For all defaulted positions: is_defaulted=True overrides LGD to 1.0
# regardless of recorded seniority; credit_quality = DEFAULTED; risk weight = 100 %.

# epsilon-holdings: two positions, one with maturity floor.
_DEF_EPSILON_SR_L_001 = _pos(
    "def-epsilon-sr-l-001", "structured-desk", "DEFAULTED", "epsilon-holdings",
    DrcSeniority.SENIOR_DEBT, CreditQuality.DEFAULTED,
    DefaultDirection.LONG, 500_000, 2.0,
    is_defaulted=True,
)
_DEF_EPSILON_SR_L_0Y3 = _pos(
    "def-epsilon-sr-l-0y3", "structured-desk", "DEFAULTED", "epsilon-holdings",
    DrcSeniority.SENIOR_DEBT, CreditQuality.DEFAULTED,
    DefaultDirection.LONG, 300_000, 0.3,
    is_defaulted=True,
)

# omega-corp: non-senior debt defaulted.
_DEF_OMEGA_NSR_L_001 = _pos(
    "def-omega-nsr-l-001", "structured-desk", "DEFAULTED", "omega-corp",
    DrcSeniority.NON_SENIOR_DEBT, CreditQuality.DEFAULTED,
    DefaultDirection.LONG, 400_000, 1.5,
    is_defaulted=True,
)

# pi-industrial: equity defaulted.
_DEF_PI_EQ_L_001 = _pos(
    "def-pi-eq-l-001", "structured-desk", "DEFAULTED", "pi-industrial",
    DrcSeniority.EQUITY, CreditQuality.DEFAULTED,
    DefaultDirection.LONG, 300_000, 3.0,
    instrument_type=DrcInstrumentType.EQUITY,
    is_defaulted=True,
)

# sigma-holdings: already impaired — negative P&L reduces gross JTD.
# gross_jtd = max(1.0 * 600 000 + (-120 000), 0) = 480 000.
_DEF_SIGMA_SR_L_001 = _pos(
    "def-sigma-sr-l-001", "structured-desk", "DEFAULTED", "sigma-holdings",
    DrcSeniority.SENIOR_DEBT, CreditQuality.DEFAULTED,
    DefaultDirection.LONG, 600_000, 1.0,
    cumulative_pnl=-120_000,
    is_defaulted=True,
)

# rho-financial: short residual maturity, exercises the linear weight ramp.
# maturity = 0.8 Y → weight = (0.8 - 0.25) / (1.0 - 0.25) ≈ 0.733.
_DEF_RHO_SR_L_001 = _pos(
    "def-rho-sr-l-001", "structured-desk", "DEFAULTED", "rho-financial",
    DrcSeniority.SENIOR_DEBT, CreditQuality.DEFAULTED,
    DefaultDirection.LONG, 250_000, 0.8,
    is_defaulted=True,
)

DEFAULTED_POSITIONS: tuple[DrcPosition, ...] = (
    _DEF_EPSILON_SR_L_001,
    _DEF_EPSILON_SR_L_0Y3,
    _DEF_OMEGA_NSR_L_001,
    _DEF_PI_EQ_L_001,
    _DEF_SIGMA_SR_L_001,
    _DEF_RHO_SR_L_001,
)

# ---------------------------------------------------------------------------
# Full portfolio
# ---------------------------------------------------------------------------

ALL_POSITIONS: tuple[DrcPosition, ...] = (
    *CORPORATE_POSITIONS,
    *NON_US_SOVEREIGN_POSITIONS,
    *PSE_GSE_POSITIONS,
    *DEFAULTED_POSITIONS,
)

DEMO_CALCULATION_DATE = date(2026, 5, 29)

DEMO_CONTEXT = DrcCalculationContext(
    run_id="demo-drc-nonsec-v2",
    calculation_date=DEMO_CALCULATION_DATE,
    base_currency=_CURRENCY,
    profile_id=US_NPR_2_0_PROFILE_ID,
)
