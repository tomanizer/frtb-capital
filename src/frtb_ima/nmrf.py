"""
Non-Modellable Risk Factor (NMRF) Stressed Expected Shortfall (SES) prototype.

Working assumptions (NPR 2.0 / Basel FRTB IMA):

    - Type A NMRFs: included in both IMCC and SES.
    - Type B NMRFs: included in SES only, with conservative aggregation rho = 0.36.

Aggregation formulas used here:

    Type A SES (full correlation assumed — conservative linear sum):
        SES_A = sum(SES_i  for i in Type_A)

    Type B SES (partial correlation via rho parameter):
        SES_B = sqrt(
            rho    * (sum(SES_i))^2
            + (1 - rho) * sum(SES_i^2)
        )

    Combined SES:
        SES = SES_A + SES_B

This is a linear / sensitivity-based prototype.
The direct method and stepwise method are not yet implemented.

TODOs:
    - Direct method: construct a stress scenario specific to each NMRF.
    - Stepwise method: sequential sensitivity to each factor.
    - Full portfolio revaluation path.
"""

from __future__ import annotations

import math


def ses_for_nmrf_linear(sensitivity: float, shock: float) -> float:
    """
    Compute the SES contribution for a single NMRF using a linear approximation.

    SES_i = |sensitivity_i| * shock_i

    Args:
        sensitivity: First-order sensitivity (dollar P&L per unit of risk factor move).
        shock:       Stress shock size (in risk factor units, positive).

    Returns:
        SES contribution as a positive scalar.
    """
    return abs(sensitivity) * abs(shock)


def aggregate_ses_type_a(values: list[float]) -> float:
    """
    Aggregate SES contributions for Type A NMRFs.

    Full (worst-case) correlation assumed: linear sum.
    """
    return sum(abs(v) for v in values)


def aggregate_ses_type_b(values: list[float], rho: float = 0.36) -> float:
    """
    Aggregate SES contributions for Type B NMRFs.

    Partial correlation via rho (default 0.36 per NPR 2.0 working assumption):

        SES_B = sqrt(rho * (sum SES_i)^2 + (1 - rho) * sum(SES_i^2))

    Args:
        values: Individual SES contributions (positive scalars).
        rho:    Correlation parameter. 0 = fully diversified, 1 = fully correlated.
    """
    if not values:
        return 0.0
    if not (0.0 <= rho <= 1.0):
        raise ValueError(f"rho must be in [0, 1], got {rho}")

    abs_vals = [abs(v) for v in values]
    linear_sum = sum(abs_vals)
    sum_of_squares = sum(v ** 2 for v in abs_vals)

    return math.sqrt(rho * linear_sum ** 2 + (1.0 - rho) * sum_of_squares)


def aggregate_ses(type_a_values: list[float], type_b_values: list[float]) -> float:
    """
    Compute total SES from Type A and Type B NMRF contributions.

    SES = SES_A + SES_B

    Type A and Type B totals are summed (no cross-type diversification credit
    in this prototype).
    """
    return aggregate_ses_type_a(type_a_values) + aggregate_ses_type_b(type_b_values)
