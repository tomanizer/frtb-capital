# frtb-cva notebooks

Executable notebooks demonstrating the current CVA package surface:

- `00_validation_map.ipynb` maps the package entrypoints to supported CVA workflows and validation fixtures.
- `01_ba_cva_fixture_walkthrough.ipynb` walks through reduced and full BA-CVA with audit lines and hedge recognition.
- `02_sa_cva_sensitivities.ipynb` demonstrates SA-CVA risk-class aggregation across supported delta and vega paths.
- `03_mixed_method_attribution_impact.ipynb` demonstrates mixed SA-CVA plus BA-CVA carve-out, attribution, and finite-difference impact.
- `04_arrow_batch_fast_path.ipynb` demonstrates the Arrow batch and package-owned columnar batch path.

The notebooks are intentionally synthetic. They cite package fixtures and public APIs, not proprietary market data.
