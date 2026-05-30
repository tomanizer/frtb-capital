# GIRR vega v1 synthetic fixture

Synthetic Basel MAR21 GIRR vega book exercising:

- cited vega risk-weight scaling with 60-day GIRR liquidity horizon (MAR21.92 Table 13);
- intra-bucket aggregation with option and underlying tenor correlation (MAR21.93);
- inter-bucket aggregation across EUR and USD buckets (MAR21.90, MAR21.95);
- low, medium, and high correlation scenarios with max selection (MAR21.6, MAR21.7).

Files:

- `sensitivities.json` — canonical input sensitivities and run context;
- `expected_outputs.json` — deterministic capital totals, hashes, and explain slices;
- `invalid_cases.json` — negative validation cases;
- `manifest.json` — file hashes for replay controls.
