# frtb-rrao architecture and data design

## Design stance

`frtb-rrao` should follow the same broad pattern as `frtb-drc`: upstream systems
classify and source position-level risk attributes, the package applies
deterministic capital mechanics, and the suite orchestration layer consumes
package-level results.

```text
Upstream risk / trade / reporting systems
    -> residual-risk classification evidence and gross effective notional
    -> optional CRIF, FNet, or vendor adapter
    -> canonical RraoPosition records
    -> frtb-rrao validation, rule-profile lookup, classification, exclusions,
       capital kernels, and audit reconciliation
    -> RraoCapitalResult + deterministic serialized audit payload
    -> frtb-orchestration SA composition and suite aggregation
```

The package must not contain pricing, legal contract interpretation,
sensitivities calculation, SBM/DRC composition, market-data retrieval, or
top-of-house aggregation.

## Implemented module layout

| Module | Responsibility |
| --- | --- |
| `data_models.py` | Frozen dataclasses and enums only. No business logic. |
| `validation.py` | Input and result invariant checks, error types, and normalisation guards. |
| `regimes.py` | Rule-profile identity, supported-feature declarations, profile selection, and profile hashes. |
| `reference_data.py` | Classification labels, exclusion rules, risk weights, evidence categories, and citation tables. |
| `classification.py` | Pure classification and exclusion decision functions. |
| `capital.py` | Weighted notional line add-ons, subtotals, and total RRAO helpers. |
| `scaffold.py` | Public `calculate_rrao_capital` entry point, package metadata, supported-profile result assembly, and proposed-rule warnings. |
| `batch.py` | NumPy-backed batch validation, hashing, and calculation for high-volume canonical columns. |
| `arrow_handoff.py` | Arrow tabular handoff normalisation under ADR 0023; kernels remain outside the Arrow expression layer. |
| `audit.py` | Deterministic JSON-compatible serialization, profile/input hashes, and reconciliation. |
| `allocation.py` | Additive line, desk, legal-entity, and evidence-type allocation reports. |
| `crif.py` | Optional CRIF/FNet-to-canonical mapping. Not imported by kernels. |
| `fixtures.py` | Synthetic fixture builders used by tests and examples. |

This mirrors DRC's separation between `data_models.py`, validation, profile
lookup, calculation kernels, audit records, and adapters, while keeping RRAO's
classification and exclusion mechanics package-local.

## Calculation flow

### Stage 1: Normalise and validate

1. Convert adapter output or user records into `RraoPosition` objects.
2. Validate identity, gross effective notional, classification evidence,
   exclusion evidence, supervisor-directed inclusion, source lineage, numeric
   finiteness, and duplicate position ids.
3. Resolve the selected `RraoRuleProfile`.
4. Reject unsupported profile/feature combinations before numeric capital is
   computed.

### Stage 2: Classification and exclusion

1. Apply profile-supported classification rules to canonical evidence.
2. Resolve cited exclusions before assigning non-zero risk weights.
3. Preserve classification and exclusion reason codes for every position.
4. Emit deterministic rejected-input records for unsupported or invalid paths.

### Stage 3: Risk-weight lookup

1. Look up risk weights by profile id and classification result.
2. Attach citation ids to every risk-weight decision.
3. Treat excluded positions as successful zero-capital lines only when the
   exclusion is cited and auditable.

### Stage 4: Line capital

1. Calculate `gross_effective_notional * risk_weight` for every included line.
2. Store excluded lines separately with zero add-on and reason codes.
3. Preserve source row lineage, gross notional source, and citation ids.

### Stage 5: Subtotals and total capital

1. Aggregate deterministic subtotals by classification, evidence type, desk,
   and legal entity.
2. Sum included line add-ons into `RraoCapitalResult.total_rrao`.
3. Verify subtotals reconcile exactly to line add-ons.

### Stage 6: Audit and reconciliation

1. Compute profile and input hashes.
2. Verify line totals, subtotal totals, and result totals.
3. Serialize deterministic audit records.
4. Return a frozen result.

## Implemented enums

```python
class RraoClassification(StrEnum):
    EXOTIC = "EXOTIC"
    OTHER_RESIDUAL_RISK = "OTHER_RESIDUAL_RISK"
    SUPERVISOR_DIRECTED = "SUPERVISOR_DIRECTED"
    EXCLUDED = "EXCLUDED"
    UNSUPPORTED = "UNSUPPORTED"

class RraoEvidenceType(StrEnum):
    EXOTIC_UNDERLYING = "EXOTIC_UNDERLYING"
    GAP_RISK = "GAP_RISK"
    CORRELATION_RISK = "CORRELATION_RISK"
    BEHAVIOURAL_RISK = "BEHAVIOURAL_RISK"
    CTP_THREE_OR_MORE_UNDERLYINGS = "CTP_THREE_OR_MORE_UNDERLYINGS"
    NON_REPLICABLE_OPTIONALITY = "NON_REPLICABLE_OPTIONALITY"
    NO_MATURITY_OPTIONALITY = "NO_MATURITY_OPTIONALITY"
    NO_STRIKE_OR_BARRIER_OPTIONALITY = "NO_STRIKE_OR_BARRIER_OPTIONALITY"
    MULTIPLE_STRIKE_OR_BARRIER_OPTIONALITY = "MULTIPLE_STRIKE_OR_BARRIER_OPTIONALITY"
    INVESTMENT_FUND_EXPOSURE = "INVESTMENT_FUND_EXPOSURE"
    PATH_DEPENDENT_OPTION = "PATH_DEPENDENT_OPTION"
    FORWARD_START_UNDETERMINED_STRIKE_OPTION = "FORWARD_START_UNDETERMINED_STRIKE_OPTION"
    OPTION_ON_OPTION = "OPTION_ON_OPTION"
    DISCONTINUOUS_PAYOFF_OPTION = "DISCONTINUOUS_PAYOFF_OPTION"
    HOLDER_MODIFIABLE_OPTION = "HOLDER_MODIFIABLE_OPTION"
    FINITE_EXERCISE_DATES_OPTION = "FINITE_EXERCISE_DATES_OPTION"
    CROSS_CURRENCY_SETTLED_OPTION = "CROSS_CURRENCY_SETTLED_OPTION"
    MULTI_UNDERLYING_OPTION = "MULTI_UNDERLYING_OPTION"
    BEHAVIOURAL_OPTION = "BEHAVIOURAL_OPTION"
    SUPERVISOR_DIRECTIVE = "SUPERVISOR_DIRECTIVE"
    EXPLICIT_EXCLUSION = "EXPLICIT_EXCLUSION"

class RraoExclusionReason(StrEnum):
    LISTED = "LISTED"
    CCP_OR_QCCP_CLEARABLE = "CCP_OR_QCCP_CLEARABLE"
    TWO_OR_FEWER_UNDERLYINGS_NON_PATH_DEPENDENT_OPTION = (
        "TWO_OR_FEWER_UNDERLYINGS_NON_PATH_DEPENDENT_OPTION"
    )
    EXACT_THIRD_PARTY_BACK_TO_BACK = "EXACT_THIRD_PARTY_BACK_TO_BACK"
    DELIVERABLE_HEDGE_PAIR = "DELIVERABLE_HEDGE_PAIR"
    GOVERNMENT_OR_GSE_DEBT = "GOVERNMENT_OR_GSE_DEBT"
    FALLBACK_CAPITAL_REQUIREMENT = "FALLBACK_CAPITAL_REQUIREMENT"
    INTERNAL_DESK_TRANSACTION = "INTERNAL_DESK_TRANSACTION"
    AGENCY_DETERMINED_EXCLUSION = "AGENCY_DETERMINED_EXCLUSION"
    EU_ARTICLE_3_DELIVERABLE_RANGE = "EU_ARTICLE_3_DELIVERABLE_RANGE"
    EU_ARTICLE_3_RELATIVE_IMPLIED_VOLATILITY = "EU_ARTICLE_3_RELATIVE_IMPLIED_VOLATILITY"
    EU_ARTICLE_3_INDEX_OPTION_CORRELATION = "EU_ARTICLE_3_INDEX_OPTION_CORRELATION"
    EU_ARTICLE_3_CIU_INDEX_OPTION_CORRELATION = "EU_ARTICLE_3_CIU_INDEX_OPTION_CORRELATION"
    EU_ARTICLE_3_DIVIDEND_RISK = "EU_ARTICLE_3_DIVIDEND_RISK"
```

The enum set is now part of the v1 public API. Any future expansion for
additional Basel, U.S., CRR3, or PRA paths must update `PUBLIC_API.md`,
package-local tests, and the requirements registry in the same PR.

## Implemented dataclasses

### Citation and lineage

```python
@dataclass(frozen=True)
class RraoCitation:
    source_id: str
    paragraph: str
    url: str
    note: str = ""

@dataclass(frozen=True)
class RraoSourceLineage:
    source_system: str
    source_file: str
    source_row_id: str
    source_column_map: Mapping[str, str] = field(default_factory=dict)
```

`RraoCitation` may later move to `frtb-common` if multiple packages converge on
the same shape. Until then, keeping it package-local avoids a premature
cross-cutting change during RRAO implementation.

### Rule profile

```python
@dataclass(frozen=True)
class RraoRuleProfile:
    profile_id: str
    regulator: str
    version: str
    publication_date: date
    effective_date: date | None
    status: str
    supported_classifications: frozenset[RraoClassification]
    supported_exclusions: frozenset[RraoExclusionReason]
    citations: Mapping[str, RraoCitation]
    content_hash: str
```

The profile owns identifiers and hashes. `reference_data.py` owns the lookup
tables keyed by `profile_id`.

### Canonical position

```python
@dataclass(frozen=True)
class RraoPosition:
    position_id: str
    source_row_id: str
    desk_id: str
    legal_entity: str
    gross_effective_notional: float
    currency: str
    evidence_type: RraoEvidenceType
    evidence_label: str
    classification_hint: RraoClassification | None = None
    exclusion_reason: RraoExclusionReason | None = None
    exclusion_evidence_id: str | None = None
    back_to_back_match: RraoBackToBackMatch | None = None
    supervisor_directive_id: str | None = None
    underlying_count: int | None = None
    is_path_dependent: bool | None = None
    has_maturity: bool | None = None
    has_strike_or_barrier: bool | None = None
    has_multiple_strikes_or_barriers: bool | None = None
    is_ctp_hedge: bool = False
    is_investment_fund_exposure: bool = False
    investment_fund_descriptor: RraoInvestmentFundDescriptor | None = None
    notional_source: str = "reported"
    lineage: RraoSourceLineage | None = None
```

Required fields depend on evidence and exclusion paths. For example, exact
back-to-back exclusion requires both `exclusion_evidence_id` and a deterministic
`RraoBackToBackMatch` pair; supervisor-directed inclusion requires
`supervisor_directive_id`; U.S. NPR 2.0 investment-fund inclusion requires a
`RraoInvestmentFundDescriptor` proving the proposed section
`__.205(e)(3)(iii)` backstop-method linkage and the included exposure portion
used for proposed section `__.211(a)(3)`.

### Classification decision

```python
@dataclass(frozen=True)
class RraoClassificationDecision:
    position_id: str
    classification: RraoClassification
    evidence_type: RraoEvidenceType
    reason_code: str
    risk_weight_key: str
    citations: tuple[str, ...]
    exclusion_reason: RraoExclusionReason | None = None
    exclusion_evidence_id: str | None = None
    supervisor_directive_id: str | None = None
```

### Line contribution

```python
@dataclass(frozen=True)
class RraoCapitalLine:
    position_id: str
    classification: RraoClassification
    evidence_type: RraoEvidenceType
    gross_effective_notional: float
    risk_weight: float
    add_on: float
    currency: str
    is_excluded: bool
    reason_code: str
    citations: tuple[str, ...]
    desk_id: str = ""
    legal_entity: str = ""
    source_row_id: str = ""
    exclusion_reason: RraoExclusionReason | None = None
    exclusion_evidence_id: str | None = None
```

### Subtotal and result

```python
@dataclass(frozen=True)
class RraoSubtotal:
    subtotal_key: str
    subtotal_type: str
    gross_effective_notional: float
    add_on: float
    position_ids: tuple[str, ...]

@dataclass(frozen=True)
class RraoCapitalResult:
    run_id: str
    calculation_date: date
    base_currency: str
    profile_id: str
    profile_hash: str
    input_hash: str
    lines: tuple[RraoCapitalLine, ...]
    excluded_lines: tuple[RraoCapitalLine, ...]
    subtotals: tuple[RraoSubtotal, ...]
    total_rrao: float
    citations: tuple[str, ...]
    warnings: tuple[str, ...] = ()
```

The public audit serializer produces deterministic JSON-compatible payloads for
hashing, replay, and downstream reporting.

## Data invariants

- All result dataclasses are frozen.
- Public result records are JSON serialisable without custom object state.
- Inputs and outputs use stable ids, not object identities.
- All grouping keys are explicit strings or enums.
- A position has exactly one final classification decision.
- A supported included position has exactly one risk weight under the selected
  profile.
- Excluded positions have zero add-on and a cited exclusion reason.
- Gross effective notional is non-negative after adapter normalisation.
- Total RRAO reconciles exactly to included line add-ons within numeric
  tolerance.
- Subtotals are explain views and must reconcile to included and excluded line
  records.

## Unsupported feature strategy

Unsupported features should be declared at profile level and checked before
calculation. Examples:

- EU Article 325u investment-fund treatment not fully mapped;
- U.S. proposed section `__.211(a)(3)` investment-fund exposure missing
  required inputs;
- PRA profile not yet mapped;
- uncited supervisory inclusion;
- unrecognised residual-risk evidence type;
- exact back-to-back exclusion requested without deterministic pair evidence.

The package should raise an error for unsupported requested calculation paths.
It may return rejected-input audit records only when no capital result is being
presented as successful.

## Testing architecture

The test suite should mirror calculation layers:

- `test_data_models.py`: frozen behavior, enum normalisation, serialization.
- `test_validation.py`: missing fields, duplicate ids, notional finiteness,
  negative notional, evidence requirements, and structured error metadata.
- `test_reference_data.py`: cited classification labels, exclusions, risk
  weights, and profile support switches.
- `test_classification.py`: exotic, other residual risk, supervisor-directed,
  investment-fund, and unsupported decisions.
- `test_exclusions.py`: listed, clearable, plain option, back-to-back,
  deliverable hedge, government/GSE, fallback, internal desk, and
  agency-determined exclusions.
- `test_capital.py`: line add-ons, risk weights, subtotals, total
  reconciliation.
- `test_public_api.py`: end-to-end calculation and explicit unsupported
  profile behavior.
- `test_audit.py`: profile hash, input hash, deterministic ordering,
  serialization, and reconciliation tolerance.
- `test_crif.py`: optional adapter mapping without dataframe runtime
  dependency.
- `test_eu_profile.py`: EU Article 325u and Delegated Regulation (EU)
  2022/2328 comparison-profile fixtures.
- `test_external_comparator.py`: independent U.S. NPR and EU hand-calculation
  fixtures.
- `test_properties.py`: Hypothesis invariants for additivity, excluded-line
  idempotency, ordering, hashing, and partition disjointness.

## Example and validation artifacts

The implemented vertical slice includes a synthetic fixture pack:

```text
tests/fixtures/rrao_v1/
    positions.json
    profile.json
    expected_classification.json
    expected_lines.json
    expected_subtotals.json
    expected_result.json
```

Future validation notebooks can inspect this fixture with `pandas`, but the
runtime package must load fixture JSON into canonical dataclasses before
calculation.
