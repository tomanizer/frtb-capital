# Nested liquidity-horizon vector validation

## Purpose

This document describes the canonical validation framework for nested liquidity-horizon vectors.

The validator exists to make structural assumptions explicit before liquidity-horizon-adjusted expected shortfall (LHA ES) or IMCC calculations consume scenario vectors.

## Regulatory intent

Basel FRTB liquidity-horizon aggregation assumes:

- aligned historical scenarios,
- deterministic ordering,
- nested liquidity-horizon subsets,
- common scenario windows.

See [REGULATORY_TRACEABILITY.md](REGULATORY_TRACEABILITY.md) for the cross-reference
to Basel MAR33, the U.S. NPR 2.0 LHA ES proposal, and EU CRR Articles 325bc and
325bd.

Implementation failures frequently occur when:

- vectors are silently reordered,
- scenario windows differ,
- longer-horizon subsets are not true nested subsets,
- missing vectors are ignored silently.

The validator centralises these assumptions.

## Validation checks

The canonical validator currently checks:

- LH10 exists,
- vectors are non-empty,
- scenario lengths match,
- metadata ordering is aligned,
- optional nesting evidence is structurally valid.

## Canonical validation entry point

```python
from frtb_ima.scenario_validation import validate_nested_lh_vectors
```

All future LHA ES and IMCC paths should validate vectors through this canonical entry point.

## Example

```python
from datetime import date

import numpy as np

from frtb_ima.data_models import LiquidityHorizon
from frtb_ima.scenario import ScenarioVector, make_scenario_metadata
from frtb_ima.scenario_validation import validate_nested_lh_vectors

metadata = make_scenario_metadata(
    [date(2025, 1, 1), date(2025, 1, 2)]
)

vectors = {
    LiquidityHorizon.LH10: ScenarioVector(
        values=np.array([100.0, 120.0]),
        metadata=metadata,
    ),
    LiquidityHorizon.LH20: ScenarioVector(
        values=np.array([80.0, 90.0]),
        metadata=metadata,
    ),
}

result = validate_nested_lh_vectors(vectors)
```

## Design decisions

### Centralised validation

Validation logic should not be duplicated across:

- LHA ES,
- IMCC,
- stress scaling,
- decomposition reporting.

The validator is intended to become the single canonical structural validation layer.

### Functional style

The implementation intentionally avoids:

- framework-heavy abstractions,
- mutable validation state,
- duplicated validation objects.

### Vectorised-first

The validator is designed around NumPy-backed vectors and future compatibility with:

- Polars,
- DuckDB,
- Arrow-style columnar processing.

## Current limitations

The validator intentionally does not yet implement:

- business-calendar validation,
- stress-window governance,
- reduced/full set governance,
- RFET evidence management,
- distributed execution semantics.

These remain explicit upstream placeholders.
