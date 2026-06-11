# frtb-cva architecture and data design

## Design stance

`frtb-cva` follows the same suite pattern as `frtb-drc` and `frtb-sbm`: upstream
systems or adapters provide canonical inputs, the package applies deterministic
capital mechanics under a selected rule profile, and `frtb-orchestration`
consumes only package-level results.

```text
Upstream CVA / exposure / sensitivity systems
    -> counterparty, netting-set EAD/M/DF records (BA-CVA)
    -> portfolio-aggregate CVA and hedge sensitivities per risk factor k (SA-CVA)
    -> optional CRIF / vendor adapter
    -> canonical CvaCounterparty / CvaNettingSet / CvaHedge / SaCvaSensitivity
    -> frtb-cva validation, scope/method routing, rule-profile lookup
         -> ba_cva path (reduced / full)
         -> sa_cva path (weight -> aggregate -> risk classes)
    -> CvaCapitalResult + audit / replay records
    -> optional attribution and impact records
    -> frtb-orchestration top-of-house aggregation (separate from SA stack)
```

The package must not simulate discounted exposure paths, source market data,
produce accounting CVA, price trades, compose the SA stack
(`frtb-sbm + frtb-drc + frtb-rrao`), or prepare regulatory submissions.

See [DETAILED_REQUIREMENTS.md](DETAILED_REQUIREMENTS.md),
[DECISIONS_AND_PLAN.md](DECISIONS_AND_PLAN.md), and
[ADR 0003](../../decisions/0003-sa-drc-cva-scope.md).

## Input granularity

| Method | Input granularity | Regulatory anchor |
| --- | --- | --- |
| BA-CVA reduced / full | Counterparty and netting-set exposure rows | MAR50.14–MAR50.26 |
| SA-CVA | **Portfolio-aggregate** sensitivities per risk factor `k` | MAR50.47 |

SA-CVA sensitivities are not counterparty-level capital inputs. Upstream systems
must supply `s_k^CVA` and `s_k^Hdg` for the aggregate CVA portfolio and eligible
hedges. The capital package may sum multiple adapter rows that share the same
risk-factor key before weighting (see [DECISIONS_AND_PLAN.md](DECISIONS_AND_PLAN.md)).

## Implemented module layout

| Module | Responsibility |
| --- | --- |
| `data_models.py` | Frozen dataclasses and enums only. Canonical inputs, profile identity, intermediate and result records. |
| `validation.py` | Input normalisation, invariant checks, error types, supported/unsupported gates, deterministic ordering helpers. |
| `regimes.py` | Rule-profile identity, profile selection, supported-feature declarations, method policy hooks, profile hashing. |
| `reference_data.py` | BA-CVA risk weights, BA-CVA scalars, SA-CVA bucket/tenor/risk-weight/correlation tables, multiplier defaults, citation tables. |
| `scope.py` | Covered-transaction scope metadata, method selection, carve-out routing, materiality-threshold fail-closed gates. |
| `ba_cva.py` | Stand-alone counterparty capital, reduced portfolio aggregation, full BA-CVA hedge recognition and floor. |
| `hedges.py` | Eligible / ineligible hedge checks, internal/external transfer evidence, CCS vs RCS assignment validation. |
| `weighted_sensitivity.py` | CVA/HDG weighting, net weighted sensitivity, gross/net preservation. |
| `aggregation.py` | Shared SA-CVA intra-bucket and inter-bucket aggregation, hedging disallowance, multiplier application. |
| `sa_cva.py` | SA-CVA orchestration, delta/vega totals, risk-class assembly. |
| `risk_classes/girr.py` | GIRR-specific bucket, tenor, delta/vega factor handling. |
| `risk_classes/fx.py` | FX-specific currency-bucket and reporting-currency leg handling. |
| `risk_classes/ccs.py` | Counterparty credit spread delta handling; no CCS vega. |
| `risk_classes/rcs.py` | Reference credit spread delta and vega handling. |
| `risk_classes/equity.py` | Equity bucket, size/region/sector, qualified-index hooks. |
| `risk_classes/commodity.py` | Commodity bucket delta and vega handling. |
| `capital.py` | Public calculation entry point wiring validation, scope, profiles, BA/SA paths, mixed-method assembly. |
| `numeric.py` | Reconciliation helpers for supported capital and attribution paths. |
| `crif.py` | Optional CRIF/vendor-to-canonical mapping. No kernel imports. |
| `batch.py` | Public compatibility facade re-exporting canonical batch contracts and entrypoints. |
| `_batch_contracts.py` | Frozen batch dataclasses (`CvaCounterpartyBatch`, etc.). |
| `_batch_adapters.py`, `_batch_*_adapter.py` | Column and row adapters → canonical batches. |
| `_batch_validation.py` | Package-local batch input rules. |
| `_batch_assembly.py`, `_ba_*_batch_kernel.py`, `_sa_batch_kernel.py` | Kernel math and result assembly. |
| `_batch_payloads.py`, `_payloads.py` | Deterministic hash inputs via `stable_json_hash`. |
| `arrow_batch.py` | Arrow tabular handoff normalisation under ADR 0023. |
| `audit.py` | Deterministic result serialisation, input hash, profile hash, and reconciliation. |
| `attribution.py` | Additive attribution for supported branches with explicit unsupported nonlinear residuals. |
| `impact.py` | Baseline-vs-candidate finite-difference capital deltas. |

## Calculation flow

### Stage 1: Normalize and validate

1. Convert adapter output or caller records into canonical CVA records.
2. Validate identity fields, method/risk-class enums, sign convention, EAD,
   maturity, discount-factor inputs, sector/credit-quality/region fields,
   numeric finiteness, hedge eligibility evidence, and lineage.
3. Resolve the selected `CvaRuleProfile`.
4. Route method selection and carve-outs through `scope.py`.
5. Reject unsupported profile/method/risk-class combinations before capital math.

### Stage 2: Enrich with profile data

1. Resolve BA-CVA sector/credit-quality risk weights, α, ρ, β, and `D_BA-CVA`.
2. Resolve SA-CVA bucket metadata, risk weights, correlations, γ_bc, `R`, and
   `m_CVA`.
3. Attach citation ids to every rule-driven value.
4. For vega paths, resolve `RW_σ` and validate supplied `σ_k` inputs where
   required by the active profile.

### Stage 3: BA-CVA path

1. Calculate netting-set stand-alone capital `SCVA_c` using cited α, RW, M, EAD,
   and DF inputs.
2. Aggregate to counterparty stand-alone totals.
3. For reduced BA-CVA, apply MAR50.14 portfolio formula and `D_BA-CVA`.
4. For full BA-CVA, compute hedged capital with SNH, IH, HMA, and β floor.
5. Emit counterparty, netting-set, and BA-CVA total records in stable order.

### Stage 4: SA-CVA path

1. Group sensitivity rows by portfolio risk-factor key and sum to `s_k^CVA` and
   `s_k^Hdg` per factor.
2. Filter ineligible hedge contributions.
3. Calculate weighted sensitivities and net weighted sensitivity
   `WS_k = WS_k^CVA − WS_k^Hdg` under positive regulatory CVA convention.
4. Aggregate to bucket capital `K_b`, then risk-class capital with `m_CVA`.
5. Sum delta and vega risk-class totals into SA-CVA capital.

### Stage 5: Method assembly

1. For pure BA-CVA or pure SA-CVA runs, expose the selected method total only.
2. For mixed carve-out runs, combine SA-CVA and BA-CVA component totals without
   double-counting hedges or exposures.
3. Fail closed when carve-out evidence is incomplete.

### Stage 6: Audit and reconciliation

1. Compute deterministic input and profile hashes.
2. Reconcile netting-set lines to counterparty totals, buckets to risk classes,
   and risk classes to method totals.
3. Preserve stable ids from input through intermediate records to total result.
4. Record branch metadata for hedge floors, `S_b` floor/cap, rejected hedges,
   and unsupported paths.
5. Serialize deterministic audit records and return a frozen result.

### Stage 7: Attribution and impact

Attribution and impact helpers preserve the public capital number. Where an
exact analytical decomposition is not available for nonlinear branches such as
SA-CVA risk-class square roots or BA-CVA hedged capital, attribution reports an
explicit unsupported branch or residual rather than silently reallocating it.
This follows [ADR 0012](../../decisions/0012-capital-impact-attribution.md).

## Implemented enums

```python
class CvaMethod(StrEnum):
    BA_CVA_REDUCED = "BA_CVA_REDUCED"
    BA_CVA_FULL = "BA_CVA_FULL"
    SA_CVA = "SA_CVA"
    MIXED_CARVE_OUT = "MIXED_CARVE_OUT"

class SaCvaRiskClass(StrEnum):
    GIRR = "GIRR"
    FX = "FX"
    COUNTERPARTY_CREDIT_SPREAD = "COUNTERPARTY_CREDIT_SPREAD"
    REFERENCE_CREDIT_SPREAD = "REFERENCE_CREDIT_SPREAD"
    EQUITY = "EQUITY"
    COMMODITY = "COMMODITY"

class SaCvaRiskMeasure(StrEnum):
    DELTA = "DELTA"
    VEGA = "VEGA"

class SensitivityTag(StrEnum):
    CVA = "CVA"
    HDG = "HDG"

class CreditQuality(StrEnum):
    INVESTMENT_GRADE = "INVESTMENT_GRADE"
    HIGH_YIELD = "HIGH_YIELD"
    NOT_RATED = "NOT_RATED"

class CvaSector(StrEnum):
    SOVEREIGN = "SOVEREIGN"
    LOCAL_GOVERNMENT = "LOCAL_GOVERNMENT"
    FINANCIALS = "FINANCIALS"
    BASIC_MATERIALS_ENERGY_INDUSTRIALS = "BASIC_MATERIALS_ENERGY_INDUSTRIALS"
    CONSUMER_TRANSPORT_ADMIN = "CONSUMER_TRANSPORT_ADMIN"
    TECHNOLOGY_TELECOM = "TECHNOLOGY_TELECOM"
    HEALTH_UTILITIES_PROFESSIONAL = "HEALTH_UTILITIES_PROFESSIONAL"
    OTHER = "OTHER"

class BaCvaHedgeType(StrEnum):
    SINGLE_NAME_CDS = "SINGLE_NAME_CDS"
    SINGLE_NAME_CONTINGENT_CDS = "SINGLE_NAME_CONTINGENT_CDS"
    INDEX_CDS = "INDEX_CDS"

class HedgeEligibility(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    EXCLUDED = "EXCLUDED"

class HedgeReferenceRelation(StrEnum):
    DIRECT = "DIRECT"
    LEGAL_RELATION = "LEGAL_RELATION"
    SAME_SECTOR_AND_REGION = "SAME_SECTOR_AND_REGION"
```

The enum set is part of the public API. Future expansions for U.S., CRR3, or PRA
comparison profiles must update package tests, traceability docs, and the
requirements registry in the same PR.

## Implemented dataclasses

### Citation and lineage

```python
@dataclass(frozen=True)
class CvaCitation:
    source_id: str
    paragraph: str
    url: str
    note: str = ""

@dataclass(frozen=True)
class CvaSourceLineage:
    source_system: str
    source_file: str
    source_row_id: str
    source_column_map: Mapping[str, str] = field(default_factory=dict)
```

`CvaCitation` may later move to `frtb-common` under a cross-cutting ADR. Until
then, keep it package-local.

### Rule profile

```python
@dataclass(frozen=True)
class CvaRuleProfile:
    profile_id: str
    regulator: str
    version: str
    publication_date: date
    effective_date: date | None
    status: str
    supported_methods: frozenset[CvaMethod]
    supported_sa_cva_risk_classes: frozenset[SaCvaRiskClass]
    citations: Mapping[str, CvaCitation]
    content_hash: str
```

The profile owns identifiers and hashes. `reference_data.py` owns lookup tables
keyed by `profile_id`.

### Canonical counterparty

```python
@dataclass(frozen=True)
class CvaCounterparty:
    counterparty_id: str
    desk_id: str
    legal_entity: str
    sector: CvaSector
    credit_quality: CreditQuality
    region: str
    source_row_id: str
    lineage: CvaSourceLineage | None = None
```

`region` is required for BA-CVA indirect hedge eligibility under MAR50.19(3) and
Table 2 in MAR50.26.

### Canonical netting set

```python
@dataclass(frozen=True)
class CvaNettingSet:
    netting_set_id: str
    counterparty_id: str
    ead: float
    effective_maturity: float
    discount_factor: float
    currency: str
    sign_convention: str
    uses_imm_ead: bool
    carved_out_to_ba_cva: bool = False
    source_row_id: str
    lineage: CvaSourceLineage | None = None
```

For IMM banks, profile rules set `discount_factor = 1.0` (MAR50.15(4)). For
non-IMM banks, upstream systems may supply DF or the profile helper may compute
`DF = (1 - exp(-0.05 * M)) / (0.05 * M)`.

### Canonical SA-CVA sensitivity

```python
@dataclass(frozen=True)
class SaCvaSensitivity:
    sensitivity_id: str
    risk_class: SaCvaRiskClass
    risk_measure: SaCvaRiskMeasure
    sensitivity_tag: SensitivityTag
    bucket_id: str
    risk_factor_key: str
    tenor: str | None
    amount: float
    amount_currency: str
    sign_convention: str
    volatility_input: float | None = None
    source_row_id: str
    lineage: CvaSourceLineage | None = None
```

`sensitivity_tag = HDG` rows must carry eligible hedge evidence ids. Multiple
rows sharing the same portfolio risk-factor key are summed before weighting.

### Portfolio risk-factor key

```python
@dataclass(frozen=True)
class SaCvaRiskFactorKey:
    risk_class: SaCvaRiskClass
    risk_measure: SaCvaRiskMeasure
    bucket_id: str
    risk_factor_key: str
    tenor: str | None = None
```

The key must be deterministic and documented per risk class. CCS keys include
entity/id and tenor; RCS delta keys are bucket-wide; GIRR keys include currency
and tenor or parallel-curve flag.

### Result records

Public results should preserve, at minimum:

- `BaCvaNettingSetLine` with EAD, M, DF, α, RW, stand-alone contribution;
- `BaCvaCounterpartyCapital` with stand-alone and portfolio-allocation metadata;
- `SaCvaWeightedSensitivity` with gross CVA, gross hedge, net weighted values;
- `SaCvaBucketCapital` with `K_b`, `S_b`, floor/cap branch metadata;
- `SaCvaRiskClassCapital` with pre- and post-`m_CVA` totals;
- `CvaCapitalResult` with method, component totals, profile hash, input hash,
  citations, warnings, and unsupported-feature flags.

## Reconciliation rules

- BA-CVA: netting-set stand-alone lines sum to counterparty stand-alone; reduced
  portfolio total reconciles to MAR50.14 components.
- SA-CVA: weighted sensitivities reconcile to buckets; buckets reconcile to
  risk-class totals; delta and vega risk classes sum to SA-CVA total.
- Mixed method: component totals sum to reported total with explicit component
  ids; no hedge may appear in both BA and SA benefit paths.

## Package boundary checks

- No imports from sibling capital packages.
- Adapters must not be imported by kernels.
- Unsupported methods and risk classes fail before numeric capital is returned.
- Hedge benefit is never applied without explicit eligibility records.
