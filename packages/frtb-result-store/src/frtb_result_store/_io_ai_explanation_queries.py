"""Governed AI explanation snapshot query helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from frtb_common.hashing import stable_json_hash

from frtb_result_store._ai_explanation_common import (
    _PROMPT_TEMPLATE_ID,
    _PROMPT_TEMPLATE_VERSION,
    _REDACTION_POLICY_VERSION,
    _SNAPSHOT_BUILDER_VERSION,
    _availability,
    _entitlement_context,
    _no_data_snapshot,
    _optional_text,
    _run_context,
)
from frtb_result_store._ai_explanation_evidence import _collect_evidence
from frtb_result_store._ai_explanation_redaction import (
    _merge_redaction_reports,
    _prompt_injection_limitations,
    _redact_payload,
)
from frtb_result_store._ai_explanation_validation import (
    _validate_mode_constraints,
    _validated_navigator_state,
    _validated_target,
)

__all__ = ["StoreAIExplanationSnapshotMixin"]


class StoreAIExplanationSnapshotMixin:
    """Build bounded, evidence-linked AI explanation input snapshots."""

    def ai_explanation_snapshot(
        self: Any,
        run_id: str,
        request: Mapping[str, object],
    ) -> dict[str, object]:
        """Return a deterministic prompt input snapshot for Navigator commentary.

        Parameters
        ----------
        run_id : str
            Committed calculation run identifier.
        request : Mapping[str, object]
            Validated small request from Navigator state. The request selects a
            target and visible state; it must not contain hidden source rows or
            authoritative prompt payloads.

        Returns
        -------
        dict[str, object]
            Redacted, bounded, hashable explanation input snapshot.
        """

        if not self.run_exists(run_id):
            return _no_data_snapshot(run_id, request, "run_not_found", "run does not exist")
        run = self.get_run(run_id)
        if run is None:
            return _no_data_snapshot(run_id, request, "run_not_found", "run does not exist")

        navigator_state = _validated_navigator_state(run_id, request)
        target = _validated_target(navigator_state, request)
        _validate_mode_constraints(navigator_state, target)

        evidence = _collect_evidence(self, run_id, target, navigator_state, request)
        redacted_payload, redaction_report = _redact_payload(evidence["bounded_payload"])
        entitlement_context = _entitlement_context(request)
        redacted_entitlement_context, entitlement_redaction_report = _redact_payload(
            {"entitlement_context": entitlement_context}
        )
        redaction_report = _merge_redaction_reports(
            redaction_report,
            entitlement_redaction_report,
        )
        limitations: tuple[dict[str, object], ...] = tuple(
            cast(Sequence[dict[str, object]], evidence["limitations"])
        )
        prompt_flags = _prompt_injection_limitations(
            {
                "bounded_payload": redacted_payload,
                "navigator_state": navigator_state,
                "user_question": request.get("user_question"),
            }
        )
        if prompt_flags:
            limitations = (*limitations, *prompt_flags)
        availability = _availability(evidence, limitations)
        run_context = _run_context(run)
        entitlement_context_hash = stable_json_hash(redacted_entitlement_context)
        navigator_state_hash = stable_json_hash(navigator_state)
        snapshot_core: dict[str, object] = {
            "prompt_template_id": _PROMPT_TEMPLATE_ID,
            "prompt_template_version": _PROMPT_TEMPLATE_VERSION,
            "redaction_policy_version": _REDACTION_POLICY_VERSION,
            "entitlement_context_hash": entitlement_context_hash,
            "run_context": run_context,
            "navigator_state_hash": navigator_state_hash,
            "navigator_state": navigator_state,
            "target": target,
            "style": _optional_text(request.get("style")) or "risk_manager",
            "depth": _optional_text(request.get("depth")) or "standard",
            "user_question": _optional_text(request.get("user_question")),
            "evidence_refs": evidence["evidence_refs"],
            "bounded_payload": redacted_payload,
            "redaction_report": redaction_report,
            "availability": availability,
            "limitations": [
                *limitations,
                *cast(Sequence[dict[str, object]], redaction_report["limitations"]),
            ],
        }
        input_snapshot_hash = stable_json_hash(snapshot_core)
        return {
            "snapshot_id": f"ai-snapshot-{input_snapshot_hash[:16]}",
            "input_snapshot_hash": input_snapshot_hash,
            "snapshot_builder_version": _SNAPSHOT_BUILDER_VERSION,
            **snapshot_core,
        }
