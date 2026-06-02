"""Package-local warning helpers for CVA profile/method combinations."""

from __future__ import annotations

from frtb_cva.data_models import CvaMethod


def profile_warnings(profile_id: str, method: CvaMethod) -> tuple[str, ...]:
    """Return deterministic non-blocking warnings for supported CVA profiles."""

    if profile_id != "BASEL_MAR50_2020":
        return ()
    if method in {CvaMethod.SA_CVA, CvaMethod.MIXED_CARVE_OUT, CvaMethod.BA_CVA_FULL}:
        return ()
    return ()
