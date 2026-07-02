# FRTB Navigator AI explanation contract

Status: governed explanation snapshot contract; result-store snapshot builder implemented for issue #1104.

Audience: FRTB Navigator frontend/backend implementers, result-store
contributors, security reviewers, model-risk reviewers, and market-risk
stakeholders who need AI-assisted commentary to remain evidence-linked and
auditable.

Related:

- Parent split epic: #1106
- Result-store explanation snapshot builder: #1104
- UX contract:
  [`UX_AUDIT_AND_INTERACTION_CONTRACT.md`](UX_AUDIT_AND_INTERACTION_CONTRACT.md)
- State and routing contract:
  [`NAVIGATOR_STATE_AND_ROUTING.md`](NAVIGATOR_STATE_AND_ROUTING.md)
- Result-store data contract:
  [`RESULT_STORE_DATA_CONTRACT.md`](RESULT_STORE_DATA_CONTRACT.md)
- Capital and movement semantics:
  [`CAPITAL_AND_MOVEMENT_SEMANTICS.md`](CAPITAL_AND_MOVEMENT_SEMANTICS.md)
- Mode wireframes:
  [`MODE_WIREFRAMES.md`](MODE_WIREFRAMES.md)
- Implementation slices:
  [`IMPLEMENTATION_SLICES.md`](IMPLEMENTATION_SLICES.md)

This document defines the governed AI explanation feature as a contract over
bounded Navigator state and result-store evidence. It does not create model
credentials, implement a provider call, make AI output regulatory evidence, or
permit generated text to calculate or restate capital.

## Binding Rules

- AI explanation is commentary beside evidence, not a replacement for the grid,
  inspector, source rows, diagnostics, lineage, or package calculation records.
- The request must be created from `NavigatorState` plus a supported target type.
  Free text may refine the question, but it must not select hidden data.
- The browser must not assemble authoritative prompt payloads. It sends a small
  request; the server-side snapshot builder decides which bounded evidence may
  be used.
- Production text generation depends on a governed model-service adapter. The
  result-store #1104 builder supplies only bounded, evidence-linked input
  snapshots and does not call an external model provider.
- Every material factual claim in a generated response must cite at least one
  internal evidence reference supplied in the snapshot.
- Generated text must distinguish fact, inference, limitation, and next action.
- Generated text must not present U.S. NPR 2.0, Basel FRTB, EU CRR3, or PRA UK
  CRR comparison material as final regulatory capital.

## Trigger Points

The UI may expose explanation actions only where the selected state can map to a
bounded evidence snapshot.

| Trigger | Target type | Required selected state | Expected output |
| --- | --- | --- | --- |
| `Explain this view` in capital workbench | `view` | `runId`, `hierarchyNodeId`, `analysisMode`, visible aggregate rows | Top drivers, binding/floor state, limitations, and next actions |
| `Explain this panel` in inspector tab | `panel` | selected row/object plus `inspectorTab` | Panel-specific attribution, source, model, diagnostic, or lineage commentary |
| `Explain selected row` in grid | `row` | selected `rowId` and resolved drilldown target | Row-scoped capital/movement explanation |
| `Explain desk eligibility` | `desk` | selected `deskId`, `framework=IMA`, PLA/backtesting evidence where supplied | Eligibility, fallback, model-evidence, and capital consequence summary |
| `Explain risk factor` | `risk_factor` | selected `riskFactorId`, RFET/NMRF/SES evidence where supplied | Modellability, SES contribution, usage, and evidence gaps |
| `Explain source sample` | `source_rows` | selected row/object plus bounded source-row page | Source-data diagnostic commentary limited to the supplied sample |

Unsupported targets must be rendered as unavailable with a precise reason rather
than routed to a generic chatbot.

## Request Shape

The frontend request is intentionally small. It identifies the target and user
intent; it does not carry hidden datasets, raw artifacts, credentials, or prompt
instructions.

```yaml
AiExplanationRequest:
  request_id: string
  run_id: string
  navigator_state:
    run_id: string
    baseline_run_id: string | null
    hierarchy_node_id: string
    analysis_mode: capital | hierarchy | desk | pla | rfet_nmrf | risk_factor | pivot
    capital_view: binding | framework
    framework: SA | IMA | CVA | null
    scenario: Binding | Base | High | Low
    time_window: current | prior_run | prior_business_day | month_end | quarter_end | year_on_year | custom
    custom_window: object | null
    grid_mode: capital_stack | drivers | evidence | source_rows | eligibility | rfet_register | time_series | pivot
    row_id: string | null
    desk_id: string | null
    risk_factor_id: string | null
    artifact_id: string | null
    inspector_tab: summary | attribution | source | model | diagnostics | lineage | explanation
    filters: object
    sort: object
    pivot_rows: list[string]
    pivot_columns: list[string]
    column_preset: capital | movement | evidence | source | compact
  target:
    target_type: view | panel | row | desk | risk_factor | source_rows
    target_id: string
    target_label: string
    selected_drilldown_target: string | null
  style: executive_summary | risk_manager | model_validation | source_data_diagnostic | movement_outlier
  depth: short | standard | detailed
  user_question: string | null
  requested_by: string
  requested_at: datetime
```

Validation rules:

- `target_type=row` requires `row_id`.
- `target_type=desk` requires `desk_id`.
- `target_type=risk_factor` requires `risk_factor_id`.
- `target_type=source_rows` requires a bounded source page or source page
  parameters from the inspector state.
- `analysis_mode=pla` forces `framework=IMA` and `scenario=Binding`.
- `analysis_mode=rfet_nmrf` requires `framework=IMA`.
- A request with stale, incompatible, or missing selected state must fail closed
  before snapshot construction.

## Snapshot Builder Dependency

The production snapshot builder belongs in `frtb-result-store`. It turns the
validated request into a frozen, bounded, entitlement-filtered input snapshot.
The read-only API endpoint is `GET /runs/{run_id}/ai-explanation-snapshot`;
the endpoint computes a deterministic snapshot and hash but does not persist a
new result row or call a model provider.

```yaml
AiExplanationInputSnapshot:
  snapshot_id: string
  input_snapshot_hash: string
  prompt_template_id: string
  prompt_template_version: string
  entitlement_context_hash: string
  run_context:
    run_id: string
    run_group_id: string | null
    lifecycle_status: string
    profile_id: string
    currency: string
    generated_at: datetime
  navigator_state_hash: string
  navigator_state:
    baseline_run_id: string | null
    hierarchy_node_id: string
    analysis_mode: capital | hierarchy | desk | pla | rfet_nmrf | risk_factor | pivot
    capital_view: binding | framework
    framework: SA | IMA | CVA | null
    scenario: Binding | Base | High | Low
    time_window: current | prior_run | prior_business_day | month_end | quarter_end | year_on_year | custom
    custom_window: object | null
    grid_mode: capital_stack | drivers | evidence | source_rows | eligibility | rfet_register | time_series | pivot
    row_id: string | null
    desk_id: string | null
    risk_factor_id: string | null
    artifact_id: string | null
    selected_drilldown_target: string | null
    inspector_tab: summary | attribution | source | model | diagnostics | lineage | explanation
    filters: object
    sort: object
    pivot_rows: list[string]
    pivot_columns: list[string]
    column_preset: capital | movement | evidence | source | compact
  target:
    target_type: view | panel | row | desk | risk_factor | source_rows
    target_id: string
    target_label: string
  evidence_refs: list[AiEvidenceRef]
  bounded_payload:
    aggregate_rows: list[object]
    movement_rows: list[object]
    attribution_rows: list[object]
    diagnostics: list[object]
    lineage: list[object]
    source_row_samples: list[object]
    model_evidence: list[object]
  redaction_report:
    redacted_fields: list[string]
    omitted_evidence_refs: list[string]
    reason_codes: list[string]
  availability:
    state: AVAILABLE | NO_DATA | UNSUPPORTED | STALE | PARTIAL | SYNTHETIC
    message: string
```

The snapshot builder must:

- preserve stable run, node, row, source, artifact, attribution, desk, and
  risk-factor IDs;
- apply entitlement, redaction, and display-policy filters before model input is
  assembled;
- include explicit no-data, unsupported, stale, partial, and synthetic states;
- hash canonical JSON input after redaction so caching and audit are stable;
- reject requests that would require unbounded raw artifacts or hidden source
  fields;
- store prompt template ID and version with the snapshot.

## Data Boundary

Data that may be sent to the model service after entitlement filtering:

- selected run, baseline, hierarchy scope, mode, framework, scenario, and time
  window;
- visible aggregate rows and movement rows for the selected target;
- row-scoped attribution, residual, unsupported, diagnostic, and lineage
  records;
- bounded source-row samples already allowed for the user to view;
- model-evidence summaries such as PLA/backtesting/RFET/NMRF/SES states when
  supplied by result-store payloads;
- stable evidence identifiers and display labels needed for citations;
- explicit limitation, no-data, unsupported, stale, partial, and synthetic flags.

Data that must not be sent to the model service:

- credentials, tokens, API keys, session cookies, or object-store signed URLs;
- hidden entitlement fields, raw permission rules, or internal user directory
  data beyond a requestor/audit identifier;
- raw artifact files, full Parquet/CSV/JSON dumps, or unbounded source tables;
- proprietary source fields that are not visible in the Navigator view or
  allowed by the display policy;
- free-form browser-supplied prompt instructions that override system or
  developer governance;
- data from a different run, hierarchy scope, baseline, desk, risk factor, or
  row than the validated snapshot unless it is explicitly labelled comparison
  evidence.

## Evidence References

Every material claim must cite one or more evidence references from the input
snapshot. The model may not invent reference IDs.

```yaml
AiEvidenceRef:
  ref_id: string
  ref_type: run | node | grid_row | movement | attribution | diagnostic | lineage | source_row | artifact | desk | risk_factor | model_evidence
  run_id: string
  hierarchy_node_id: string | null
  target_id: string
  artifact_id: string | null
  source_id: string | null
  attribution_id: string | null
  risk_factor_id: string | null
  desk_id: string | null
  label: string
  data_state: AVAILABLE | NO_DATA | UNSUPPORTED | STALE | PARTIAL | SYNTHETIC
  citation_text: string
```

Evidence refs are internal product references, not legal or regulatory citations.
Regulatory citation text must still come from package/result-store metadata or
the capital/movement semantics contract.

## Prompt Template Versioning

Prompt templates are governed artifacts. Each template must have:

- `prompt_template_id`;
- semantic version;
- target types it supports;
- allowed style/depth combinations;
- required evidence sections;
- redaction policy version;
- output schema version;
- test fixture set and approval status.

Template changes that alter evidence requirements, refusal policy, output
classification, or regulatory caution are material governance changes and should
be reviewed separately from UI copy changes.

## Response Shape

The response is structured data rendered by the UI. The UI must not parse
free-form prose to recover findings or citations.

```yaml
AiExplanationResponse:
  explanation_id: string
  request_id: string
  run_id: string
  baseline_run_id: string | null
  hierarchy_node_id: string
  analysis_mode: string
  target:
    target_type: view | panel | row | desk | risk_factor | source_rows
    target_id: string
    target_label: string
  prompt_template_id: string
  prompt_template_version: string
  input_snapshot_hash: string
  output_hash: string
  model_id: string
  agent_profile: string
  requested_by: string
  requested_at: datetime
  generated_at: datetime
  status: complete | partial | refused | failed
  failure_code: string | null
  limitation_summary: string | null
  summary: object | null
    # Required when status is complete or partial; null for refused or failed.
    text: string
    evidence_refs: list[string]
  findings: list[object]
    # Required to contain at least one item when status is complete.
    - finding_id: string
      kind: fact | inference | limitation | next_action
      severity: info | watch | warning | critical
      claim: string
      rationale: string
      confidence: low | medium | high
      evidence_refs: list[string]
  limitations:
    - code: string
      message: string
      evidence_refs: list[string]
  next_actions:
    - action_id: string
      label: string
      reason: string
      evidence_refs: list[string]
  audit:
    redaction_report_hash: string
    snapshot_builder_version: string
    response_schema_version: string
```

Response validation rules:

- `complete` responses require at least one summary evidence reference and at
  least one finding.
- `partial` responses must begin with `limitation_summary`.
- `refused` responses must include `failure_code` or a limitation code and must
  not include unsupported analytical claims. `summary` may be null and
  `findings` may be empty.
- `failed` responses must include a stable `failure_code` suitable for UI
  display and audit. `summary` may be null and `findings` may be empty.
- Each `fact`, `inference`, and `next_action` finding must cite at least one
  supplied evidence ref unless it is a pure limitation about missing data.
- Inferences must be labelled as inferences and must not be rendered as facts.

## Caching and Regeneration

Explanation results may be cached only by:

- `input_snapshot_hash`;
- prompt template ID and version;
- output schema version;
- redaction policy version;
- entitlement context hash;
- target type and target ID.

The UI may reuse an explanation only when the current snapshot hash matches the
stored `input_snapshot_hash`. Changing run, baseline, scope, mode, framework,
scenario, selected object, server-side search, filters, pivots, visible row set,
source page, entitlement context, or prompt template version invalidates the
cached result.

Regeneration must record a new `explanation_id`, requester, timestamp, model ID,
output hash, and regeneration reason.

## Prompt Injection and Source-Data Controls

Source rows, diagnostics, labels, comments, and artifact text are untrusted input
to the model. The snapshot builder and prompt template must:

- wrap source-data text as quoted evidence, not as instructions;
- tell the model to ignore instructions embedded in source rows or labels;
- strip or escape executable markup, links, scripts, and object-store paths that
  are not display-safe;
- keep system/developer governance outside the user/source-data text block;
- refuse or downgrade output when evidence contains conflicting instructions,
  suspicious prompt text, or unsupported requests.

## Refusal and Failure UX

The UI should make refusal and failure states useful rather than silent.

| State | UI behavior |
| --- | --- |
| `NO_DATA` snapshot | Disable generation or return a limitation-first response explaining which evidence is missing. |
| `UNSUPPORTED` target | Disable the action and link to the relevant dependency, usually #1104 or a #1105 child issue. |
| `STALE` evidence | Allow generation only if stale status is included as the first limitation. |
| `PARTIAL` evidence | Allow generation only with `status=partial` and explicit omitted-evidence refs. |
| Entitlement redaction | Generate only from redacted evidence and show a redaction limitation. |
| Prompt-injection risk | Refuse or generate a limited source-data diagnostic without following embedded instructions. |
| Model/provider failure | Show stable failure code, keep evidence visible, and allow retry without changing state. |

## Audit Fields

Every generated or refused explanation must retain:

- `explanation_id`;
- request and response schema versions;
- `run_id`, `baseline_run_id`, `hierarchy_node_id`, `analysis_mode`, and target;
- `prompt_template_id` and version;
- `input_snapshot_hash` and `output_hash`;
- `model_id` and `agent_profile`;
- `requested_by`, `requested_at`, and `generated_at`;
- entitlement context hash and redaction report hash;
- status and limitation codes;
- evidence refs used by each material claim.

Copied or exported explanations must include run ID, timestamp, scope, baseline
where applicable, snapshot hash, and the label `AI-generated analytical
commentary`.

## Negative Tests and Refusal Scenarios

Implementation PRs for this feature should include at least these tests:

1. A row explanation request without `row_id` fails validation before snapshot
   construction.
2. A source-row explanation with an unbounded artifact or missing page limit is
   refused.
3. A response that makes a material claim without an evidence ref fails schema
   validation.
4. A source row containing prompt text such as "ignore previous instructions" is
   treated as quoted evidence and cannot change the prompt policy.
5. A user without entitlement to source rows receives a redacted snapshot and a
   limitation-first explanation.
6. A stale snapshot hash cannot be reused after run, baseline, scope, selected
   row, filter, pivot, visible row set, or prompt template version changes.
7. A request asking the model to calculate capital or override package results
   is refused.
8. A partial RFET/NMRF snapshot leads with missing-evidence limitations before
   any inference about SES drivers.
9. A model/provider timeout returns `status=failed` with a stable failure code
   and does not hide the underlying evidence panel.

## Acceptance Checklist

- Request and response shapes are explicit and structured.
- Model-service input and forbidden data classes are defined.
- Material claims require internal evidence IDs.
- Fact, inference, limitation, and next action are separate response kinds.
- Production snapshot construction is linked to #1104.
- Negative/refusal scenarios cover validation, evidence, entitlement,
  prompt-injection, stale-cache, and provider-failure paths.
