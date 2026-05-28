# Capital Run v1 Validation Pack

The validation pack is a deterministic, notebook-backed review bundle for the
committed `capital_run_v1` synthetic fixture. It is designed for model
validators and quants who need to inspect the prototype workflow from fixture
lineage through capital assembly.

The formal model documentation pack for this package lives at
[`docs/model_documentation/frtb-ima/`](../../../docs/model_documentation/frtb-ima/).
Use that pack for intended use, conceptual soundness, derivation, assumptions,
sensitivity-analysis planning, monitoring, and change history.

The pack is not a regulatory report, does not use live market data, and does
not present final regulatory capital. NPR 2.0 references are proposed-rule
material for this prototype.

## Build

```bash
make validation-pack
```

The target executes every notebook with `nbmake`, renders the fixture audit
report, emits an NDJSON desk audit record, and writes a deterministic manifest.
`make check` deliberately remains the faster per-commit gate; notebooks are
covered by the dedicated local target and CI artifact job.

## Output

The generated files are written under `build/validation/capital_run_v1/`:

- `README.md`: reviewer-facing pack summary.
- `validation_pack_manifest.json`: machine-readable run metadata, fixture
  hashes, notebook hashes, golden-output inventory, artifact hashes, and open
  prototype gaps.
- `audit/capital_run_v1_audit_report.md`: deterministic Markdown audit report
  rendered from the fixture's golden outputs.
- `audit/capital_run_v1_desk_records.ndjson`: serialised desk audit record.

Audit records and reports can now include a compact `input_manifest` lineage
summary built from `CapitalRunInputManifest`. The committed fixture manifest is
mapped into that structure by package APIs, preserving fixture checksums while
adding source-system, schema-version, sign-convention, count, and validation
status controls for each artifact.

CI uploads this directory as the `capital-run-v1-validation-pack` artifact from
the notebooks job.

## Review Order

Start with `notebooks/00_validation_map.ipynb` for the fixture lineage,
proposed-rule assumptions, notebook index, golden-output inventory, and open
gaps. Then review the process notebooks in order:

1. `01_rfet_evidence_classification.ipynb`
2. `02_stress_period_selection.ipynb`
3. `03_lha_es_imcc.ipynb`
4. `04_nmrf_chain.ipynb`
5. `05_pla_backtesting.ipynb`
6. `06_capital_assembly.ipynb`

Use the generated manifest to confirm that reviewers are looking at the same
fixture files, notebook sources, and audit artifacts that CI executed.
Use any attached `input_manifest` summary in audit NDJSON or Markdown reports
to confirm the upstream artifact lineage behind a replay or validation pack.
