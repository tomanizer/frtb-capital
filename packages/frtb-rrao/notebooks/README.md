# RRAO Demonstration Notebooks

These notebooks are deterministic development artifacts for `frtb-rrao`. They
use synthetic residual-risk positions and package-local fixtures to demonstrate
classification, exclusions, capital-line explain records, allocation reports,
and multi-profile comparison. They are not final regulatory capital outputs.

Smoke-test the notebook code cells from the repository root with:

```bash
MPLBACKEND=Agg uv run --all-extras --directory packages/frtb-rrao pytest --nbmake notebooks
```

Open them interactively with any local Jupyter environment that can import the
workspace packages.

Current notebooks:

- `01_classification_and_exclusions.ipynb` walks every sample-book position
  through classification, exclusions, and cited regulatory decisions.
- `02_capital_lines_and_explain.ipynb` computes RRAO capital lines and explains
  risk-weight, exclusion, and investment-fund treatment.
- `03_allocation_and_breakdown.ipynb` slices additive RRAO capital by desk,
  legal entity, and evidence type with reconciliation checks.
- `04_multi_profile_comparison.ipynb` compares Basel MAR23 and US NPR 2.0
  profile scope, citations, exclusions, and deterministic profile hashes.
