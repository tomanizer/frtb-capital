# frtb-drc architecture and data design

## Design stance

`frtb-drc` should follow the same broad pattern as `frtb-ima`: upstream systems
generate risk inputs, the package applies deterministic capital mechanics, and
the suite orchestration layer consumes package-level results.

```text
Upstream risk / trade systems
    -> issuer, tranche, notional, P&L, maturity, seniority, credit-quality data
    -> optional CRIF or vendor adapter
    -> canonical DrcPosition records
    -> frtb-drc validation, rule-profile lookup, and capital kernels
    -> DrcCapitalResult with attribution records
    -> optional impact records
    -> frtb-orchestration SA composition and suite aggregation
```

The package must not contain pricing, issuer mastering, market-data retrieval,
SA composition, or top-of-house aggregation.

## Proposed module layout

| Module | Responsibility |
| --- | --- |
| `data_models.py` | Frozen dataclasses and enums only. No business logic. |
| `validation.py` | Input and result invariant checks, error types, and normalisation guards. |
| `regimes.py` | Rule-profile identity, supported-feature declarations, profile selection, and profile hashes. |
| `reference_data.py` | LGD, bucket, seniority, credit-quality, maturity, risk-weight, and citation tables. |
| `gross_jtd.py` | Position-level gross JTD and default direction handling. |
| `maturity.py` | Maturity weighting, floors, and hedge maturity alignment helpers. |
| `netting.py` | Same-obligor, seniority-aware, maturity-weighted net JTD aggregation. |
| `capital.py` | HBR, bucket capital, category totals, and public calculation entry point. |
| `attribution.py` | Analytical Euler, residual, and unsupported attribution over the audited capital graph. |
| `impact.py` | Baseline-vs-candidate capital deltas for change-control reporting. Not part of the capital kernel. |
| `securitisation.py` | U.S. NPR 2.0 and Basel MAR22 securitisation non-CTP market-value gross default exposure, optional fair-value cap evidence, offsetting, HBR, bucket, and category capital paths. Unsupported profiles fail closed. |
| `ctp.py` | U.S. NPR 2.0 CTP market-value gross default exposure, replication-group netting, CTP-wide HBR, bucket recognition, and category capital path. Unsupported profiles fail closed. |
| `crif.py` | Optional CRIF-to-canonical mapping. Not imported by kernels. |
| `audit.py` | Serialisable audit records, profile/input hashes, result reconciliation, Markdown/JSON helpers. |
| `fixtures.py` | Synthetic fixture builders used by tests and examples. |

This mirrors IMA's separation between `data_models.py`, calculation kernels,
policy/regime choices, audit records, and examples while keeping DRC's issuer
and tranche mechanics package-local.

## Calculation flow

### Stage 1: Normalize and validate

1. Convert adapter output or user records into `DrcPosition` objects.
2. Validate identity, category, sign convention, maturity, seniority, credit
   quality, bucket inputs, numeric finiteness, and source lineage.
3. Resolve the selected `DrcRuleProfile`.
4. Reject unsupported category/profile combinations before any numeric capital
   is computed.

### Stage 2: Enrich with profile data

1. Assign LGD using profile rules or validate cited explicit LGD overrides.
2. Assign bucket and credit-quality keys.
3. Assign risk weights.
4. Attach source citation ids to each rule-derived value.

### Stage 3: Gross JTD

1. Calculate position-level gross JTD.
2. Preserve default direction, unscaled amount, LGD source, P&L/market-value
   component, and source row lineage.
3. Emit `GrossJtd` records in stable order.

### Stage 4: Maturity scaling and netting

1. Apply maturity weights and floors.
2. Build netting groups by category, bucket, obligor/tranche/index key, and
   eligible seniority layer.
3. Offset only where the profile permits it.
4. Emit `NetJtd` records and rejected-offset audit notes.

### Stage 5: Bucket and category capital

1. Compute HBR for each bucket.
2. Risk-weight net JTD records.
3. Apply bucket capital formula and floors.
4. Aggregate to category totals.
5. Sum category totals into `DrcCapitalResult` without cross-category
   diversification unless a profile explicitly cites another rule.

### Stage 6: Audit and reconciliation

1. Compute profile and input hashes.
2. Verify bucket totals sum to category totals and category totals sum to DRC
   total.
3. Preserve lineage from position id through gross JTD, scaled JTD, netting
   group, bucket, category, and total result.
4. Record branch metadata for floors, zero denominators, rejected offsets, and
   unsupported features.
5. Serialize deterministic audit records.
6. Return a frozen result.

### Stage 7: Attribution and impact

Attribution is implemented under
[ADR 0012](../../decisions/0012-capital-impact-attribution.md) and
[ADR 0031](../../decisions/0031-drc-attribution-method-contract.md). Impact
analysis follows the suite-wide `CapitalImpact` boundary from
[ADR 0038](../../decisions/0038-suite-wide-attribution-impact-contract.md).

1. Consume the capital result and audit graph.
2. Calculate analytical Euler contributions where the DRC formula is
   differentiable on the active branch.
3. Label branch-specific fallbacks, such as residual or unsupported
   attribution.
4. Reconcile contribution totals to total DRC without changing the capital
   number.
5. Report residuals explicitly when floors, caps, branch changes, or bucket
   moves prevent exact Euler reconciliation.
6. Compare compatible baseline and candidate `DrcCapitalResult` objects for
   change-control impact without mutating either capital result.
7. Label stable branch deltas as finite-difference impact, and label profile,
   bucket, category, floor, and unsupported branch changes separately from
   analytical contribution.

## Proposed enums

```python
class DrcRiskClass(StrEnum):
    NON_SECURITISATION = "NON_SECURITISATION"
    SECURITISATION_NON_CTP = "SECURITISATION_NON_CTP"
    CORRELATION_TRADING_PORTFOLIO = "CORRELATION_TRADING_PORTFOLIO"

class DefaultDirection(StrEnum):
    LONG = "LONG"    # issuer default creates a loss
    SHORT = "SHORT"  # issuer default creates a gain

class DrcInstrumentType(StrEnum):
    BOND = "BOND"
    EQUITY = "EQUITY"
    LOAN = "LOAN"
    CREDIT_DERIVATIVE = "CREDIT_DERIVATIVE"
    SECURITISATION_TRANCHE = "SECURITISATION_TRANCHE"
    INDEX_TRANCHE = "INDEX_TRANCHE"
    OTHER = "OTHER"

class DrcSeniority(StrEnum):
    EQUITY = "EQUITY"
    NON_SENIOR_DEBT = "NON_SENIOR_DEBT"
    SENIOR_DEBT = "SENIOR_DEBT"
    COVERED_BOND = "COVERED_BOND"
    GSE_GUARANTEED = "GSE_GUARANTEED"
    GSE_ISSUED_NOT_GUARANTEED = "GSE_ISSUED_NOT_GUARANTEED"
    PSE = "PSE"
    NOT_RECOVERY_LINKED = "NOT_RECOVERY_LINKED"

class CreditQuality(StrEnum):
    INVESTMENT_GRADE = "INVESTMENT_GRADE"
    SPECULATIVE_GRADE = "SPECULATIVE_GRADE"
    SUB_SPECULATIVE_GRADE = "SUB_SPECULATIVE_GRADE"
    DEFAULTED = "DEFAULTED"
    UNRATED = "UNRATED"

class DrcBucketType(StrEnum):
    NON_US_SOVEREIGN = "NON_US_SOVEREIGN"
    PSE_GSE = "PSE_GSE"
    CORPORATE = "CORPORATE"
    DEFAULTED = "DEFAULTED"
    SECURITISATION_ASSET_REGION = "SECURITISATION_ASSET_REGION"
    CTP = "CTP"
```

The exact enum set can expand as Basel, U.S., CRR3, and PRA profiles are mapped.
Enums should be stable public API once capital calculation is released.

## Proposed dataclasses

### Citation and lineage

```python
@dataclass(frozen=True)
class DrcCitation:
    source_id: str
    paragraph: str
    url: str
    note: str = ""

@dataclass(frozen=True)
class DrcSourceLineage:
    source_system: str
    source_file: str
    source_row_id: str
    source_column_map: Mapping[str, str] = field(default_factory=dict)
```

`DrcCitation` may later move to `frtb-common` if other packages need the same
shape. Until then, keeping it package-local avoids a premature cross-cutting
change during DRC implementation.

### Rule profile

```python
@dataclass(frozen=True)
class DrcRuleProfile:
    profile_id: str
    regulator: str
    version: str
    publication_date: date
    effective_date: date | None
    status: str
    supported_risk_classes: frozenset[DrcRiskClass]
    citations: Mapping[str, DrcCitation]
    content_hash: str
```

The profile owns identifiers and hashes. `reference_data.py` owns the actual
lookup tables keyed by `profile_id`.

### Canonical position

```python
@dataclass(frozen=True)
class DrcPosition:
    position_id: str
    desk_id: str
    legal_entity: str
    risk_class: DrcRiskClass
    instrument_type: DrcInstrumentType
    default_direction: DefaultDirection
    issuer_id: str | None
    tranche_id: str | None
    index_series_id: str | None
    bucket_key: str | None
    seniority: DrcSeniority | None
    credit_quality: CreditQuality | None
    notional: float
    market_value: float | None
    cumulative_pnl: float | None
    maturity_years: float
    currency: str
    lgd_override: float | None = None
    is_defaulted: bool = False
    is_gse: bool = False
    is_pse: bool = False
    is_covered_bond: bool = False
    lineage: DrcSourceLineage | None = None
```

Required fields depend on risk class. For example, non-securitisation requires
`issuer_id`; securitisation requires `tranche_id`; CTP requires enough
`index_series_id` and tranche metadata for decomposition.

### Securitisation tranche metadata

```python
@dataclass(frozen=True)
class SecuritisationTranche:
    tranche_id: str
    attachment_point: float
    detachment_point: float
    asset_class: str
    region: str
    is_cash_position: bool
```

This can be embedded in `DrcPosition` later or held in a separate keyed mapping.
The first implementation should keep non-securitisation independent and require
explicit tranche metadata only when securitisation paths are enabled.
Optional fair-value cap treatment is not embedded in tranche metadata. It is a
run-scoped `DrcFairValueCapEvidence` map keyed by position id so the source
profile, eligibility, cap amount, lineage, citations, and stale/validation
flags remain auditable and profile-controlled.

### Gross JTD

```python
@dataclass(frozen=True)
class GrossJtd:
    position_id: str
    risk_class: DrcRiskClass
    issuer_or_tranche_key: str
    bucket_key: str
    default_direction: DefaultDirection
    lgd_rate: float
    lgd_source: str
    notional: float
    pnl_component: float
    gross_jtd: float
    citations: tuple[str, ...]
```

### Maturity-scaled JTD

```python
@dataclass(frozen=True)
class MaturityScaledJtd:
    position_id: str
    gross_jtd: float
    maturity_years: float
    maturity_weight: float
    scaled_jtd: float
    floor_applied: bool
    citations: tuple[str, ...]
```

### Net JTD

```python
@dataclass(frozen=True)
class NetJtd:
    netting_group_id: str
    risk_class: DrcRiskClass
    bucket_key: str
    obligor_or_tranche_key: str
    seniority_layer: str
    gross_long: float
    gross_short: float
    scaled_long: float
    scaled_short: float
    net_amount: float
    net_direction: DefaultDirection
    position_ids: tuple[str, ...]
    rejected_offset_ids: tuple[str, ...] = ()
```

`gross_short` and `scaled_short` should be stored as positive magnitudes for
readability, while `net_direction` carries direction. Internal numeric kernels
may use signed arrays after validation.

### Hedge benefit and bucket capital

```python
@dataclass(frozen=True)
class HedgeBenefitRatio:
    bucket_key: str
    aggregate_net_long: float
    aggregate_net_short: float
    ratio: float
    citations: tuple[str, ...]

@dataclass(frozen=True)
class BucketDrc:
    bucket_key: str
    risk_class: DrcRiskClass
    hbr: HedgeBenefitRatio
    weighted_long: float
    weighted_short: float
    capital: float
    floor_applied: bool
    net_jtd_ids: tuple[str, ...]
    citations: tuple[str, ...]
```

### Category and run result

```python
@dataclass(frozen=True)
class CategoryDrc:
    risk_class: DrcRiskClass
    bucket_results: tuple[BucketDrc, ...]
    capital: float
    unsupported_features: tuple[str, ...] = ()

@dataclass(frozen=True)
class DrcCapitalResult:
    run_id: str
    calculation_date: date
    base_currency: str
    profile_id: str
    profile_hash: str
    input_hash: str
    categories: tuple[CategoryDrc, ...]
    total_drc: float
    citations: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    attribution_records: tuple[DrcCapitalContribution, ...] = ()
```

The public result should expose `as_dict()` for audit/reporting, following the
IMA package style.

### Attribution and impact records

DRC results emit `DrcCapitalContribution` records for analytical attribution.
`calculate_drc_impact` emits separate baseline-vs-candidate impact records over
two compatible capital results.

```python
class AttributionMethod(StrEnum):
    ANALYTICAL_EULER = "ANALYTICAL_EULER"
    RESIDUAL = "RESIDUAL"
    UNSUPPORTED = "UNSUPPORTED"

@dataclass(frozen=True)
class DrcCapitalContribution:
    contribution_id: str
    source_id: str
    source_level: str
    bucket_key: str | None
    category: DrcRiskClass
    base_amount: float
    marginal_multiplier: float | None
    contribution: float | None
    method: AttributionMethod
    residual: float = 0.0
    reason: str = ""

@dataclass(frozen=True)
class DrcImpactRecord:
    impact_id: str
    source_id: str
    source_level: str
    baseline_capital: float | None
    candidate_capital: float | None
    delta: float | None
    method: DrcImpactMethod
    reconciliation_status: ReconciliationStatus
    reason: str

@dataclass(frozen=True)
class DrcImpactAnalysis:
    total_impact: CapitalImpact
    records: tuple[DrcImpactRecord, ...]
    residual: float
    reconciliation_status: ReconciliationStatus
```

For non-securitisation DRC, analytical Euler is expected to be tractable for
bucket capital after netting because bucket DRC is a function of net long, net
short, risk-weighted net long, risk-weighted net short, and HBR. The
implementation must still handle branch cases explicitly: zero denominators,
bucket-level floors, offset rejection, maturity-scaling floors, and any change
that moves an exposure to a different bucket or category.

For CTP, attribution uses the CTP-wide HBR carried on each bucket and applies
the active positive/negative bucket recognition factor before reconciling to
category capital. For securitisation non-CTP, attribution uses the
bucket-local HBR and run-supplied risk-weight lineage.

## Data invariants

- All result dataclasses are frozen.
- Public result records are JSON serialisable without custom object state.
- Inputs and outputs use stable ids, not object identities.
- All grouping keys are explicit strings or enums.
- Intermediate records preserve enough lineage for later impact and
  attribution through stable joins: position id and source row lineage on
  inputs, gross/scaled/net JTD ids on intermediates, netting group id and bucket
  key on aggregation records, risk class on category records, and run id on the
  public capital result.
- A position has exactly one DRC risk class.
- A supported position has exactly one bucket under the selected profile.
- Direction is never inferred from notional sign alone.
- Maturity scaling is applied before netting where the profile requires it.
- HBR uses netted exposures, not raw position-level gross JTD.
- Category totals reconcile exactly to bucket totals within numeric tolerance.
- Total DRC reconciles exactly to category totals within numeric tolerance.
- Every attribution record must state its method and reconciliation residual.

## Unsupported feature strategy

Unsupported features should be declared at profile level and checked before
calculation. Current fail-closed examples:

- Basel securitisation non-CTP risk weights not mapped;
- Basel CTP decomposition not mapped;
- CRR3 securitisation non-CTP and CTP mappings missing;
- PRA UK CRR rulebook mappings missing;
- explicit LGD override not allowed by selected profile;
- unsupported product type or bucket assignment.

The package should raise an error for unsupported requested calculation paths.
It may return rejected-input audit records only when no capital result is being
presented as successful.

## Testing architecture

The test suite should mirror calculation layers:

- `test_drc_data_models.py`: frozen behavior, enum normalisation, serialization.
- `test_drc_validation.py`: missing fields, duplicate ids, sign convention, numeric
  finiteness.
- `test_drc_reference_data.py`: cited LGD, maturity, bucket, and risk-weight tables.
- `test_drc_gross_jtd.py`: long, short, defaulted, zero-LGD, credit derivative, call
  option, and invalid LGD paths.
- `test_drc_maturity.py`: below three months, below one year, one year or greater,
  derivative hedge maturity alignment.
- `test_drc_netting.py`: same obligor, rejected seniority, rejected cross-obligor,
  weighted long/short maturity cases.
- `test_drc_capital.py`: HBR, risk weighting, bucket floor, category total, total
  reconciliation.
- `test_drc_securitisation.py`: securitisation non-CTP gross JTD, exact-group
  netting, bucket capital, and fail-closed validation paths.
- `test_drc_ctp.py`: CTP gross JTD, replication-group netting, CTP category
  aggregation, and fail-closed validation paths.
- `test_drc_attribution.py`: analytical, residual, unsupported, row, batch,
  securitisation non-CTP, CTP, and reconciliation-failure attribution paths.
- `test_drc_impact.py`: stable bucket deltas, floors, profile changes,
  bucket/category moves, unsupported branches, metadata serialization, and
  unchanged capital totals during impact generation.
- `test_drc_arrow_batch.py`: Arrow batch normalization and batch parity for
  non-securitisation, securitisation non-CTP, and CTP inputs.
- `test_drc_audit.py`: profile hash, input hash, deterministic ordering,
  serialization.
- `test_drc_public_api.py` and `test_drc_replay.py`: public entrypoint behavior
  and deterministic audit replay.
- `test_drc_nonsec_fixture.py`, `test_drc_nonsec_v2_fixture.py`, and fixture
  packs under `tests/fixtures/`: committed synthetic validation fixtures.

Impact tests are package-local because impact records consume DRC branch
metadata and stable ids.

## Example and validation artifacts

The original non-securitisation vertical slice introduced a synthetic fixture
pack:

```text
tests/fixtures/drc_nonsec_v1/
    positions.json
    profile.json
    expected_gross_jtd.json
    expected_net_jtd.json
    expected_bucket_capital.json
    expected_result.json
```

Validation notebooks can inspect these fixtures with `pandas`, but the runtime
package must load fixture JSON into canonical dataclasses before calculation.
Current fixture coverage also includes securitisation non-CTP and CTP packs
under `packages/frtb-drc/tests/fixtures/`.
