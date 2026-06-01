# non_girr_vega_v1

Synthetic Basel MAR21 non-GIRR vega fixture covering FX, equity, commodity,
CSR non-securitisation, CSR securitisation non-CTP, and CSR securitisation CTP.

The fixture is intentionally small: one sensitivity per risk class keeps the
expected outputs readable while proving that the public SBM API supports every
MAR21.90-MAR21.95 non-GIRR vega path and preserves deterministic audit hashes.
