"""
Baseline-vs-candidate CVA capital impact assessment.

Returns :class:`frtb_common.impact.CapitalImpact` (see ADR 0038).
``CvaCapitalImpact`` has been removed; callers should import
``CapitalImpact`` from ``frtb_common.impact`` directly.
"""

from __future__ import annotations

from frtb_common.impact import CapitalImpact, ImpactMethod

from frtb_cva.data_models import CvaCapitalResult


def assess_cva_capital_impact(
    baseline: CvaCapitalResult,
    candidate: CvaCapitalResult,
) -> CapitalImpact:
    """Return the capital delta between two results (finite-difference method).

    The returned :class:`~frtb_common.impact.CapitalImpact` carries:

    * ``component = "frtb_cva"``
    * ``method = ImpactMethod.FINITE_DIFFERENCE``
    * ``baseline_input_hash`` / ``candidate_input_hash`` from the respective
      :attr:`CvaCapitalResult.input_hash` fields.
    * ``baseline_profile_hash`` / ``candidate_profile_hash`` from the
      respective :attr:`CvaCapitalResult.profile_hash` fields.

        Parameters
        ----------
        baseline : CvaCapitalResult
            Reference CVA capital result for the impact comparison.
        candidate : CvaCapitalResult
            Candidate CVA capital result whose delta is measured.

        Returns
        -------
        CapitalImpact
            Finite-difference impact record with input and profile hashes for both runs.
    """
    return CapitalImpact(
        baseline_run_id=baseline.run_id,
        candidate_run_id=candidate.run_id,
        component="frtb_cva",
        baseline_total=baseline.total_cva_capital,
        candidate_total=candidate.total_cva_capital,
        delta=candidate.total_cva_capital - baseline.total_cva_capital,
        method=ImpactMethod.FINITE_DIFFERENCE,
        baseline_input_hash=baseline.input_hash,
        candidate_input_hash=candidate.input_hash,
        baseline_profile_hash=baseline.profile_hash,
        candidate_profile_hash=candidate.profile_hash,
    )


__all__ = ["assess_cva_capital_impact"]
