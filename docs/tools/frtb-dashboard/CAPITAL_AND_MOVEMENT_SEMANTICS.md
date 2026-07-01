# Capital Navigator capital and movement semantics

Status: draft analytical contract for issue #1109.

Audience: Capital Navigator frontend/backend implementers, result-store adapter
authors, reviewers, and market-risk stakeholders who need stable display
semantics for capital, movement, hierarchy, contribution, and attribution.

Related:

- UX contract: [`UX_AUDIT_AND_INTERACTION_CONTRACT.md`](UX_AUDIT_AND_INTERACTION_CONTRACT.md)
- AI explanation contract: [`AI_EXPLANATION_CONTRACT.md`](AI_EXPLANATION_CONTRACT.md)
- Implementation slices: [`IMPLEMENTATION_SLICES.md`](IMPLEMENTATION_SLICES.md)
- Mode wireframes: [`MODE_WIREFRAMES.md`](MODE_WIREFRAMES.md)
- State and routing contract: [`NAVIGATOR_STATE_AND_ROUTING.md`](NAVIGATOR_STATE_AND_ROUTING.md)
- Result-store data contract: [`RESULT_STORE_DATA_CONTRACT.md`](RESULT_STORE_DATA_CONTRACT.md)
- Result-store public API: [`PUBLIC_API.md`](../../modules/frtb-result-store/PUBLIC_API.md)
- Orchestration API: [`PUBLIC_API.md`](../../modules/frtb-orchestration/PUBLIC_API.md)

This document defines what each capital and movement number means when rendered
by the Navigator. It is a display and adapter contract over committed
calculation evidence. It does not change capital calculations, create an
allocation methodology, or treat U.S. NPR 2.0 / Basel / EU CRR3 / PRA UK CRR
comparison outputs as final regulatory capital.

## Regulatory Anchors

The Navigator must display cited capital results without turning framework names
into regulatory justification:

- Standardised Approach capital is `SBM + DRC + RRAO`, consistent with BCBS
  d457 MAR20.4.
- SBM risk-class, bucket, measure, and scenario values are sensitivities-based
  method outputs governed by BCBS d457 MAR21.
- DRC issuer, bucket, JTD, LGD, hedge-benefit, and default-risk rows are DRC
  outputs governed by BCBS d457 MAR22.
- RRAO residual-risk add-on rows are residual-risk outputs governed by BCBS d457
  MAR23.
- IMA desk eligibility, expected shortfall, RFET/NMRF, SES, PLA, and
  backtesting states are IMA/model-evidence outputs governed by BCBS d457
  MAR31-MAR33.
- CVA rows are CVA-risk outputs governed by BCBS d457 MAR50 and the selected
  profile's CVA citation set.
- Output-floor percentages, phase-ins, and jurisdictional applicability must
  come from the selected profile or backend payload. The current Navigator
  fixture displays a `0.725` multiplier only when that value is explicitly
  supplied by the backend.

The UI may show these citations as evidence text or links. It must not infer a
regulatory rule from a display label, framework tab, or hierarchy node.

## Source of Truth

Every analytical amount shown as capital, movement, contribution, attribution,
eligibility, RFET, SES, PLA, source-row count, or official subtotal must be
supplied by the backend or `frtb-result-store`.

The browser may:

- format, sort, filter, hide, expand, and select rows;
- calculate visual percentages from supplied numerator and denominator values
  when the denominator is available and stable;
- group currently visible rows for exploration when the grouped value is clearly
  labelled `display-only`;
- route users to no-data, unsupported, residual, stale, partial, or synthetic
  states supplied by the backend.

The browser must not:

- recompute capital totals, subtotals, binding capital, floors, CVA, IMA, SA,
  SBM, DRC, RRAO, RFET, SES, PLA, or official source-row totals;
- allocate top-of-house capital to desks/books unless the allocation rows are
  supplied by the backend or result store;
- treat missing data as zero;
- treat a display-only grouping as an official subtotal;
- suppress unsupported or residual attribution because a numeric amount exists;
- infer freshness, restatement, final regulatory status, or no-exposure state
  without persisted evidence.

## Capital Amount Definitions

| Display amount | Meaning | Required source | UI rule |
| --- | --- | --- | --- |
| Binding capital | Capital amount that the backend marks as binding for the selected run and scope | `binding_total`, `binding_capital.binding_value`, or equivalent result-store measure | Emphasise one binding amount only; preserve `binding_side` or `bindingSource` |
| IMA capital | Current IMA capital for the selected run and scope | IMA summary, capital tree node, mart row, or scope view | Show eligibility/fallback state with the amount when available |
| SA capital | Standardised Approach total for the selected run and scope | Backend/result-store `SBM + DRC + RRAO` total | Do not compute from visible child rows unless the backend labels the row official |
| SBM capital | Sensitivities-based method component amount | SBM component summary, capital tree node, or mart row | Scenario selection applies only where backend supplies scenario values |
| DRC capital | Default Risk Charge component amount | DRC component summary, capital tree node, or mart row | Preserve issuer/bucket/default-risk lineage in drilldown |
| RRAO capital | Residual Risk Add-On component amount | RRAO component summary, capital tree node, or mart row | Label additive/residual-risk classification evidence explicitly |
| CVA capital | CVA-risk capital for the selected run and scope | CVA summary, CVA mart row, or explicit no-data/unsupported state | Show no-exposure only when the backend asserts no exposure |
| Output floor value | Profile-supplied floor multiplier times supplied SA amount | Backend floor payload with multiplier and SA basis | Explain multiplier, SA basis, floor value, and binding side together |
| Suite/display total | Top-level total shown by the Navigator for the selected scope | Suite/scope payload | If CVA is additive to binding market-risk capital, the payload must say so |
| Current amount | Amount for active `runId`, scope, framework, scenario, and row | Backend/result-store payload | Keep the run, scope, currency, and data state visible |
| Baseline amount | Amount for selected `baselineRunId` or baseline alias on the same semantic row | Movement payload or baseline result-store row | Do not substitute current amount when missing |
| Movement amount | `current - baseline` for the same semantic row when both values exist | Backend movement row or row payload | If computed by adapter, only use supplied current and baseline values for identical row IDs |
| Movement percent | `movement / abs(baseline)` when baseline is stable and non-zero | Backend movement row or adapter from supplied values | Suppress or mark unstable when baseline is near zero |
| Contribution to total | Current row amount as a share of the supplied official parent or total | Backend contribution field or supplied denominator | Label denominator: selected parent, scope, SA, IMA, CVA, or binding |
| Contribution to movement | Row movement as a share of supplied total movement | Backend contribution field or supplied movement denominator | Suppress when total movement is zero, near zero, or unavailable |

## Binding, Floor, and Suite Total Semantics

Binding view answers "which amount currently matters for this scope?"

Rules:

- `capitalView=binding` is not a framework. It is a view over supplied IMA, SA,
  CVA, floor, and binding-side evidence.
- The binding row must carry `binding_side` or `bindingSource`: `IMA`,
  `SA_FLOOR`, `CVA`, `output_floor`, or `NO_DATA`, depending on the backend
  contract.
- If the floor is displayed, show the supplied multiplier, supplied SA basis,
  floor value, and comparison amount. Do not recompute the floor in the browser.
- If IMA or SA is missing, the floor comparison is `NO_DATA` unless the backend
  supplies an explicit fallback state.
- CVA must be shown as a separate component/state. It may be part of a suite
  total only when the backend payload defines the additive relationship.
- A floor-driven movement can occur because SA moved, the floor multiplier or
  profile changed, IMA moved below/above the floor, or the backend restated the
  floor basis. The movement driver must name the supplied reason where present.

Examples:

- Top-of-house binding: IMA is `100`, SA is `150`, floor multiplier is `0.725`,
  floor value is `108.75`, and binding side is `SA_FLOOR`. Display binding
  capital `108.75`, show IMA and SA as comparators, and open the floor
  explanation from the floor row.
- IMA binding: IMA is `120`, SA is `150`, floor value is `108.75`, and binding
  side is `IMA`. Display binding capital `120`; do not call the floor "binding"
  even though it is visible.
- No-data floor: SA exists but IMA is unavailable. Show floor value only if the
  backend supplies it, but binding side must be `NO_DATA` or an explicit
  fallback state.

## Component Semantics

### Standardised Approach

SA is a composition label, not a standalone package. The Navigator may display
SA only from backend/result-store rows that already compose SBM, DRC, and RRAO.
Child component rows can explain SA, but visible child rows are not themselves
authority to restate the SA total.

Rules:

- Component contribution to SA must use the supplied SA denominator.
- SBM scenario controls affect SBM/SA rows only when scenario-specific values
  are supplied for the selected run, scope, and row.
- DRC issuer and bucket rows must reconcile through DRC backend/result-store
  evidence before they are used as official DRC subtotals.
- RRAO rows are additive residual-risk charges; they are not Euler
  contributions unless the backend explicitly supplies an analytical method.

### IMA

IMA capital is desk/model-evidence driven. Desk rows must keep capital terms
separate from eligibility evidence.

Rules:

- IMCC, SES, multiplier, fallback, PLA, backtesting, RFET, and NMRF values must
  come from IMA or result-store evidence.
- A desk can have capital and still be in a warning or fallback state. Do not
  hide model-evidence diagnostics because the capital number is non-null.
- Fallback movement is a model-governance movement, not a market-data movement,
  unless backend evidence classifies it otherwise.
- SES/NMRF amounts should be displayed as current capital terms or movements,
  not as source-row counts.

### CVA

CVA has a state before it has a grid. The first display decision is whether CVA
is calculated, no exposure, feed missing, unsupported, not in run, or synthetic
fixture-limited.

Rules:

- `0` means calculated zero only when the backend supplies a calculated CVA
  result or a positive no-exposure assertion.
- `NO_DATA` means no usable CVA payload for this scope/run. It is not zero.
- `UNSUPPORTED` means the selected profile, method, or data family is outside
  the implemented contract.
- CVA movement should distinguish exposure/profile movement, spread movement,
  hedge movement, and method/data-state movement only when those driver fields
  are supplied.

Example:

- A top-of-house run with no CVA payload should show CVA as `NO_DATA` with a
  reason such as `synthetic run does not include CVA`, not `0`.
- A legal entity with a backend assertion of no CVA exposures may show `0` with
  state `no exposure` and the supporting evidence reference.

## Hierarchy and Scope Semantics

Hierarchy changes the analytical scope. It is not a client-side filter over a
top-of-house total unless the backend explicitly labels the result
`display-only`.

| Scope level | Official amount rule | Display-only grouping rule |
| --- | --- | --- |
| Top of house | Use supplied top-of-house capital and movement rows | Never sum visible child rows to restate top-of-house |
| Legal entity | Use supplied legal-entity aggregate or result-store hierarchy aggregate | Visible desk/book grouping may help navigation but is not sign-off capital |
| Division/business line | Use supplied aggregate for that hierarchy node | Collapsed display rows must say `display-only` when not backend-backed |
| Desk | Use supplied desk capital, eligibility, and source evidence | Do not allocate legal-entity capital to desks locally |
| Book | Use supplied book capital/source evidence | Do not infer missing book capital from desk residual |

Rules:

- The selected `hierarchyNodeId`, `hierarchy_id`, and `version_id` must be
  preserved in URLs, cache keys, exports, and explanation snapshots.
- Parent and child rows may have mixed states. A parent can be `partial` even
  when some children are `ok`.
- A collapsed parent row must show whether its subtotal is official
  backend/result-store evidence or display-only grouping of visible children.
- Source-row samples under hierarchy nodes use their own `total_row_count` and
  `next_offset`; those counts must not be merged with artifact page counts.
- Legal entity, division, desk, and book examples must preserve the same run,
  baseline, currency, framework, and profile context as top-of-house.

Examples:

- Legal entity rollup: if result store returns an aggregate for `US_BANK_NA`,
  display it as official for that legal entity and show child desks as
  contributors.
- Desk rollup: if a desk has supplied IMA and SBM evidence but no CVA evidence,
  display IMA/SBM normally and CVA as `NO_DATA` or `UNSUPPORTED` with reason.
- Book grouping: if the user groups visible rows by book in a pivot before a
  backend subtotal exists, label the value `display-only grouped rows`.

## Movement and Baseline Semantics

Movement compares one semantic row in the current run to the corresponding
semantic row in the selected baseline. The comparison must preserve run,
hierarchy scope, framework, component, scenario, row identity, currency, and
profile basis.

Baseline types:

- previous official run;
- previous business day;
- month-end;
- quarter-end;
- year-on-year;
- custom run or window.

Movement states:

| State | Meaning | UI treatment |
| --- | --- | --- |
| `ok` | Current and baseline amounts exist for the same semantic row | Show current, baseline, absolute movement, and stable percent where allowed |
| `zero_movement` | Current and baseline exist and are equal within backend tolerance | Show zero movement, not no-data |
| `no_baseline` | No baseline run or row is available | Hide or disable movement columns and show reason |
| `new` | Current row exists and baseline row does not | Show current amount and `new`; percentage is unavailable |
| `dropped` | Baseline row exists and current row does not | Show baseline amount and `dropped`; current is unavailable |
| `restated_baseline` | Baseline run exists but has been restated | Label the baseline and include restatement evidence |
| `near_zero_baseline` | Baseline denominator is zero or below backend tolerance | Suppress percentage movement or mark it unstable |
| `currency_mismatch` | Current and baseline use different reporting basis | Do not compare until backend supplies converted basis |
| `profile_mismatch` | Current and baseline use incompatible regulatory/profile basis | Do not compare unless backend supplies a comparison row |

Rules:

- Column headers must name the baseline, such as `Movement vs prior run`.
- Absolute movement is signed: positive means current is greater than baseline.
- Percentage movement must use `abs(baseline)` as denominator when displayed.
- If the backend supplies a percentage movement, display that value and its
  basis instead of recalculating.
- Near-zero tolerance is backend-owned. Until supplied, the adapter should
  suppress percentage movement when baseline is exactly zero and avoid inventing
  a tolerance.
- Baseline restatements must stay visible in exports and AI explanations.
- A row can be new or dropped because the underlying business object changed,
  the hierarchy scope changed, the model path changed, or data is missing. Use
  supplied driver labels instead of guessing.

Examples:

- SA current `120`, baseline `100`: movement is `20`, percent is `20%`, and
  contribution to total movement depends on the supplied total movement
  denominator.
- DRC issuer current `5`, baseline `0`: show amount movement `5`, mark
  percentage `unstable` or unavailable.
- CVA baseline row exists but current CVA feed is missing: show `NO_DATA`
  current state, preserve baseline value, and classify movement as data-state
  unavailable rather than `-baseline`.

## Contribution Semantics

Contribution answers "how much of a supplied parent or movement does this row
explain?" It is not the same as attribution method.

Types:

- contribution to selected parent;
- contribution to top-of-house;
- contribution to SA;
- contribution to IMA;
- contribution to CVA;
- contribution to binding capital;
- contribution to total movement.

Rules:

- Every contribution field must name its denominator and denominator row ID.
- Contribution to total uses current amount and supplied current denominator.
- Contribution to movement uses movement amount and supplied movement
  denominator.
- Negative contributions are valid when a row offsets the parent or movement.
- Contribution percentages must be suppressed when the denominator is zero,
  near zero, no-data, unsupported, or display-only without a supplied basis.
- Ranking by contribution should use absolute value by default and preserve the
  signed value in the column.

Examples:

- Component contribution: SBM current `60` and SA current `100` gives `60%`
  contribution to SA if the backend identifies SA as the denominator.
- Movement contribution: DRC movement `-10` and total movement `20` gives
  `-50%`; show that DRC offset the increase rather than hiding the row.

## Attribution, Residual, and Unsupported Semantics

Attribution explains why an amount exists. Contribution ranks how much it
matters. They are related but not interchangeable.

Attribution methods:

- `ANALYTICAL` or equivalent: backend-supplied analytical contribution method;
- `STANDALONE`: row is presented as its own capital amount, not decomposed;
- `RESIDUAL`: unreconciled, non-homogeneous, or unsupported branch retained as
  a residual amount;
- `UNSUPPORTED`: exact attribution method is not implemented or not valid for
  the branch;
- `NO_DATA`: attribution payload is missing for this row.

Rules:

- Residual amounts must be rendered as residual. Do not allocate residual
  across children in the browser.
- Unsupported attribution must show the persisted `unsupported_reason`.
- Additive components such as RRAO may be shown as standalone/additive
  contribution but must not be labelled analytical Euler unless supplied.
- Floors, curvature branch choices, alternative SBM branches, fallback routes,
  and no-data CVA states may be valid capital results and unsupported for exact
  attribution at the same time.
- Inspector rows must preserve `attribution_id`, `target_type`, `target_id`,
  `source_level`, `source_id`, and `artifact_id` where supplied.

Example:

- A CVA unsupported-method row with an amount and `unsupported_reason` should
  appear in the capital grid and in diagnostics. The grid can rank the amount,
  but the inspector must say attribution is unsupported for the persisted
  reason.

## Additive and Non-Additive Rows

Rows need an explicit additivity state because some values are capital terms,
some are explanatory measures, and some are diagnostics.

| Additivity state | Meaning | Examples |
| --- | --- | --- |
| `additive_official` | Row contributes to an official backend/result-store subtotal | SA component rows supplied under SA total, CVA counterparty rows when backend-backed |
| `standalone_capital` | Row is a capital amount but not intended to sum with sibling rows | Binding capital, output floor value, selected scenario value |
| `display_group` | Browser or adapter grouped visible rows for exploration | Pivot grouping without backend subtotal |
| `diagnostic_measure` | Row explains state but is not capital | RFET count, PLA status, source warning count |
| `non_additive_comparator` | Comparator amount used for context | Baseline amount, floor comparator, scenario comparator |

Rules:

- Only `additive_official` rows may be summed for sign-off.
- `standalone_capital` rows may be ranked and selected but should not be added
  to siblings.
- Scenario values and floor comparators are non-additive unless the backend
  marks them as selected official amounts.
- Diagnostic measures must never be included in capital totals.

## Currency and Reporting Basis

Every capital and movement amount must carry a reporting basis.

Rules:

- Preserve `currency`, `base_currency`, profile ID, calculation date, and run ID
  wherever a number is exported, copied, explained, or linked.
- Do not compare current and baseline amounts across currencies unless the
  backend supplies converted amounts and conversion evidence.
- Source-row currencies may differ from reporting currency. The grid should show
  reporting currency for capital amounts and source currency in source-row
  drilldown.
- FX translation effects are movement drivers only when supplied by the backend.
- Percentage contribution is dimensionless but still inherits the denominator
  basis.

## State Taxonomy

The Navigator must distinguish these states:

| State | Meaning | Never render as |
| --- | --- | --- |
| `OK` | Complete value exists for the selected run/scope | Warning or no-data |
| `NO_DATA` | The run/scope explicitly lacks the value or payload | Zero |
| `UNSUPPORTED` | The value is outside implemented profile/method support | Zero or no-data |
| `STALE` | Persisted evidence exists but is older than the current run basis | Fresh value |
| `PARTIAL` | Some required child/evidence rows are missing | Complete value |
| `SYNTHETIC` | Fixture/development evidence | Production evidence |
| `RESIDUAL` | Amount is retained as residual rather than allocated | Analytical allocation |
| `RESTATED` | Baseline or current run was restated | Ordinary movement |
| `FILTERED` | User filters exclude rows | Missing source data |

## What the Dashboard Must Never Infer

The dashboard must never infer:

- official capital totals or official subtotals;
- output-floor multiplier, phase-in, jurisdictional applicability, or binding
  side;
- no-exposure CVA state;
- IMA eligibility, PLA, backtesting, RFET, NMRF, or SES status;
- source-row totals or completeness;
- issuer, risk-factor, desk, book, counterparty, or residual-risk
  classification;
- market-data, sensitivity, exposure, hedge, model-evidence, or source-data
  movement driver;
- restatement status;
- final regulatory-capital status for proposed-rule or comparison profiles.

When evidence is missing, the correct UI behavior is a visible unavailable,
unsupported, no-data, stale, partial, or residual state with a reason.

## Examples

### Top of House

Given a run with supplied IMA `120`, SA `150`, CVA `11`, floor multiplier
`0.725`, and floor value `108.75`, the binding market-risk amount is IMA if the
backend marks `binding_side=IMA`. If the suite payload defines CVA as additive,
the suite/display total can show `131` with CVA as a separate row. If the
backend does not define that additive relationship, show CVA separately and do
not calculate a suite total.

### Legal Entity

Given a legal entity aggregate supplied by result store, display that aggregate
as official for the selected legal entity. Desk rows below it explain the
aggregate only when they are supplied with compatible `hierarchy_id`,
`version_id`, run, baseline, currency, and denominator evidence. If a user
groups visible rows by division in the browser before a backend aggregate
exists, label the result display-only.

### Desk and Book

Given a rates desk with supplied IMA, SBM, RFET, and PLA evidence, display desk
capital and model state together. If book-level CVA is not supplied, show CVA
`NO_DATA` for that book rather than inheriting desk or top-of-house CVA.
Book-level contribution to desk capital requires a supplied desk denominator or
official allocation row.

### Standardised Approach

Given SA current `100`, SBM `60`, DRC `35`, and RRAO `5`, display those child
rows as official component contributors only when the backend supplies the SA
composition row. SBM scenario comparators can be shown for base/high/low, but
only the backend-selected scenario contributes to the official current amount.

### IMA

Given an IMA desk with IMCC `80`, SES `20`, and amber PLA state, show IMA
capital and model evidence in the same row. If the movement is driven by a PLA
fallback state supplied by the backend, classify it as model-governance
movement, not market-data movement.

### CVA

Given no CVA payload in a synthetic run, show CVA `NO_DATA` with the persisted
reason. Given a backend no-exposure assertion, show CVA `0` with state
`no exposure` and evidence reference. Given unsupported SA-CVA method evidence,
show `UNSUPPORTED` with the persisted reason even if BA-CVA rows exist.

## Acceptance Checklist

A Navigator implementation conforms to this contract when:

- every capital amount has a named source, run, scope, currency, and state;
- binding, floor, SA, IMA, CVA, and suite totals use backend/result-store
  values rather than browser recomputation;
- movement columns name the baseline and handle no-baseline, new, dropped,
  restated, and near-zero-baseline states explicitly;
- hierarchy totals identify official backend/result-store values versus
  display-only grouping;
- contribution fields name their denominator and suppress unstable percentages;
- residual and unsupported attribution remain visible with persisted reasons;
- CVA zero, no-data, no-exposure, and unsupported states are distinct;
- exports, copied findings, and AI explanations preserve the semantic IDs and
  data-state limitations that support the displayed numbers.
