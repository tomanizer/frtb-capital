# GIRR delta v1 synthetic fixture

Synthetic Basel MAR21 GIRR delta book exercising:

- cited risk-weight lookup with liquid-currency `sqrt(2)` adjustment (MAR21.40);
- intra-bucket aggregation with tenor correlation and `Sb` floor (MAR21.4, MAR21.41);
- inter-bucket aggregation across EUR and USD buckets (MAR21.42);
- low, medium, and high correlation scenarios with max selection (MAR21.6, MAR21.7).

Files:

- `sensitivities.json` — canonical input sensitivities and run context;
- `expected_outputs.json` — deterministic capital totals, hashes, and explain slices;
- `invalid_cases.json` — negative validation and unsupported-path cases;
- `manifest.json` — file hashes for replay controls.
