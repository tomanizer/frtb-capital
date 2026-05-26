# FRTB-IMA

**Prototype NPR 2.0-style FRTB IMA capital calculator.**

> ⚠️ Prototype only. Not for regulatory reporting. All regulatory statements are working assumptions based on the March 2026 U.S. NPR 2.0 proposal and Basel FRTB IMA concepts.

## What this is

A Python prototype demonstrating how an existing risk engine can generate 10-day scenario P&L vectors, with an ex-post capital assembly layer computing NPR 2.0-style IMA capital:

- Risk factor modellability classification (RFET)
- Liquidity horizon adjusted expected shortfall (LHA ES)
- Internal Model Capital Charge (IMCC)
- Stressed Expected Shortfall for NMRFs (SES)
- Models-based capital assembly
- PLA Kolmogorov-Smirnov statistic
- Backtesting exception counts

## Install

```bash
pip install -e ".[dev]"
```

Requires Python 3.11+, numpy.

## Local development

The repository includes a small `Makefile` for a fresh-clone workflow:

```bash
make install
make check
make demo
```

Individual targets are available for `make test`, `make lint`, and `make typecheck`.

## Run tests

```bash
pytest
```

## Run demo

```bash
python examples/run_demo.py
```

Expected output sections:

```
Risk factor classifications
Liquidity horizon adjusted ES
IMCC
SES
Models-based capital
PLA KS statistic
Backtesting exception counts
```

## Package layout

```
src/frtb_ima/
    data_models.py          Enums and dataclasses
    expected_shortfall.py   ES calculation
    liquidity_horizon.py    LHA ES from nested vectors
    rfet.py                 RFET modellability classification
    nmrf.py                 NMRF SES aggregation
    imcc.py                 IMCC unconstrained / constrained
    pla.py                  PLA KS statistic
    backtesting.py          Exception counting
    capital.py              Models-based capital assembly
    demo_data.py            Synthetic demo data
```

## Key design decisions

**Nested LH vectors, not scalar scaling.** The LHA ES uses nested P&L sub-vectors per liquidity horizon subset, per the NPR 2.0 formula. Scaling a single ES scalar by sqrt(weighted_avg_LH / 10) is explicitly labelled a toy approximation.

**Deterministic-first.** No LLM involvement in calculations. This layer computes capital from risk engine outputs.

**Minimal dependencies.** numpy only. No pandas, no scipy — keeps it auditable.

**Functional style.** Classes only where data structure demands it (dataclasses). Business logic is pure functions.

## Regulatory assumptions

See [docs/REGULATORY_ASSUMPTIONS.md](docs/REGULATORY_ASSUMPTIONS.md).

## Architecture notes

See [docs/CODEX_HANDOFF.md](docs/CODEX_HANDOFF.md).
