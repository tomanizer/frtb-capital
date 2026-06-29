# Client ingestion workflow

This guide describes the v1 workflow for mapping client risk-system exports into
canonical `frtb-ima` tabular handoff objects before RFET, PLA/backtesting,
scenario P&L, ES/IMCC, and NMRF/SES validation or capital assembly.

The workflow is intentionally small. It has one human-authored artifact,
`mapping.yaml`, and generated evidence artifacts that can be attached to an
onboarding record or validation pack.

```text
client exports
  -> profile.json
  -> mapping_suggestion_report.json
  -> human-reviewed mapping.yaml
  -> canonical IMA tabular batches
  -> validation_report.json
  -> IMA validation and NumPy-native kernels
```

Do not treat this as a production regulatory submission workflow. The package is
a transparent prototype, uses proposed-rule comparison material, and does not
source market data, price trades, approve risk-factor taxonomy, or generate
upstream NMRF valuation artifacts.

## Artifacts

| Artifact | Author | Purpose |
| --- | --- | --- |
| `profile.json` | Generated | Schema discovery for a client export: columns, inferred types, null rates, cardinalities, examples, ranges, row count, and source hash. |
| `mapping_suggestion_report.json` | Generated | Deterministic candidate source-column rankings for supported canonical IMA targets. It is advisory only and records `human_review_required: true`. |
| `mapping.yaml` | Human | Explicit source-to-canonical mapping reviewed by the onboarding team. This is the only v1 authored mapping artifact. |
| Canonical tabular batches | Generated | Package-owned normalized handoff objects for daily P&L, scenario P&L, RFET observations, and risk-factor master rows. |
| `validation_report.json` | Generated | Aggregated row counts, rejects, findings, source hashes, mapping hash, and report hash for mapped tables. |

Do not introduce a multi-file mapping pack for v1. If a real onboarding needs
aliases, controls, or manifest detail, put them in `mapping.yaml` or
`validation_report.json` first and split them later only when repeated client
work proves the need.

## Supported canonical targets

The mapping workflow targets existing canonical handoff contracts. It must not
add client-specific logic to capital kernels.

| `mapping.yaml` table key | Canonical target | Main downstream use |
| --- | --- | --- |
| `daily_pnl_vectors` | `ima_daily_pnl_vectors` | PLA and backtesting APL/HPL/RTPL/VaR vectors. |
| `scenario_pnl_vectors` | `ima_scenario_pnl_vectors` | Scenario P&L rows materialized through the canonical table path before cube construction. |
| `risk_factor_master` | `ima_risk_factor_master` | Risk class and liquidity-horizon reconciliation for scenario P&L and RFET inputs. |
| `rfet_observations` | `ima_rfet_observations` | Real-price observation evidence for RFET assessment. |

Scenario cubes, stress histories, and NMRF upstream valuation outputs remain
NumPy-native runtime artifacts. Arrow/tabular handoff is used for ingestion,
normalization, audit lineage, and row-level validation; kernels remain
NumPy-native and must not import Arrow, pandas, polars, or client adapters.

## Step 1: profile source exports

Use `profile_source_rows(...)` when a notebook or intake script has already read
rows, or `profile_csv_source(...)` for a simple CSV file. Profiling does not
require a mapping spec.

```python
from pathlib import Path

from frtb_ima.adapters import profile_csv_source

profile = profile_csv_source("client_daily_pnl.csv")
Path("profile.json").write_text(profile.to_json(), encoding="utf-8")
```

Review `profile.json` for unexpected columns, high null rates, type inference
that conflicts with the client data dictionary, and source hashes that should be
recorded in onboarding evidence.

## Step 2: generate mapping suggestions

Generate suggestions from one or more profiles. Suggestions are deterministic
rankings, not an executable mapping spec.

```python
from pathlib import Path

from frtb_ima.adapters import build_ima_mapping_suggestion_report

suggestions = build_ima_mapping_suggestion_report(
    {"ima_daily_pnl_vectors": profile},
    target_schema="ima-arrow-v1",
    source_system="client_risk_engine",
)
Path("mapping_suggestion_report.json").write_text(
    suggestions.to_json(), encoding="utf-8"
)
```

A single profile can be scored against multiple targets during exploration:

```python
suggestions = build_ima_mapping_suggestion_report(
    {"default": profile},
    target_schema="ima-arrow-v1",
    source_system="client_risk_engine",
    targets=("ima_rfet_observations", "ima_risk_factor_master"),
)
```

The report highlights missing required target fields. A missing required field
means the client export is insufficient until the mapping author supplies a
valid source column, a safe constant where supported, or a revised upstream
extract.

## Step 3: author `mapping.yaml`

`mapping.yaml` is explicit and reviewable. Every required target field must map
to either a source column or an allowed constant.

```yaml
mapping_spec_version: 1
target_schema: ima-arrow-v1
source_system: client_risk_engine
base_currency: USD
timezone: America/New_York
sign_convention:
  pnl_positive_means: profit
tables:
  daily_pnl_vectors:
    source: client_daily_pnl.csv
    target: ima_daily_pnl_vectors
    fields:
      desk_id: DESK
      business_date: COB_DATE
      apl: ACTUAL_PNL
      hpl: HYPOTHETICAL_PNL
      rtpl: RISK_THEORETICAL_PNL
      var_975: VAR_975
      var_99: VAR_99
      source_row_id: SOURCE_ROW_ID
```

Sign convention is mandatory for P&L vectors. Do not infer it from column names.
If the client exports losses as positive values, set the mapping spec
accordingly and verify the resulting validation report before feeding PLA,
backtesting, ES, or IMCC workflows.

## Step 4: materialize canonical batches

Load the reviewed mapping spec and materialize the canonical target. The mapper
returns accepted rows plus a table-level validation report.

```python
from pathlib import Path

from frtb_ima.adapters.mapping_spec import load_ima_mapping_spec
from frtb_ima.adapters.daily_pnl_mapping import materialize_daily_pnl_vectors_from_mapping

spec = load_ima_mapping_spec("mapping.yaml")
result = materialize_daily_pnl_vectors_from_mapping(
    spec,
    source_rows,
    source_file="client_daily_pnl.csv",
)
Path("daily_pnl_validation_report.json").write_text(
    result.report.to_json() if hasattr(result.report, "to_json") else "",
    encoding="utf-8",
)
```

For scenario P&L, prefer providing `risk_factor_master` in the same mapping spec
or as an already materialized batch. This lets the mapper reconcile scenario
risk factors to master-data liquidity horizons and reject conflicting metadata
before cube construction.

Scenario P&L missing-cell behavior defaults to `reject`. Use
`missing_cells: zero` only when the upstream extract explicitly distinguishes a
true zero P&L from an absent row and the decision is documented in the mapping
review.

## Step 5: aggregate validation evidence

After each table mapper has run, aggregate table reports into one
`validation_report.json`.

```python
from pathlib import Path

from frtb_ima.adapters import build_ima_mapping_validation_report

validation = build_ima_mapping_validation_report(
    {
        "ima_daily_pnl_vectors": daily_result.report,
        "ima_scenario_pnl_vectors": scenario_result.report,
    }
)
Path("validation_report.json").write_text(validation.to_json(), encoding="utf-8")
```

The aggregate report records source hashes, one mapping hash, row counts,
reject counts, findings, and a deterministic report hash. Store it with the
profile and mapping spec used for the run.

## Notebook workflow

A notebook should keep the same review order as the artifact flow:

1. Load source exports and generate `profile.json`.
2. Inspect type inference, null rates, examples, and row counts.
3. Generate `mapping_suggestion_report.json` and inspect missing required fields.
4. Author or update `mapping.yaml` outside the notebook so it is reviewable.
5. Parse `mapping.yaml` and materialize each canonical target.
6. Review table reports and aggregate `validation_report.json`.
7. Feed accepted canonical batches to existing validation and NumPy kernel paths.

Keep notebooks synthetic or client-local. Do not commit proprietary exports,
client dictionaries, screenshots, or derived market data.

## Unsupported scalar-only inputs

Final scalar ES, IMCC, SES, VaR, or NMRF totals are not enough to reconstruct
canonical IMA scenario vectors or NMRF valuation artifacts. Treat scalar-only
exports as unsupported for capital-kernel ingestion unless a separate upstream
artifact provides the underlying vector or scenario-level evidence.

The correct response to scalar-only source data is a validation finding or an
explicit onboarding gap, not fabricated scenario vectors and not liquidity-
horizon scaling of one final ES scalar.

## Review checklist

Before using mapped data downstream, confirm:

- source hashes in `profile.json`, table reports, and `validation_report.json` match the reviewed extracts;
- `mapping.yaml` uses the expected canonical target names and all required fields are mapped;
- P&L sign convention is explicit and reconciled;
- date fields have no unexpected gaps for the target workflow;
- duplicate keys are either rejected or documented by the relevant mapper;
- scenario P&L coverage is rectangular unless an explicit missing-cell policy is reviewed;
- risk-factor names reconcile to the risk-factor master where available;
- accepted rows preserve `source_row_id` lineage where the target supports it;
- scalar-only ES/IMCC/SES/NMRF source data is rejected as insufficient for vector-based kernels;
- all committed examples and fixtures remain synthetic.
