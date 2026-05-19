# Liquidity-horizon-adjusted ES decomposition

## Purpose

This document describes the decomposed liquidity-horizon-adjusted expected shortfall (LHA ES) reporting framework.

The objective is to make the LHA calculation:

- auditable,
- regulator-reviewable,
- management-explainable,
- validation-friendly.

The implementation intentionally exposes intermediate aggregation terms rather than only returning a single scalar capital number.

## Regulatory intent

Basel FRTB liquidity-horizon aggregation is structurally decomposable.

The capital calculation is built from:

- liquidity-horizon-specific expected shortfalls,
- weighted squared contributions,
- final square-root aggregation.

Model validation and regulatory review typically require visibility into:

- which LH buckets contribute most,
- how weights affect aggregation,
- whether nested subsets are aligned correctly,
- whether missing subsets are intentional.

The decomposition framework exists to expose these semantics explicitly.

## Canonical decomposition model

The implementation introduces:

- `LHAESComponent`
- `LHAESResult`

Each component exposes:

- liquidity horizon,
- ES value,
- aggregation weight,
- weighted squared contribution,
- whether the component was present.

The aggregate result exposes:

- final LHA ES,
- sum of weighted squares,
- scenario-count metadata,
- metadata-alignment status.

## Canonical reporting path

The canonical vector-based reporting path is:

```python
from frtb_ima.liquidity_horizon import lha_es_breakdown_from_vectors
```

This path validates nested vectors through the canonical validator introduced in Issue #13.

## Example

```python
from datetime import date

import numpy as np

from frtb_ima.data_models import LiquidityHorizon
from frtb_ima.liquidity_horizon import lha_es_breakdown_from_vectors
from frtb_ima.scenario import ScenarioVector, make_scenario_metadata

metadata = make_scenario_metadata(
    [date(2025, 1, 1), date(2025, 1, 2)]
)

result = lha_es_breakdown_from_vectors(
    {
        LiquidityHorizon.LH10: ScenarioVector(
            values=np.array([100.0, 120.0]),
            metadata=metadata,
        ),
        LiquidityHorizon.LH20: ScenarioVector(
            values=np.array([80.0, 90.0]),
            metadata=metadata,
        ),
    }
)

for line in result.summary_lines():
    print(line)
```

## Design decisions

### Canonical decomposition model

The implementation intentionally centralises decomposition semantics.

The goal is to avoid:

- duplicate aggregation logic,
- inconsistent reporting semantics,
- scalar-only shadow paths.

### Validation-first calculation

The vector-based decomposition path validates vectors before calculation.

This ensures:

- deterministic scenario semantics,
- aligned nested vectors,
- stable aggregation assumptions.

### Vectorised-first

The implementation preserves:

- NumPy-backed vectors,
- functional aggregation,
- lightweight deterministic processing.

## Current limitations

The implementation intentionally does not yet include:

- business-calendar semantics,
- stress-window governance,
- reduced/full set decomposition,
- desk-level governance outputs,
- regulator-specific reporting exports.

These remain future workstreams.
