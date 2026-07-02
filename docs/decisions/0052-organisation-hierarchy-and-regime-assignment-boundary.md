# 52. Organisation hierarchy and regime assignment boundary

Date: 2026-07-01

## Status

Proposed

## Context

The FRTB Navigator and result store need to support business rollups such as
top of house, legal entities, business divisions, desks, Volcker desks, and
trading books. Different clients use different hierarchy shapes and labels:

```text
TOH -> Legal Entity -> Business Division -> Desk -> Trading Book
TOH -> Region -> Legal Entity -> Business Line -> Desk -> Book
TOH -> Management Unit -> Product Control Unit -> Volcker Desk -> Trading Book
TOH -> Desk -> Book
```

The repository already has flexible result-store hierarchy primitives:
`HierarchyDefinition`, `HierarchyLevel`, and `HierarchyNode`. Those support
client-defined level names, dimensions, ordering, leaf levels, generated
hierarchy nodes, and immutable per-run storage.

Two boundaries need to be explicit before richer hierarchy work continues:

1. **Business hierarchy is not the capital tree.** Business hierarchy answers
   "who owns the risk?" Capital tree answers "which regulatory capital
   component, risk class, bucket, or branch produced the number?"
2. **Business hierarchy is not regulatory regime assignment.** Organisation
   structure answers ownership and management rollup. Regime assignment answers
   which rule profile applies to a legal entity, scope, product set, or run.

Without an ADR, implementation could hard-code one bank's hierarchy, mix
capital-tree and organisation-tree concepts, or assume one hierarchy implies
one regulatory regime.

## Decision

`frtb-capital` will support a flexible, run-scoped organisation hierarchy model.

`TOH` / top of house is the canonical root rollup role for a committed view.
Everything below top of house is client-configured and stored in the committed
run's hierarchy definition.

The result store owns:

- the committed hierarchy definition used by a run;
- generated hierarchy nodes and paths;
- links from result/capital nodes to hierarchy leaf nodes or paths;
- read-only hierarchy exposure for the Navigator.

Packages may carry source dimensions such as `legal_entity`, `desk_id`,
`portfolio_id`, or `book_id`, but packages do not own enterprise organisation
hierarchy logic.

External organisation/reference-data platforms own:

- enterprise legal-entity, desk, book, business-line, Volcker-desk, and
  management hierarchy lifecycle;
- hierarchy approval and effective dating;
- desk/book ownership changes;
- entitlement mapping and user access policy;
- client-specific display labels outside committed run evidence.

The result store may expose hierarchy IDs, paths, and dimensions as entitlement
attributes for downstream access-control systems. It does not decide user
access.

Regulatory regime assignment is a separate run-scoped evidence problem. A legal
entity, desk, book, or scope may be assigned to a regime/profile independently
of its business hierarchy position.

## Core model

### 1. Flexible hierarchy definition

Each committed hierarchy definition has:

- `hierarchy_id`;
- `hierarchy_version`;
- `hierarchy_name`;
- ordered `levels`;
- one `leaf_level`;
- creation timestamp;
- metadata.

A run may expose multiple hierarchy definitions, such as management, legal,
risk-management, or product-control views. Any Navigator view or API query that
uses a hierarchy must name the active `hierarchy_id` and `hierarchy_version`, or
the result store must expose one explicit default hierarchy for that view.

Each level has:

- `level_name`, such as `legal_entity`, `business_division`, `desk`,
  `volcker_desk`, or `trading_book`;
- `dimension`, such as `legal_entity_id`, `business_division_id`, `desk_id`,
  or `book_id`;
- `level_order`.

`TOH` is mandatory as a conceptual root rollup role. It may be represented by a
configured root level such as `top_of_house`, `firm`, or `group`, or synthesized
by the result store for the committed view when the source hierarchy has no firm
row.

The committed hierarchy must identify top of house with concrete metadata:

- either `HierarchyDefinition.metadata["top_of_house_node_id"]` points to the
  root hierarchy node;
- or exactly one root `HierarchyNode.metadata["hierarchy_role"]` is
  `TOP_OF_HOUSE`.

Both forms may be present only if they identify the same node. More than one
`TOP_OF_HOUSE` node in a `(hierarchy_id, hierarchy_version)` is invalid.

No other level name is mandatory.

### 2. Hierarchy nodes and paths

Generated hierarchy nodes are immutable within a committed run and should carry:

- `hierarchy_id`;
- `hierarchy_version`;
- `hierarchy_node_id`;
- optional parent node id;
- level name and order;
- business key;
- display label;
- full path of `(level_name, business_key)` pairs;
- metadata.

Node ids must be deterministic for a given hierarchy version and path. If a
client changes the hierarchy shape, level ordering, level meaning, or path
membership, the run must use a new `hierarchy_version` or hierarchy hash.

### 3. Capital tree linkage

The organisation hierarchy must not replace the capital tree.

Capital tree examples:

- `SA`;
- `IMA`;
- `CVA`;
- `SBM`;
- `DRC`;
- `RRAO`;
- risk class;
- bucket;
- scenario branch;
- attribution/source line.

Organisation hierarchy examples:

- `TOH`;
- legal entity;
- region;
- business division;
- desk;
- Volcker desk;
- portfolio;
- trading book.

The result store links them. A capital node may be associated with a hierarchy
leaf node or hierarchy path, but the capital node identity remains regulatory
and component-oriented.

Hierarchy linkage is context, edge, or metadata. It must not become part of the
canonical regulatory capital node id. A hierarchy version change may change
hierarchy node ids while preserving the same capital node ids for the same
regulatory component/risk-class/bucket identity.

### 4. Regime assignment

Organisation hierarchy and regulatory regime assignment are separate.

```text
Organisation hierarchy: who owns the risk?
Regulatory regime: under which rule profile is it calculated?
```

A legal entity can belong to different regimes depending on jurisdiction,
reporting date, reporting basis, product scope, consolidation group, or
official/internal run purpose.

The model must not assume:

- one hierarchy equals one regime;
- one legal entity has one permanent regime;
- one business division maps to one regulatory profile;
- top-of-house rollup implies a single rule profile.

Current `CalculationRun` identity remains single-primary-regime:
`CalculationRun.regime_id` is part of the canonical run id. Mixed-regime
organisation views are therefore a result-store/Navigator view over linked runs
or run groups, or a future composite-run model defined by a later ADR. They are
not a single existing `CalculationRun` unless run identity is explicitly
changed by a later ADR.

Future run-scoped regime assignment evidence should include:

- `run_id`;
- organisation dimension key, such as `legal_entity_id`, `desk_id`, or
  `book_id`;
- optional `hierarchy_node_id`;
- `regime_id`;
- `profile_id` or package profile ids where needed;
- jurisdiction;
- reporting basis;
- effective date or snapshot timestamp;
- scope;
- source row id;
- assignment hash or source hash.

Regime assignment evidence is stored for audit and Navigator filtering. It does
not replace package profile controls or orchestration jurisdiction guards.

## Ownership

| Concept | Owner |
| --- | --- |
| Enterprise organisation master | external organisation/reference-data platform |
| Enterprise entitlement policy | external identity/access platform |
| Committed hierarchy definition and nodes | `frtb-result-store` |
| Regulatory top-of-house capital formulae and suite component aggregation | `frtb-orchestration` |
| Hierarchy-slice rollups over persisted results | `frtb-result-store` query/read model, when run policy permits |
| Package source dimensions such as `legal_entity` or `desk_id` | owning capital package input contracts |
| Legal-entity/regime assignment evidence | result store as run-scoped evidence; external platform as source of record |
| Package regulatory profile interpretation | owning package and orchestration guards |
| Navigator hierarchy rendering and filtering | FRTB Navigator |

## Design rules

### Rule 1: top of house is a role, not a hard-coded client tree

The committed view must identify a top-of-house root rollup. The display label
and configured root level may differ by client. Do not hard-code a universal
hierarchy below top of house.

The top-of-house role is identified by `top_of_house_node_id` or
`hierarchy_role=TOP_OF_HOUSE` metadata. It is a rollup/display role, not a
mandatory source-system level name.

### Rule 2: hierarchy levels are data/config driven

Levels below top of house are supplied by the run-scoped hierarchy definition.
The Navigator and result-store APIs must render level names dynamically rather
than assuming `legal_entity -> business_line -> desk -> book`.

### Rule 3: hierarchy versions are immutable per run

A committed run uses the hierarchy definition and hierarchy nodes captured at
commit time. If the organisation structure changes, a new `hierarchy_version`,
hash, or run-scoped reference is required.

Capital node ids must remain stable across hierarchy version changes when the
regulatory capital identity is unchanged. Hierarchy node ids and hierarchy paths
may change with the hierarchy version.

### Rule 4: packages do not own enterprise hierarchy

Capital packages may validate and carry source dimensions needed for lineage.
They must not hard-code client hierarchy rollups, generate organisation trees,
or infer business divisions from desk/book names.

### Rule 5: capital tree and organisation hierarchy stay separate

Do not encode regulatory component hierarchy as business hierarchy levels, and
do not encode business ownership levels as capital-node families. Link the two
through explicit hierarchy node/path references.

Those references must not be included in canonical capital node id generation.

### Rule 6: regime assignment is separate from hierarchy

Legal-entity or desk placement in a hierarchy does not determine regulatory
profile by itself. Regime/profile assignment must be explicit run-scoped
evidence or package/run context.

### Rule 7: mixed-regime rollups require explicit policy

Mixed-regime top-of-house or group views must not present a single regulatory
capital number unless an explicit consolidation/comparison policy defines what
is being shown. Otherwise the Navigator should show separate regime/profile
slices or linked runs.

### Rule 8: client-specific labels are display metadata

Client labels such as `FICC`, `Markets`, `Volcker Desk`, or `Trading Book` are
display/configuration metadata unless a package-specific regulatory profile
explicitly gives them calculation meaning.

### Rule 9: hierarchy dimensions can support entitlements but do not decide them

Hierarchy node ids, paths, and dimensions may be exposed to downstream
entitlement systems. `frtb-result-store` and package kernels must not decide
user access or row-level permissions.

## Examples

### In scope

- A hierarchy definition with levels
  `top_of_house -> legal_entity -> business_division -> desk -> trading_book`.
- A client-specific hierarchy with levels
  `group -> region -> legal_entity -> product_control_unit -> volcker_desk`.
- A run where legal entity `LE-US-BANK` is assigned `US_NPR_2_0` and
  `LE-EU-BANK` is assigned `EU_CRR3` for Navigator display and filtering.
- A capital node for `SBM GIRR delta` linked to a hierarchy leaf path ending in
  `desk=Rates`, `trading_book=USD-Swaps`.
- A top-of-house view that shows separate regime slices rather than combining
  incompatible regulatory profiles.

### Out of scope

- Building the enterprise organisation master.
- Managing desk/book lifecycle approvals.
- Managing Volcker designation governance.
- Inferring legal-entity regime from a desk name.
- Inferring business division from a book prefix.
- Collapsing mixed-regime legal-entity results into one scalar without an
  explicit policy.
- Using organisation hierarchy as a substitute for entitlements.

## Enforcement

| Rule | Enforcement |
| --- | --- |
| Hierarchy levels are flexible | Result-store tests with client-defined level sets |
| Top-of-house is role metadata | Fixture/API tests identify the root rollup role |
| Only one top-of-house node exists per hierarchy version | Result-store validation tests |
| Hierarchy versions are immutable per run | Store tests for stable node ids and versioned definitions |
| Capital node ids stay stable across hierarchy versions | Result-store graph tests |
| Capital tree and hierarchy stay separate | Model/API review and tests for explicit linkage |
| Packages do not own hierarchy rollups | Package-boundary review; no sibling imports or hierarchy builders in kernels |
| Regime assignment is explicit | Result-store/orchestration tests for run context and assignment evidence |
| Mixed-regime rollups are not silently combined | Orchestration and Navigator tests once mixed-regime views are implemented |
| Entitlement attributes are exposed but not enforced | API review and future entitlement integration tests |

## Consequences

**Positive:**

- Different clients can use different organisation hierarchies without code
  changes.
- Top-of-house aggregation is available without hard-coding one bank's
  structure.
- Legal-entity regime differences can be shown honestly without conflating
  ownership and regulatory profile.
- Capital tree navigation and business ownership slicing remain independent.
- Future entitlement and organisation-master integration has a clean boundary.

**Negative:**

- Result-store and Navigator code must render hierarchy levels dynamically.
- More run-scoped evidence is required to explain historical organisation and
  regime views.
- Mixed-regime top-of-house views need explicit policy before they can show a
  single number.

**Risks to guard against:**

- Hard-coding one hierarchy shape in UI or result-store queries.
- Treating `legal_entity` as synonymous with regulatory regime.
- Reusing capital-node families as business hierarchy levels.
- Letting packages infer business rollups from names.
- Showing a mixed-regime group total without clear comparison/consolidation
  semantics.

## Follow-up work

- Add explicit top-of-house role metadata to hierarchy definitions or nodes.
- Add a run-scoped entity/regime assignment artifact or reference contract.
- Add Navigator support for dynamic hierarchy level labels and paths.
- Add API/catalog support for hierarchy-driven filtering without hard-coded
  level names.
- Add tests for multiple client hierarchy shapes.
- Add tests or fixtures for legal entities assigned to different regimes within
  a linked run group or consolidated Navigator view.
- Define policy for mixed-regime top-of-house display before combining such
  results into one number.

## References

- [ADR 0022](0022-sa-jurisdiction-profile-consistency-guard.md): SA composition
  jurisdiction-family guard.
- [ADR 0039](0039-orchestration-suite-capital-aggregation.md): orchestration
  suite capital aggregation.
- [ADR 0049](0049-result-evidence-and-market-data-platform-boundary.md): result
  evidence and market data platform boundary.
- [ADR 0050](0050-risk-factor-identity-and-package-projection-boundary.md): risk
  factor identity and package projection boundary.
- [`docs/modules/frtb-result-store/FIRST_PASS_DESIGN.md`](../modules/frtb-result-store/FIRST_PASS_DESIGN.md):
  original result-store hierarchy and regime-comparison design notes.
- [`docs/modules/frtb-result-store/ISSUE_BREAKDOWN.md`](../modules/frtb-result-store/ISSUE_BREAKDOWN.md):
  result-store hierarchy issue breakdown.
