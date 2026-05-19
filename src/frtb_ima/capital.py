"""
Models-based capital assembly.

Working assumption (NPR 2.0 / Basel FRTB IMA):

    MBC = max(IMCC_t-1 + SES_t-1,  multiplier * IMCC_60d_avg + SES_60d_avg)
          + PLA_addon

    multiplier:  supervisory multiplier, floor 1.5 (increases with backtesting exceptions).
    pla_addon:   additional capital charge from PLA amber/red zone.

This is the desk-level aggregation. Firm-level capital would sum approved desks
and add fallback SA capital for non-approved desks — not implemented here.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CapitalComponents:
    imcc_t_minus_1: float
    ses_t_minus_1: float
    imcc_60d_avg: float
    ses_60d_avg: float
    multiplier: float
    pla_addon: float
    models_based_capital: float
    binding_term: str   # "SPOT" or "AVERAGE"


def models_based_capital(
    imcc_t_minus_1: float,
    ses_t_minus_1: float,
    imcc_60d_avg: float,
    ses_60d_avg: float,
    multiplier: float = 1.5,
    pla_addon: float = 0.0,
) -> CapitalComponents:
    """
    Compute models-based capital for one approved desk.

    Formula:
        MBC = max(
            IMCC_{t-1} + SES_{t-1},
            multiplier * IMCC_60d_avg + SES_60d_avg
        ) + PLA_addon

    Args:
        imcc_t_minus_1: Most recent day's IMCC.
        ses_t_minus_1:  Most recent day's SES.
        imcc_60d_avg:   60-business-day average IMCC.
        ses_60d_avg:    60-business-day average SES.
        multiplier:     Supervisory multiplier (floor 1.5; increases with
                        backtesting exceptions per Basel / NPR 2.0).
        pla_addon:      PLA capital add-on (zero for green zone desks).

    Returns:
        CapitalComponents with breakdown and binding term.
    """
    if multiplier < 1.5:
        raise ValueError(f"multiplier must be >= 1.5 (floor), got {multiplier}")

    spot_term    = imcc_t_minus_1 + ses_t_minus_1
    average_term = multiplier * imcc_60d_avg + ses_60d_avg

    if spot_term >= average_term:
        binding = "SPOT"
        mbc = spot_term + pla_addon
    else:
        binding = "AVERAGE"
        mbc = average_term + pla_addon

    return CapitalComponents(
        imcc_t_minus_1=imcc_t_minus_1,
        ses_t_minus_1=ses_t_minus_1,
        imcc_60d_avg=imcc_60d_avg,
        ses_60d_avg=ses_60d_avg,
        multiplier=multiplier,
        pla_addon=pla_addon,
        models_based_capital=mbc,
        binding_term=binding,
    )


def supervisory_multiplier(exception_count: int) -> float:
    """
    Map backtesting exception count to supervisory multiplier.

    Basel traffic-light add-ons (working assumption):
        0-4   exceptions: 1.50
        5     exceptions: 1.70
        6     exceptions: 1.76
        7     exceptions: 1.83
        8     exceptions: 1.88
        9     exceptions: 1.92
        10+   exceptions: 2.00

    These are the Basel standard add-ons; NPR 2.0 may differ.
    """
    MULTIPLIERS = {
        0: 1.50, 1: 1.50, 2: 1.50, 3: 1.50, 4: 1.50,
        5: 1.70, 6: 1.76, 7: 1.83, 8: 1.88, 9: 1.92,
    }
    return MULTIPLIERS.get(exception_count, 2.00)
