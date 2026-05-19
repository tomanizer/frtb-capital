# Scenario metadata and canonical vector semantics

## Purpose

This document defines the canonical scenario metadata representation used by the FRTB IMA prototype.

The objective is to create a deterministic and auditable interface between:

- upstream scenario generation,
- downstream capital calculations.

The engine intentionally does not generate scenarios here. It only validates and carries scenario vectors.

## Regulatory intent

Basel FRTB and NPR 2.0-style calculations rely heavily on aligned historical scenario vectors.

This matters because:

- liquidity-horizon aggregation assumes aligned historical shocks,
- constrained/unconstrained IMCC assumes consistent scenario ordering,
- reduced/full set scaling assumes comparable historical windows,
- PLA and backtesting depend on deterministic alignment semantics.

Many implementation failures come from:

- silently misaligned vectors,
- reordered scenarios,
- inconsistent stress/current windows,
- duplicated or missing scenario observations.

The scenario metadata layer exists to make these assumptions explicit.

## Canonical structures

The implementation introduces:

- `ScenarioMetadata`
- `ScenarioVector`
- `ScenarioSetType`

The canonical vector representation stores:

- NumPy vector values,
- optional aligned scenario metadata,
- optional risk-class metadata,
- optional liquidity-horizon metadata.

## Design decisions

### Lightweight immutable structures

The implementation intentionally uses:

- frozen dataclasses,
- NumPy arrays,
- functional validation helpers.

It intentionally avoids:

- ORM-style models,
- framework-heavy abstractions,
- mutable global state.

### Vectorised-first

Vectors are stored as NumPy float64 arrays to support efficient downstream calculations.

### Deterministic ordering

Scenario ordering is explicit and validated.

The implementation validates:

- unique scenario IDs,
- unique scenario dates,
- aligned vector ordering.

## Example

```python
from datetime import date

import numpy as np

from frtb_ima.scenario import (
    ScenarioSetType,
    ScenarioVector,
    make_scenario_metadata,
)

metadata = make_scenario_metadata(
    [date(2025, 1, 1), date(2025, 1, 2)],
    prefix="stress",
    scenario_set=ScenarioSetType.STRESS,
)

vector = ScenarioVector(
    values=np.array([100.0, 120.0]),
    metadata=metadata,
)
```

## Current limitations

The current implementation intentionally excludes:

- upstream market-data ingestion,
- stress-window governance,
- RFET evidence management,
- distributed compute concerns,
- business-calendar management.

These remain explicit upstream placeholders in the broader roadmap.
