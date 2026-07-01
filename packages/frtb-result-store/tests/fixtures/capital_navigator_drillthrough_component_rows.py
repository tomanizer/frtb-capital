"""Component drillthrough rows for the Capital Navigator fixture."""

from __future__ import annotations

from datetime import date


def _ima(
    desk_id: str,
    portfolio_id: str,
    book_id: str,
    position_id: str,
    risk_factor_id: str,
    risk_factor_set_id: str,
    scenario_id: str,
    observation_date: date,
    pnl_amount: float,
    tail_flag: bool,
    source_row_id: str,
    modellability_status: str,
    ses_component: str,
    stress_method: str,
) -> dict[str, object]:
    return {
        "desk_id": desk_id,
        "portfolio_id": portfolio_id,
        "book_id": book_id,
        "position_id": position_id,
        "risk_factor_id": risk_factor_id,
        "risk_factor_set_id": risk_factor_set_id,
        "scenario_id": scenario_id,
        "observation_date": observation_date,
        "pnl_amount": pnl_amount,
        "currency": "USD",
        "tail_flag": tail_flag,
        "source_row_id": source_row_id,
        "modellability_status": modellability_status,
        "ses_component": ses_component,
        "stress_method": stress_method,
    }


def _sbm(
    risk_class: str,
    bucket: str,
    sensitivity_id: str,
    risk_factor_id: str,
    tenor: str,
    sensitivity_amount: float,
    source_row_id: str,
) -> dict[str, object]:
    return {
        "risk_class": risk_class,
        "bucket": bucket,
        "sensitivity_id": sensitivity_id,
        "risk_factor_id": risk_factor_id,
        "tenor": tenor,
        "sensitivity_amount": sensitivity_amount,
        "currency": "USD",
        "source_row_id": source_row_id,
    }


def _drc(
    issuer_id: str,
    obligor_name: str,
    bucket: str,
    seniority: str,
    gross_jtd: float,
    hedge_amount: float,
    net_jtd: float,
    source_row_id: str,
) -> dict[str, object]:
    return {
        "issuer_id": issuer_id,
        "obligor_name": obligor_name,
        "bucket": bucket,
        "seniority": seniority,
        "gross_jtd": gross_jtd,
        "hedge_amount": hedge_amount,
        "net_jtd": net_jtd,
        "currency": "USD",
        "source_row_id": source_row_id,
    }


def _rrao(
    exposure_id: str,
    exposure_class: str,
    notional: float,
    risk_weight: float,
    capital: float,
    source_row_id: str,
) -> dict[str, object]:
    return {
        "exposure_id": exposure_id,
        "exposure_class": exposure_class,
        "notional": notional,
        "risk_weight": risk_weight,
        "capital": capital,
        "currency": "USD",
        "source_row_id": source_row_id,
    }


def _cva(
    counterparty_id: str,
    netting_set_id: str,
    ead: float,
    maturity_years: float,
    risk_weight: float,
    capital: float,
    source_row_id: str,
) -> dict[str, object]:
    return {
        "counterparty_id": counterparty_id,
        "netting_set_id": netting_set_id,
        "ead": ead,
        "maturity_years": maturity_years,
        "risk_weight": risk_weight,
        "capital": capital,
        "currency": "USD",
        "source_row_id": source_row_id,
    }


IMA_ROWS = (
    _ima(
        "rates",
        "rates-options",
        "rates-core",
        "rates-001",
        "rf-girr-usd-5y",
        "girr-usd",
        "s-001",
        date(2026, 6, 1),
        1.25,
        False,
        "ima-rates-imcc-001",
        "MODELLABLE",
        "IMCC_CURRENT_ES",
        "",
    ),
    _ima(
        "rates",
        "rates-options",
        "rates-core",
        "rates-002",
        "rf-girr-usd-basis-nmrfa",
        "girr-usd",
        "s-002",
        date(2026, 6, 2),
        -0.50,
        True,
        "ima-rates-nmrfa-001",
        "TYPE_A_NMRF",
        "SES_NMRF_TYPE_A",
        "DIRECT",
    ),
    _ima(
        "rates",
        "rates-options",
        "rates-core",
        "rates-003",
        "rf-csr-ig-spread-nmrfb",
        "csr-ig",
        "s-003",
        date(2026, 6, 3),
        -0.75,
        True,
        "ima-rates-nmrfb-001",
        "TYPE_B_NMRF",
        "SES_NMRF_TYPE_B",
        "FULL_REVALUATION",
    ),
    _ima(
        "credit",
        "credit-options",
        "credit-core",
        "credit-001",
        "rf-csr-hy-index",
        "csr-hy",
        "s-001",
        date(2026, 6, 1),
        0.90,
        False,
        "ima-credit-imcc-001",
        "MODELLABLE",
        "IMCC_CURRENT_ES",
        "",
    ),
    _ima(
        "credit",
        "credit-options",
        "credit-core",
        "credit-002",
        "rf-csr-hy-single-name-nmrfa",
        "csr-hy",
        "s-002",
        date(2026, 6, 2),
        -0.60,
        True,
        "ima-credit-nmrfa-001",
        "TYPE_A_NMRF",
        "SES_NMRF_TYPE_A",
        "STEPWISE",
    ),
    _ima(
        "credit",
        "credit-options",
        "credit-core",
        "credit-003",
        "rf-equity-large-vol-nmrfb",
        "eq-large",
        "s-003",
        date(2026, 6, 3),
        -1.10,
        True,
        "ima-credit-nmrfb-001",
        "TYPE_B_NMRF",
        "SES_NMRF_TYPE_B",
        "MAX_LOSS_FALLBACK",
    ),
)

SBM_ROWS = (
    _sbm("GIRR", "USD", "sensitivity-girr-usd-5y", "rf-girr-usd-5y", "5Y", 125000.0, "sbm-001"),
    _sbm("GIRR", "USD", "sensitivity-girr-usd-10y", "rf-girr-usd-10y", "10Y", 98000.0, "sbm-002"),
    _sbm("GIRR", "EUR", "sensitivity-girr-eur-2y", "rf-girr-eur-2y", "2Y", 31000.0, "sbm-003"),
    _sbm("CSR_NON_SEC", "IG", "sensitivity-csr-ig-a", "rf-csr-ig-a", "5Y", 45000.0, "sbm-004"),
    _sbm(
        "EQ", "LARGE_CAP", "sensitivity-equity-large-a", "rf-equity-large-a", "", 27000.0, "sbm-005"
    ),
    _sbm(
        "EQ",
        "LARGE_CAP",
        "sensitivity-equity-large-b",
        "rf-equity-large-b",
        "",
        -12000.0,
        "sbm-006",
    ),
)

DRC_ROWS = (
    _drc("issuer-alpha", "Issuer Alpha", "corporate", "SENIOR", 24.0, -6.0, 18.0, "drc-001"),
    _drc("issuer-alpha", "Issuer Alpha", "corporate", "SUBORDINATED", 3.0, -3.0, 0.0, "drc-002"),
    _drc("issuer-beta", "Issuer Beta", "sovereign", "SENIOR", 5.0, -1.0, 4.0, "drc-003"),
    _drc("issuer-gamma", "Issuer Gamma", "financial", "SENIOR", 9.0, -3.0, 6.0, "drc-004"),
)

RRAO_ROWS = (
    _rrao("rrao-line-exotic-001", "EXOTIC_UNDERLIER", 40.0, 0.10, 4.0, "rrao-001"),
    _rrao("rrao-line-cliff-001", "CLIFF_RISK", 20.0, 0.10, 2.0, "rrao-002"),
    _rrao("rrao-line-gap-001", "GAP_RISK", 30.0, 0.10, 3.0, "rrao-003"),
)

CVA_ROWS = (
    _cva("counterparty-bank-a", "bank-a-rates", 100.0, 2.5, 0.12, 12.0, "cva-001"),
    _cva("counterparty-bank-a", "bank-a-fx", 70.0, 1.8, 0.1142857143, 8.0, "cva-002"),
    _cva("counterparty-fund-b", "fund-b-credit", 80.0, 3.0, 0.125, 10.0, "cva-003"),
    _cva("counterparty-corp-c", "corp-c-equity", 45.0, 1.2, 0.1111111111, 5.0, "cva-004"),
    _cva("counterparty-corp-c", "corp-c-rates", 30.0, 2.0, 0.10, 3.0, "cva-005"),
)
