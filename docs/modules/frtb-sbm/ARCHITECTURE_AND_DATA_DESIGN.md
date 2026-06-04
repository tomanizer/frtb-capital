# frtb-sbm architecture and data design

## Design stance

`frtb-sbm` should follow the same suite pattern as `frtb-drc`: upstream systems
or adapters provide canonical inputs, the package applies deterministic capital
mechanics under a selected rule profile, and `frtb-orchestration` consumes only
package-level results.

```text
Upstream risk / sensitivity systems
    -> CRIF / CSV / vendor adapters (optional)
    -> canonical SbmSensitivity records
    -> frtb-sbm validation, rule-profile lookup, and weighting kernels
    -> shared intra-bucket / inter-bucket aggregation engine
    -> risk-class capital by scenario + selected result
    -> SbmCapitalResult + audit / replay records
    -> optional attribution and impact records
    -> frtb-orchestration SA composition and suite aggregation
```

The package must not contain pricing, market-data sourcing, trade mastering,
SA composition, or regulatory submission packaging.

## Current module layout

| Module | Responsibility |
| --- | --- |
| `data_models.py` | Frozen dataclasses and enums only. Canonical sensitivities, profile identity, bucket/risk-class results, and audit-facing records. |
| `validation.py` | Input normalisation, invariant checks, error types, supported/unsupported gates, and deterministic ordering helpers. |
| `regimes.py` | Rule-profile identity, profile selection, supported-feature declarations, and profile hashing. |
| `reference_data.py` | Risk weights, buckets, tenor sets, liquidity horizons, intra-bucket and inter-bucket correlation tables, scenario definitions, and citation tables. |
| `weighted_sensitivity.py` | Canonical input enrichment, risk-weight lookup, vega scaling, and weighted sensitivity records. |
| `aggregation.py` | Shared intra-bucket and inter-bucket aggregation primitives, scenario evaluation, floors, and reconciliation helpers. |
| `risk_classes/girr.py` | GIRR-specific canonical fields, lookups, and assembly onto shared aggregation primitives. |
| `risk_classes/csr_nonsec.py` | CSR non-securitisation-specific assembly and validation. |
| `risk_classes/csr_sec_nonctp.py` | CSR securitisation non-CTP assembly and cited BASEL_MAR21 validation gates. |
| `risk_classes/csr_sec_ctp.py` | CSR securitisation CTP assembly and cited decomposition-evidence fail-closed gates. |
| `risk_classes/equity.py` | Equity-specific bucket, qualifier, and measure handling. |
| `risk_classes/commodity.py` | Commodity-specific bucket, location/tenor, and measure handling. |
| `risk_classes/fx.py` | FX-specific currency-bucket and base/reporting currency handling. |
| `curvature.py` | Curvature-specific up/down branch handling, floors, and result records. |
| `capital.py` | Public calculation entry point wiring validation, profiles, weighting, aggregation, scenario selection, and result assembly. |
| `crif.py` | Optional CRIF-to-canonical mapping. No kernel imports. |
| `audit.py` | Deterministic result serialization, input hash, profile hash, reconciliation, JSON/Markdown helpers. |
| `attribution.py` | Analytical Euler contribution support for selected differentiable delta/vega branches, with explicit unsupported residual records for curvature, active floors, alternative `S_b`, missing detail, and incomplete pairwise evidence. |
| `impact.py` | Baseline-vs-candidate finite-difference capital impact records. |
| `fixtures.py` | Synthetic fixture builders for tests and examples. |

## Calculation flow

### Stage 1: Normalize and validate

1. Convert adapter output or caller records into canonical `SbmSensitivity`
   objects.
2. Validate identity fields, risk class, risk measure, sign convention,
   currencies, required tenor fields, qualifier fields, numeric finiteness, and
   lineage.
3. Resolve the selected `SbmRuleProfile`.
4. Reject unsupported profile/risk-class/risk-measure combinations before any
   capital math begins.

### Stage 2: Enrich with profile data

1. Resolve bucket metadata and lookup keys.
2. Resolve risk weights, tenor sets, liquidity horizons, and correlation
   parameters.
3. Attach citation ids to every rule-driven value.
4. Preserve explicit reasons when a requested lookup is unsupported or missing.

### Stage 3: Weighted sensitivities

1. Calculate weighted sensitivities from canonical inputs and cited profile
   values.
2. Apply vega-specific scaling where prescribed.
3. Preserve raw amount, selected risk weight, scaling inputs, scaled amount, and
   lineage.
4. Emit weighted sensitivity records in stable order.

### Stage 4: Intra-bucket aggregation

1. Group weighted sensitivities by profile, risk class, risk measure, bucket,
   and required qualifier dimensions.
2. Apply the cited intra-bucket correlation structure.
3. Calculate signed bucket aggregate `Sb` where relevant.
4. Calculate bucket capital `Kb` and any profile-prescribed floors.
5. Preserve pairwise correlation evidence or an equivalent audit trace.

### Stage 5: Inter-bucket aggregation and scenario selection

1. Aggregate bucket outputs under low, medium, and high correlation scenarios
   where required.
2. Apply scenario-specific correlation adjustments from the active profile.
3. Produce risk-class capital totals per scenario.
4. Select the final risk-class capital according to the cited profile rule.
5. Preserve scenario-selection metadata and rejected-scenario notes where
   relevant.

### Stage 6: Curvature path

1. Validate curvature-specific up/down inputs or equivalent canonical shock
   fields.
2. Run curvature-specific weighting and aggregation rather than reusing delta or
   vega directly.
3. Apply curvature floors and worst-side or profile-prescribed branch logic.
4. Emit bucket-level and risk-class-level curvature records with branch
   metadata.

### Stage 7: Audit and replay

1. Compute deterministic input and profile hashes.
2. Reconcile weighted sensitivities to buckets, buckets to risk-class scenarios,
   and risk-class totals to total SBM.
3. Preserve stable ids from sensitivity through bucket, scenario, risk class,
   and total result.
4. Record branch metadata for floors, unsupported paths, scenario choice, and
   rejected inputs.
5. Serialize deterministic audit records and return a frozen result.

### Stage 8: Attribution and impact

1. Consume the audited capital graph.
2. Calculate analytical Euler contributions for selected differentiable delta
   and vega branches.
3. Report unsupported attribution explicitly when the formula is not
   differentiable on the active branch or required audit evidence was not
   retained.
4. Report baseline-vs-candidate impact as finite difference, not marginal
   contribution.
5. Reconcile contribution totals to bucket, risk-class, and total SBM where
   supported.

## Proposed enums

```python
class SbmRiskClass(StrEnum):
    GIRR = "GIRR"
    CSR_NONSEC = "CSR_NONSEC"
    CSR_SEC_CTP = "CSR_SEC_CTP"
    CSR_SEC_NONCTP = "CSR_SEC_NONCTP"
    EQUITY = "EQUITY"
    COMMODITY = "COMMODITY"
    FX = "FX"

class SbmRiskMeasure(StrEnum):
    DELTA = "DELTA"
    VEGA = "VEGA"
    CURVATURE = "CURVATURE"

class SbmScenarioLabel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class SbmSignConvention(StrEnum):
    PAY = "PAY"
    RECEIVE = "RECEIVE"
    LONG = "LONG"
    SHORT = "SHORT"

class SbmBucketType(StrEnum):
    GIRR = "GIRR"
    CSR = "CSR"
    EQUITY = "EQUITY"
    COMMODITY = "COMMODITY"
    FX = "FX"
```

The exact enum set can expand as Basel, U.S., and CRR3 profiles are mapped, but
public identifiers should become stable once capital calculation is released.

## Proposed dataclasses

### Citation and lineage

```python
@dataclass(frozen=True)
class SbmCitation:
    source_id: str
    location: str
    url: str
    note: str = ""

@dataclass(frozen=True)
class SbmSourceLineage:
    source_system: str
    source_file: str
    source_row_id: str
    source_column_map: tuple[tuple[str, str], ...] = field(default_factory=tuple)
```

### Rule profile

```python
@dataclass(frozen=True)
class SbmRuleProfile:
    profile_id: str
    regulator: str
    version: str
    publication_date: date
    effective_date: date | None
    supported_risk_classes: frozenset[SbmRiskClass]
    supported_measures: Mapping[SbmRiskClass, frozenset[SbmRiskMeasure]]
    citations: Mapping[str, SbmCitation]
    content_hash: str
```

The profile owns identity, supported-feature declarations, and citations.
`reference_data.py` owns the actual tables keyed by `profile_id`.

### Canonical sensitivity

```python
@dataclass(frozen=True)
class SbmSensitivity:
    sensitivity_id: str
    source_row_id: str
    desk_id: str
    legal_entity: str
    position_id: str | None
    risk_class: SbmRiskClass
    risk_measure: SbmRiskMeasure
    bucket: str
    qualifier: str | None
    risk_factor: str
    amount: float
    amount_currency: str
    tenor: str | None
    option_tenor: str | None
    maturity: str | None
    sign_convention: SbmSignConvention
    lineage: SbmSourceLineage
```

Risk-class-specific qualifier extensions may be modelled by extra optional
fields or subordinate package-local dataclasses, but the public contract should
remain canonical-first.

### Weighted sensitivity and bucket result

```python
@dataclass(frozen=True)
class WeightedSensitivity:
    sensitivity_id: str
    risk_class: SbmRiskClass
    risk_measure: SbmRiskMeasure
    bucket: str
    qualifier: str | None
    raw_amount: float
    risk_weight: float
    scaled_amount: float
    citation_ids: tuple[str, ...]

@dataclass(frozen=True)
class BucketCapital:
    bucket_id: str
    risk_class: SbmRiskClass
    risk_measure: SbmRiskMeasure
    scenario: SbmScenarioLabel | None
    sb: float | None
    kb: float
    floor_applied: bool
    weighted_sensitivities: tuple[WeightedSensitivity, ...]
    citation_ids: tuple[str, ...]
```

### Risk-class and run result

```python
@dataclass(frozen=True)
class RiskClassCapital:
    risk_class: SbmRiskClass
    risk_measure: SbmRiskMeasure | None
    scenario_totals: Mapping[SbmScenarioLabel, float]
    selected_scenario: SbmScenarioLabel | None
    selected_capital: float
    buckets: tuple[BucketCapital, ...]
    citation_ids: tuple[str, ...]

@dataclass(frozen=True)
class SbmCapitalResult:
    total_capital: float
    risk_classes: tuple[RiskClassCapital, ...]
    profile_id: str
    profile_hash: str
    input_hash: str
    warnings: tuple[str, ...]
    unsupported_flags: tuple[str, ...]
```

### Curvature-specific records

```python
@dataclass(frozen=True)
class CurvatureInput:
    sensitivity_id: str
    bucket: str
    up_shock_amount: float
    down_shock_amount: float
    citation_ids: tuple[str, ...]

@dataclass(frozen=True)
class CurvatureResult:
    bucket_id: str
    selected_branch: str
    bucket_capital: float
    floor_applied: bool
    citation_ids: tuple[str, ...]
```

## Data invariants

- `sensitivity_id` is unique within a run unless an adapter explicitly performs
  a documented pre-aggregation step.
- Every rule-driven lookup resolves through the selected profile and has at
  least one citation id.
- Unsupported profile/risk-class/risk-measure combinations fail before numeric
  aggregation.
- Bucket and scenario outputs are deterministic for the same ordered canonical
  inputs.
- Result records reconcile bottom-up from weighted sensitivities to total SBM.
- Audit serialization preserves stable ordering and stable ids.

## Unsupported feature strategy

Unsupported paths should fail at the narrowest possible boundary with explicit
errors such as:

- unsupported profile;
- unsupported risk class;
- unsupported risk measure;
- incomplete curvature inputs;
- missing bucket mapping;
- missing risk weight;
- unsupported adapter convention.

The package must never return placeholder bucket, scenario, or total capital.

## Testing architecture

Tests are separated by layer:

- `tests/test_data_models.py` and `tests/test_validation.py` for canonical
  contracts and invariant checks;
- `tests/test_regimes.py` and `tests/test_reference_data.py` for cited profile
  lookup and hashes;
- `tests/test_weighted_sensitivity.py` for risk weights and vega scaling;
- `tests/test_aggregation.py` for shared intra/inter-bucket mechanics and
  scenario selection;
- risk-class-specific tests under `tests/risk_classes/`;
- `tests/test_curvature.py` for curvature-specific branches and floors;
- `tests/test_audit.py` and `tests/test_replay.py` for hashes and
  serialization;
- `tests/test_sbm_unsupported_features.py` for explicit fail-closed behavior.

## Example and validation artifacts

Synthetic fixture packs now cover the supported BASEL_MAR21 delta and vega
paths used by the package tests, with curvature parity covered by dedicated
row/batch/Arrow tests. Negative cases cover missing mappings, unsupported
sub-features, duplicate sensitivity ids, and incomplete curvature inputs. Audit
and replay tests assert deterministic input hashes, profile hashes, bucket
results, scenario totals, and total SBM reconciliation.
