# SBM Demonstration Notebooks

These notebooks are deterministic development artifacts for `frtb-sbm`. They
use synthetic inputs and package-local fixtures to demonstrate public APIs,
validation replay, curvature/vega treatment, and the Arrow batch fast path.
They are not final regulatory capital outputs.

Smoke-test the notebook code cells from the repository root with:

```bash
uv run pytest packages/frtb-sbm/tests/test_sbm_notebooks.py
```

Open them interactively with any local Jupyter environment that can import the
workspace packages.

Current notebooks:

- `00_validation_map.ipynb` maps supported Basel MAR21 risk-class/measure paths
  and executable fixture packs.
- `01_delta_fixture_walkthrough.ipynb` replays the GIRR delta fixture and shows
  deterministic audit output.
- `02_vega_curvature_paths.ipynb` demonstrates GIRR/non-GIRR vega fixtures and
  synthetic curvature branch evidence.
- `03_arrow_batch_fast_path.ipynb` compares row API output with the Arrow batch
  portfolio dispatcher and shows fast-path diagnostics.
