# FRTB-IMA

**Prototype NPR 2.0-style FRTB IMA capital calculator.**

> ⚠️ Prototype only. Not for regulatory reporting. U.S. NPR 2.0 references are
> proposed-rule material based on the March 2026 proposal and Basel FRTB IMA
> concepts.

## What this is

A Python prototype demonstrating how an existing risk engine can generate 10-day scenario P&L vectors, with an ex-post capital assembly layer computing NPR 2.0-style IMA capital:

- Risk factor modellability classification (RFET)
- Liquidity horizon adjusted expected shortfall (LHA ES)
- Internal Model Capital Charge (IMCC)
- Vectorized stress-period calibration from supplied historical risk-class losses
- NMRF stress-method evidence, valuation specs, artifact reconciliation, and SES
- Stressed Expected Shortfall for NMRFs (SES)
- Models-based capital assembly
- Fed NPR PLA Kolmogorov-Smirnov statistic and EU/PRA Spearman comparison metric
- Backtesting exception counts at 97.5% and 99.0% VaR levels
- Structured JSON logging, NDJSON audit records, and Markdown audit reports

The current boundary is intentional: the package assembles and validates
capital inputs, and can select stress windows from supplied historical loss
series, but it does not source raw market data, price trades, run
SBM/DRC/RRAO/CVA capital, compose SA totals, or produce final regulatory
submissions.

## Install

From the monorepo root:

```bash
uv sync
```

For isolated package work from `packages/frtb-ima`:

```bash
python -m pip install -e ".[dev]"
```

Requires Python 3.11+ and numpy.

## Local development

The monorepo root exposes workspace-level targets through `make check` and
`make ima`. This package also includes a package-local `Makefile`; run these
from `packages/frtb-ima`:

```bash
make install
make check
make examples
make fixtures
make audit
make notebooks
make validation-pack
```

Individual targets are available for `make test`, `make lint`, `make format`,
`make format-check`, `make typecheck`, `make fixtures`, `make notebooks`,
`make validation-pack`, and `make demo` (alias for `make examples`). `make audit`
renders the committed fixture's audit report to
`build/audit/capital_run_v1_audit_report.md`.

## Run tests

From the monorepo root:

```bash
uv run pytest packages/frtb-ima/tests
```

From `packages/frtb-ima` after package-local installation:

```bash
python -m pytest
```

## Run demo

From the monorepo root:

```bash
uv run python packages/frtb-ima/examples/run_demo.py
```

From `packages/frtb-ima`:

```bash
python examples/run_demo.py
```

Expected output sections:

```
Risk factor classifications
NMRF method selection
Liquidity horizon adjusted ES
IMCC
SES
Models-based capital
PLA KS statistic
Backtesting exception counts
```

## Package layout

```
packages/frtb-ima/src/frtb_ima/
    data_models.py          Enums and dataclasses
    data_contracts.py       Validated run inputs and scenario cubes
    expected_shortfall.py   ES calculation
    lha_builder.py          Scenario cube to nested LH vector builder
    liquidity_horizon.py    LHA ES from nested vectors
    liquidity_horizon_mapping.py Regulatory risk-factor category to LH table
    reduced_set.py          Indirect-approach reduced-set diagnostics
    stress_periods.py       Vectorized stress-window selection by risk class
    regimes.py              Regulatory policy profiles and run context
    rfet.py                 RFET modellability classification
    rfet_evidence.py        RFET evidence assessment and audit trail
    nmrf_method_selection.py NMRF stress-method evidence and selector
    nmrf_stress_spec.py     NMRF upstream valuation-run specifications
    nmrf_valuation_run.py   NMRF valuation-run reconciliation
    nmrf.py                 NMRF stress artifacts, routing, and SES aggregation
    imcc.py                 IMCC unconstrained / constrained with audit decomposition
    pla.py                  PLA KS/Spearman metrics and policy-window diagnostics
    backtesting.py          Exception counting and optional dated traces
    capital.py              Models-based capital assembly
    logging.py              JSON logging formatter and structured fields
    audit.py                Desk/run audit records and NDJSON serialization
    demo_data.py            Synthetic demo data
```

## Key design decisions

**Nested LH vectors, not scalar scaling.** The LHA ES uses nested P&L sub-vectors per liquidity horizon subset, per the NPR 2.0 formula. Scaling a single ES scalar by sqrt(weighted_avg_LH / 10) is explicitly labelled a toy approximation.

**LH mapping is category-based.** The regulatory risk-factor category to
liquidity-horizon table is available in `liquidity_horizon_mapping.py`, including
short-maturity and weighted-average index helpers. The package does not infer
those categories from vendor or instrument data.

**Deterministic-first.** No LLM involvement in calculations. This layer computes capital from risk engine outputs.

**Minimal dependencies.** numpy only. No pandas, no scipy — keeps it auditable.

**Functional style.** Classes only where data structure demands it (dataclasses). Business logic is pure functions.

**Stress-period calibration is pre-run.** Stress windows are selected by risk
class from supplied historical loss/severity vectors before NMRF valuation
specs are built. The selector is vectorized with NumPy and produces
`NMRFStressPeriodSpec` inputs, but raw market-data sourcing and pricing remain
upstream.

**Audit trail without backend coupling.** Runtime observability uses stdlib
logging and compact scalar JSON events at policy-wrapper boundaries. Durable
desk/run audit records are serialisable NDJSON objects and can be rendered to a
deterministic Markdown report. Object-store, database, Splunk, OpenTelemetry,
Parquet, or DuckDB integration belongs in an external runner.

## Regulatory assumptions

See [docs/REGULATORY_ASSUMPTIONS.md](docs/REGULATORY_ASSUMPTIONS.md).

For a bidirectional code-to-regulation and regulation-to-code index, see
[docs/REGULATORY_TRACEABILITY.md](docs/REGULATORY_TRACEABILITY.md).

For machine-readable source links and section hints without vendored regulatory
text, see [docs/regulatory_sources.yml](docs/regulatory_sources.yml).

For the committed synthetic capital-run fixture contract, see
[docs/DATASET_CONTRACT.md](docs/DATASET_CONTRACT.md).
