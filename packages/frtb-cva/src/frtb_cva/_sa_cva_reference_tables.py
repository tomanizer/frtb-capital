"""Static SA-CVA risk-class reference tables."""

from __future__ import annotations

from frtb_cva.data_models import CreditQuality

CCS_SINGLE_NAME_BUCKETS = frozenset({"1a", "1b", "2", "3", "4", "5", "6", "7"})

SA_CVA_VEGA_RW_SIGMA = 0.55

FX_DELTA_RISK_WEIGHT = 0.11
FX_INTER_BUCKET_CORRELATION = 0.6

GIRR_VEGA_INFLATION_FACTOR = "INFL_VOL"
GIRR_VEGA_RATE_FACTOR = "IR_VOL"

CCS_DELTA_TENORS: tuple[str, ...] = ("0.5y", "1y", "3y", "5y", "10y")
CCS_QUALIFIED_INDEX_BUCKET = "8"

CCS_DELTA_RISK_WEIGHTS: dict[tuple[str, CreditQuality], float] = {
    ("1a", CreditQuality.INVESTMENT_GRADE): 0.005,
    ("1b", CreditQuality.INVESTMENT_GRADE): 0.01,
    ("2", CreditQuality.INVESTMENT_GRADE): 0.05,
    ("3", CreditQuality.INVESTMENT_GRADE): 0.03,
    ("4", CreditQuality.INVESTMENT_GRADE): 0.03,
    ("5", CreditQuality.INVESTMENT_GRADE): 0.02,
    ("6", CreditQuality.INVESTMENT_GRADE): 0.015,
    ("7", CreditQuality.INVESTMENT_GRADE): 0.05,
    ("8", CreditQuality.INVESTMENT_GRADE): 0.015,
    ("1a", CreditQuality.HIGH_YIELD): 0.02,
    ("1b", CreditQuality.HIGH_YIELD): 0.04,
    ("2", CreditQuality.HIGH_YIELD): 0.12,
    ("3", CreditQuality.HIGH_YIELD): 0.07,
    ("4", CreditQuality.HIGH_YIELD): 0.085,
    ("5", CreditQuality.HIGH_YIELD): 0.055,
    ("6", CreditQuality.HIGH_YIELD): 0.05,
    ("7", CreditQuality.HIGH_YIELD): 0.05,
    ("8", CreditQuality.HIGH_YIELD): 0.05,
    ("1a", CreditQuality.NOT_RATED): 0.02,
    ("1b", CreditQuality.NOT_RATED): 0.04,
    ("2", CreditQuality.NOT_RATED): 0.12,
    ("3", CreditQuality.NOT_RATED): 0.07,
    ("4", CreditQuality.NOT_RATED): 0.085,
    ("5", CreditQuality.NOT_RATED): 0.055,
    ("6", CreditQuality.NOT_RATED): 0.05,
    ("7", CreditQuality.NOT_RATED): 0.05,
    ("8", CreditQuality.NOT_RATED): 0.05,
}

CCS_GAMMA_BC: dict[tuple[str, str], float] = {
    ("1", "1"): 1.0,
    ("1", "2"): 0.10,
    ("1", "3"): 0.20,
    ("1", "4"): 0.25,
    ("1", "5"): 0.20,
    ("1", "6"): 0.15,
    ("1", "7"): 0.0,
    ("1", "8"): 0.45,
    ("2", "2"): 1.0,
    ("2", "3"): 0.15,
    ("2", "4"): 0.20,
    ("2", "5"): 0.05,
    ("2", "6"): 0.0,
    ("2", "7"): 0.0,
    ("2", "8"): 0.45,
    ("3", "3"): 1.0,
    ("3", "4"): 0.25,
    ("3", "5"): 0.05,
    ("3", "6"): 0.0,
    ("3", "7"): 0.0,
    ("3", "8"): 0.45,
    ("4", "4"): 1.0,
    ("4", "5"): 0.05,
    ("4", "6"): 0.0,
    ("4", "7"): 0.0,
    ("4", "8"): 0.45,
    ("5", "5"): 1.0,
    ("5", "6"): 0.0,
    ("5", "7"): 0.0,
    ("5", "8"): 0.45,
    ("6", "6"): 1.0,
    ("6", "7"): 0.0,
    ("6", "8"): 0.45,
    ("7", "7"): 1.0,
    ("7", "8"): 0.0,
    ("8", "8"): 1.0,
}

RCS_DELTA_RISK_WEIGHTS: dict[str, float] = {
    "1": 0.005,
    "2": 0.01,
    "3": 0.05,
    "4": 0.03,
    "5": 0.03,
    "6": 0.02,
    "7": 0.015,
    "8": 0.02,
    "9": 0.04,
    "10": 0.12,
    "11": 0.07,
    "12": 0.085,
    "13": 0.055,
    "14": 0.05,
    "15": 0.12,
    "16": 0.015,
    "17": 0.05,
}

RCS_QUALIFIED_INDEX_BUCKETS = frozenset({"16", "17"})
RCS_SINGLE_NAME_BUCKETS = frozenset(RCS_DELTA_RISK_WEIGHTS) - RCS_QUALIFIED_INDEX_BUCKETS
RCS_CROSS_QUALITY_HALVING_BUCKETS = frozenset(
    {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14"}
)
RCS_IG_BUCKETS = frozenset({"1", "2", "3", "4", "5", "6", "7", "16"})
RCS_HY_NR_BUCKETS = frozenset({"8", "9", "10", "11", "12", "13", "14", "15", "17"})

# Maps bucket ids to MAR50.67 Table 9 row/column labels.
RCS_TABLE_COORDINATES: dict[str, str] = {
    "1": "1/8",
    "8": "1/8",
    "2": "2/9",
    "9": "2/9",
    "3": "3/10",
    "10": "3/10",
    "4": "4/11",
    "11": "4/11",
    "5": "5/12",
    "12": "5/12",
    "6": "6/13",
    "13": "6/13",
    "7": "7/14",
    "14": "7/14",
    "15": "15",
    "16": "16",
    "17": "17",
}

RCS_GAMMA_BY_COORDINATE: dict[tuple[str, str], float] = {
    ("1/8", "1/8"): 1.0,
    ("1/8", "2/9"): 0.75,
    ("1/8", "3/10"): 0.10,
    ("1/8", "4/11"): 0.20,
    ("1/8", "5/12"): 0.25,
    ("1/8", "6/13"): 0.20,
    ("1/8", "7/14"): 0.15,
    ("1/8", "15"): 0.0,
    ("1/8", "16"): 0.45,
    ("1/8", "17"): 0.45,
    ("2/9", "2/9"): 1.0,
    ("2/9", "3/10"): 0.05,
    ("2/9", "4/11"): 0.15,
    ("2/9", "5/12"): 0.20,
    ("2/9", "6/13"): 0.15,
    ("2/9", "7/14"): 0.10,
    ("2/9", "15"): 0.0,
    ("2/9", "16"): 0.45,
    ("2/9", "17"): 0.45,
    ("3/10", "3/10"): 1.0,
    ("3/10", "4/11"): 0.05,
    ("3/10", "5/12"): 0.15,
    ("3/10", "6/13"): 0.20,
    ("3/10", "7/14"): 0.05,
    ("3/10", "15"): 0.0,
    ("3/10", "16"): 0.45,
    ("3/10", "17"): 0.45,
    ("4/11", "4/11"): 1.0,
    ("4/11", "5/12"): 0.20,
    ("4/11", "6/13"): 0.25,
    ("4/11", "7/14"): 0.05,
    ("4/11", "15"): 0.0,
    ("4/11", "16"): 0.45,
    ("4/11", "17"): 0.45,
    ("5/12", "5/12"): 1.0,
    ("5/12", "6/13"): 0.25,
    ("5/12", "7/14"): 0.05,
    ("5/12", "15"): 0.0,
    ("5/12", "16"): 0.45,
    ("5/12", "17"): 0.45,
    ("6/13", "6/13"): 1.0,
    ("6/13", "7/14"): 0.05,
    ("6/13", "15"): 0.0,
    ("6/13", "16"): 0.45,
    ("6/13", "17"): 0.45,
    ("7/14", "7/14"): 1.0,
    ("7/14", "15"): 0.0,
    ("7/14", "16"): 0.45,
    ("7/14", "17"): 0.45,
    ("15", "15"): 1.0,
    ("15", "16"): 0.0,
    ("15", "17"): 0.0,
    ("16", "16"): 1.0,
    ("16", "17"): 0.75,
    ("17", "17"): 1.0,
}

EQUITY_DELTA_RISK_WEIGHTS: dict[str, float] = {
    "1": 0.55,
    "2": 0.60,
    "3": 0.45,
    "4": 0.55,
    "5": 0.30,
    "6": 0.35,
    "7": 0.40,
    "8": 0.50,
    "9": 0.70,
    "10": 0.50,
    "11": 0.70,
    "12": 0.15,
    "13": 0.25,
}

EQUITY_VEGA_RW_SCALAR: dict[str, float] = {
    "1": 0.78,
    "2": 0.78,
    "3": 0.78,
    "4": 0.78,
    "5": 0.78,
    "6": 0.78,
    "7": 0.78,
    "8": 0.78,
    "9": 1.0,
    "10": 1.0,
    "11": 1.0,
    "12": 0.78,
    "13": 1.0,
}

EQUITY_LARGE_CAP_BUCKETS = frozenset({"1", "2", "3", "4", "5", "6", "7", "8", "12"})
EQUITY_OTHER_BUCKET = "11"
EQUITY_QUALIFIED_INDEX_BUCKETS = frozenset({"12", "13"})

COMMODITY_DELTA_RISK_WEIGHTS: dict[str, float] = {
    "1": 0.30,
    "2": 0.35,
    "3": 0.60,
    "4": 0.80,
    "5": 0.40,
    "6": 0.45,
    "7": 0.20,
    "8": 0.35,
    "9": 0.25,
    "10": 0.35,
    "11": 0.50,
}

COMMODITY_MAIN_BUCKETS = frozenset({"1", "2", "3", "4", "5", "6", "7", "8", "9", "10"})
COMMODITY_OTHER_BUCKET = "11"


__all__ = [
    "CCS_DELTA_RISK_WEIGHTS",
    "CCS_DELTA_TENORS",
    "CCS_GAMMA_BC",
    "CCS_QUALIFIED_INDEX_BUCKET",
    "CCS_SINGLE_NAME_BUCKETS",
    "COMMODITY_DELTA_RISK_WEIGHTS",
    "COMMODITY_MAIN_BUCKETS",
    "COMMODITY_OTHER_BUCKET",
    "EQUITY_DELTA_RISK_WEIGHTS",
    "EQUITY_LARGE_CAP_BUCKETS",
    "EQUITY_OTHER_BUCKET",
    "EQUITY_QUALIFIED_INDEX_BUCKETS",
    "EQUITY_VEGA_RW_SCALAR",
    "FX_DELTA_RISK_WEIGHT",
    "FX_INTER_BUCKET_CORRELATION",
    "GIRR_VEGA_INFLATION_FACTOR",
    "GIRR_VEGA_RATE_FACTOR",
    "RCS_CROSS_QUALITY_HALVING_BUCKETS",
    "RCS_DELTA_RISK_WEIGHTS",
    "RCS_GAMMA_BY_COORDINATE",
    "RCS_HY_NR_BUCKETS",
    "RCS_IG_BUCKETS",
    "RCS_QUALIFIED_INDEX_BUCKETS",
    "RCS_SINGLE_NAME_BUCKETS",
    "RCS_TABLE_COORDINATES",
    "SA_CVA_VEGA_RW_SIGMA",
]
