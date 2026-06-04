"""Package-local warning helpers for CVA profile/method combinations."""

from __future__ import annotations

from frtb_cva.data_models import CvaMethod


def profile_warnings(profile_id: str, method: CvaMethod) -> tuple[str, ...]:
    """Return deterministic non-blocking warnings for supported CVA profiles.

    Parameters
    ----------
    profile_id : str
        Active CVA regulatory profile identifier for support and warning selection.
    method : CvaMethod
        Requested CVA calculation method (BA-CVA, SA-CVA, or mixed carve-out).

    Returns
    -------
    tuple[str, ...]
        Non-blocking warning messages; empty when the profile/method pair is fully supported.
    """

    if profile_id != "BASEL_MAR50_2020":
        return ()
    if method in {CvaMethod.SA_CVA, CvaMethod.MIXED_CARVE_OUT, CvaMethod.BA_CVA_FULL}:
        return ()
    return ()
