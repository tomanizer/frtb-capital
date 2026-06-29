import { useEffect, useMemo, useState } from "react";
import {
  exportMapping,
  getTable,
  listTables,
  loadSourceDuckDb,
  loadSourcePath,
  suggestMapping,
  uploadSource,
  validateMapping,
} from "./api";
import type {
  ColumnMappingState,
  InputTableDetail,
  InputTableSummary,
  SourcePreview,
  ValidationResult,
  WizardStep,
} from "./types";

const COMPONENTS = ["All", "DRC", "SBM", "RRAO", "CVA", "IMA"] as const;

const STEPS: { id: WizardStep; title: string; subtitle: string }[] = [
  { id: "dataset", title: "Target dataset", subtitle: "Choose canonical Arrow contract" },
  { id: "source", title: "Client source", subtitle: "Load CSV, Parquet, or SQL" },
  { id: "mapping", title: "Column mapping", subtitle: "Align client columns" },
  { id: "validate", title: "Validate & export", subtitle: "Preview and download mapping" },
];

export default function App() {
  const [step, setStep] = useState<WizardStep>("dataset");
  const [componentFilter, setComponentFilter] = useState<string>("All");
  const [tables, setTables] = useState<InputTableSummary[]>([]);
  const [selectedTable, setSelectedTable] = useState<InputTableSummary | null>(null);
  const [tableDetail, setTableDetail] = useState<InputTableDetail | null>(null);
  const [sourcePreview, setSourcePreview] = useState<SourcePreview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string | null>>({});
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [exportContent, setExportContent] = useState<string>("");
  const [exportFilename, setExportFilename] = useState<string>("mapping.yaml");
  const [exportFormat, setExportFormat] = useState<"yaml" | "toml" | "json">("yaml");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [sourceTab, setSourceTab] = useState<"upload" | "path" | "duckdb">("upload");
  const [pathValue, setPathValue] = useState("");
  const [duckQuery, setDuckQuery] = useState("SELECT * FROM client_table LIMIT 5000");
  const [duckDatabase, setDuckDatabase] = useState(":memory:");
  const [duckAttachPath, setDuckAttachPath] = useState("");
  const [lineageSystem, setLineageSystem] = useState("client_etl");

  useEffect(() => {
    const component = componentFilter === "All" ? undefined : componentFilter;
    listTables(component)
      .then(setTables)
      .catch((exc) => setError(String(exc)));
  }, [componentFilter]);

  useEffect(() => {
    if (!selectedTable) {
      setTableDetail(null);
      return;
    }
    getTable(selectedTable.package, selectedTable.id)
      .then(setTableDetail)
      .catch((exc) => setError(String(exc)));
  }, [selectedTable]);

  const mappingState = useMemo<ColumnMappingState | null>(() => {
    if (!sourcePreview || !selectedTable) return null;
    return {
      session_id: sourcePreview.session_id,
      target_package: selectedTable.package,
      target_table_id: selectedTable.id,
      mapping,
    };
  }, [mapping, selectedTable, sourcePreview]);

  const mappedRequired = useMemo(() => {
    if (!tableDetail) return { done: 0, total: 0 };
    const required = tableDetail.columns.filter((column) => column.required);
    const done = required.filter((column) => Boolean(mapping[column.name])).length;
    return { done, total: required.length };
  }, [mapping, tableDetail]);

  async function handleUpload(file: File) {
    setBusy(true);
    setError(null);
    try {
      const preview = await uploadSource(file);
      setSourcePreview(preview);
      setValidation(null);
      setExportContent("");
      setStep("source");
    } catch (exc) {
      setError(String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function handleLoadPath() {
    setBusy(true);
    setError(null);
    try {
      const preview = await loadSourcePath(pathValue);
      setSourcePreview(preview);
      setValidation(null);
      setExportContent("");
    } catch (exc) {
      setError(String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function handleLoadDuckDb() {
    setBusy(true);
    setError(null);
    try {
      const attach_files = duckAttachPath
        ? { client_table: duckAttachPath }
        : undefined;
      const preview = await loadSourceDuckDb({
        database_path: duckDatabase,
        query: duckQuery,
        attach_files,
      });
      setSourcePreview(preview);
      setValidation(null);
      setExportContent("");
    } catch (exc) {
      setError(String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function handleSuggestMapping() {
    if (!mappingState) return;
    setBusy(true);
    setError(null);
    try {
      const suggested = await suggestMapping(mappingState);
      setMapping(suggested.mapping);
      setStep("mapping");
    } catch (exc) {
      setError(String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function handleValidate() {
    if (!mappingState) return;
    setBusy(true);
    setError(null);
    try {
      const result = await validateMapping(mappingState);
      setValidation(result);
      setStep("validate");
    } catch (exc) {
      setError(String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function handleExport() {
    if (!mappingState) return;
    setBusy(true);
    setError(null);
    try {
      const response = await exportMapping({
        ...mappingState,
        format: exportFormat,
        source_connector: sourceTab === "duckdb" ? "duckdb" : sourceTab === "path" ? "path" : "file",
        lineage_source_system: lineageSystem,
      });
      setExportContent(response.content);
      setExportFilename(response.filename);
    } catch (exc) {
      setError(String(exc));
    } finally {
      setBusy(false);
    }
  }

  function downloadExport() {
    if (!exportContent) return;
    const blob = new Blob([exportContent], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = exportFilename;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  const stepIndex = STEPS.findIndex((item) => item.id === step);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">F</div>
          <div>
            <h1>FRTB Onboarding</h1>
            <p>Client data to Arrow contracts</p>
          </div>
        </div>
        <div className="step-list">
          {STEPS.map((item, index) => (
            <button
              key={item.id}
              type="button"
              className={`step-item ${step === item.id ? "active" : ""} ${index < stepIndex ? "done" : ""}`}
              onClick={() => setStep(item.id)}
            >
              <span className="step-index">{index + 1}</span>
              <span className="step-copy">
                <strong>{item.title}</strong>
                <span>{item.subtitle}</span>
              </span>
            </button>
          ))}
        </div>
      </aside>

      <main className="main">
        <header className="page-header">
          <div>
            <h2>{STEPS.find((item) => item.id === step)?.title}</h2>
            <p>{STEPS.find((item) => item.id === step)?.subtitle}</p>
          </div>
          {selectedTable ? (
            <span className="chip">
              {selectedTable.component} · {selectedTable.label}
            </span>
          ) : null}
        </header>

        {error ? <div className="alert error">{error}</div> : null}

        {step === "dataset" ? (
          <section className="panel">
            <div className="panel-header">
              <strong>Select canonical input table</strong>
              <span className="chip">{tables.length} datasets</span>
            </div>
            <div className="panel-body">
              <div className="filter-row">
                {COMPONENTS.map((component) => (
                  <button
                    key={component}
                    type="button"
                    className={`filter-pill ${componentFilter === component ? "active" : ""}`}
                    onClick={() => setComponentFilter(component)}
                  >
                    {component}
                  </button>
                ))}
              </div>
              <div className="dataset-grid">
                {tables.map((table) => (
                  <button
                    key={`${table.package}:${table.id}`}
                    type="button"
                    className={`dataset-card ${selectedTable?.package === table.package && selectedTable?.id === table.id ? "selected" : ""}`}
                    onClick={() => {
                      setSelectedTable(table);
                      setMapping({});
                      setValidation(null);
                      setExportContent("");
                    }}
                  >
                    <span className="chip">{table.component}</span>
                    <h3>{table.label}</h3>
                    <p>{table.description}</p>
                    <p>
                      {table.required_column_count} required / {table.column_count} columns
                    </p>
                  </button>
                ))}
              </div>
              <div className="footer-actions">
                <span />
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={!selectedTable}
                  onClick={() => setStep("source")}
                >
                  Continue to source load
                </button>
              </div>
            </div>
          </section>
        ) : null}

        {step === "source" ? (
          <section className="panel">
            <div className="panel-header">
              <strong>Load client dataset</strong>
              {sourcePreview ? <span className="chip">{sourcePreview.row_count.toLocaleString()} rows</span> : null}
            </div>
            <div className="panel-body">
              <div className="source-tabs">
                {(["upload", "path", "duckdb"] as const).map((tab) => (
                  <button
                    key={tab}
                    type="button"
                    className={`source-tab ${sourceTab === tab ? "active" : ""}`}
                    onClick={() => setSourceTab(tab)}
                  >
                    {tab === "upload" ? "Upload file" : tab === "path" ? "Server path" : "DuckDB query"}
                  </button>
                ))}
              </div>

              {sourceTab === "upload" ? (
                <label className="dropzone">
                  <input
                    type="file"
                    hidden
                    accept=".csv,.parquet,.pq,.arrow,.ipc"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) void handleUpload(file);
                    }}
                  />
                  <strong>Drop or choose CSV, Parquet, or Arrow IPC</strong>
                  <span>Files stay in local memory for this session only.</span>
                </label>
              ) : null}

              {sourceTab === "path" ? (
                <>
                  <div className="field">
                    <label htmlFor="path">Absolute or relative file path</label>
                    <input
                      id="path"
                      value={pathValue}
                      onChange={(event) => setPathValue(event.target.value)}
                      placeholder="/data/client/drc_positions.parquet"
                    />
                  </div>
                  <button type="button" className="btn btn-primary" disabled={busy || !pathValue} onClick={() => void handleLoadPath()}>
                    Load file
                  </button>
                </>
              ) : null}

              {sourceTab === "duckdb" ? (
                <>
                  <div className="field">
                    <label htmlFor="duckdb">Database path</label>
                    <input
                      id="duckdb"
                      value={duckDatabase}
                      onChange={(event) => setDuckDatabase(event.target.value)}
                    />
                  </div>
                  <div className="field">
                    <label htmlFor="attach">Attach file as view `client_table` (optional)</label>
                    <input
                      id="attach"
                      value={duckAttachPath}
                      onChange={(event) => setDuckAttachPath(event.target.value)}
                      placeholder="/data/client/positions.parquet"
                    />
                  </div>
                  <div className="field">
                    <label htmlFor="query">SQL query</label>
                    <textarea
                      id="query"
                      rows={5}
                      value={duckQuery}
                      onChange={(event) => setDuckQuery(event.target.value)}
                    />
                  </div>
                  <button type="button" className="btn btn-primary" disabled={busy || !duckQuery} onClick={() => void handleLoadDuckDb()}>
                    Run query
                  </button>
                </>
              ) : null}

              {sourcePreview ? (
                <>
                  <div className="stats-grid" style={{ marginTop: 20 }}>
                    <div className="stat-card">
                      <strong>{sourcePreview.row_count.toLocaleString()}</strong>
                      <span>Rows loaded</span>
                    </div>
                    <div className="stat-card">
                      <strong>{sourcePreview.columns.length}</strong>
                      <span>Source columns</span>
                    </div>
                    <div className="stat-card">
                      <strong>{tableDetail?.column_count ?? "—"}</strong>
                      <span>Target columns</span>
                    </div>
                    <div className="stat-card">
                      <strong>{mappedRequired.total || "—"}</strong>
                      <span>Required target fields</span>
                    </div>
                  </div>
                  <div className="preview-table-wrap">
                    <table className="preview-table">
                      <thead>
                        <tr>
                          {sourcePreview.columns.map((column) => (
                            <th key={column.name}>{column.name}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {sourcePreview.preview_rows.map((row, rowIndex) => (
                          <tr key={rowIndex}>
                            {sourcePreview.columns.map((column) => (
                              <td key={column.name}>{String(row[column.name] ?? "")}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : null}

              <div className="footer-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setStep("dataset")}>
                  Back
                </button>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={!sourcePreview || !selectedTable || busy}
                  onClick={() => void handleSuggestMapping()}
                >
                  Auto-map columns
                </button>
              </div>
            </div>
          </section>
        ) : null}

        {step === "mapping" && tableDetail && sourcePreview ? (
          <section className="panel">
            <div className="panel-header">
              <strong>Map client columns to canonical spec</strong>
              <div className="toolbar">
                <span className="chip">
                  {mappedRequired.done}/{mappedRequired.total} required mapped
                </span>
                <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => void handleSuggestMapping()}>
                  Re-suggest
                </button>
              </div>
            </div>
            <div className="panel-body mapping-layout">
              <div>
                <table className="mapping-table">
                  <thead>
                    <tr>
                      <th>Canonical column</th>
                      <th>Client source column</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tableDetail.columns.map((column) => (
                      <tr key={column.name}>
                        <td>
                          <div className="canonical-name">{column.name}</div>
                          <div className="toolbar" style={{ marginTop: 8 }}>
                            <span className={`badge ${column.required ? "required" : "optional"}`}>
                              {column.required ? "required" : "optional"}
                            </span>
                            <span className="badge type">{column.logical_type}</span>
                          </div>
                          {column.aliases.length ? (
                            <div className="alias-list">Aliases: {column.aliases.join(", ")}</div>
                          ) : null}
                        </td>
                        <td>
                          <select
                            value={mapping[column.name] ?? ""}
                            onChange={(event) =>
                              setMapping((current) => ({
                                ...current,
                                [column.name]: event.target.value || null,
                              }))
                            }
                          >
                            <option value="">— unmapped —</option>
                            {sourcePreview.columns.map((sourceColumn) => (
                              <option key={sourceColumn.name} value={sourceColumn.name}>
                                {sourceColumn.name}
                              </option>
                            ))}
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div>
                <h3 style={{ marginTop: 0 }}>Source column profile</h3>
                {sourcePreview.columns.map((column) => (
                  <div key={column.name} className="panel" style={{ marginBottom: 12, boxShadow: "none" }}>
                    <div className="panel-body" style={{ padding: 14 }}>
                      <strong className="canonical-name">{column.name}</strong>
                      <div className="alias-list">{column.arrow_type}</div>
                      <div className="alias-list">
                        Samples: {column.sample_values.map(String).join(", ") || "—"}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="panel-body" style={{ borderTop: "1px solid var(--border)" }}>
              <div className="footer-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setStep("source")}>
                  Back
                </button>
                <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void handleValidate()}>
                  Validate mapping
                </button>
              </div>
            </div>
          </section>
        ) : null}

        {step === "validate" ? (
          <section className="panel">
            <div className="panel-header">
              <strong>Validation and export</strong>
              <div className="toolbar">
                <select value={exportFormat} onChange={(event) => setExportFormat(event.target.value as "yaml" | "toml" | "json")}>
                  <option value="yaml">YAML</option>
                  <option value="toml">TOML</option>
                  <option value="json">JSON</option>
                </select>
                <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => void handleExport()}>
                  Generate mapping
                </button>
                <button type="button" className="btn btn-primary" disabled={!exportContent} onClick={downloadExport}>
                  Download
                </button>
              </div>
            </div>
            <div className="panel-body">
              {validation ? (
                <>
                  <div className="stats-grid">
                    <div className="stat-card">
                      <strong>{validation.accepted_rows}</strong>
                      <span>Accepted rows</span>
                    </div>
                    <div className="stat-card">
                      <strong>{validation.rejected_rows}</strong>
                      <span>Rejected rows</span>
                    </div>
                    <div className="stat-card">
                      <strong>{validation.batch_built ? "Yes" : "No"}</strong>
                      <span>Batch built</span>
                    </div>
                    <div className="stat-card">
                      <strong>{validation.input_table_hash?.slice(0, 12) ?? "—"}</strong>
                      <span>Input table hash</span>
                    </div>
                  </div>
                  {validation.diagnostics.length ? (
                    validation.diagnostics.map((diagnostic, index) => (
                      <div
                        key={`${diagnostic.code}-${index}`}
                        className={`alert ${diagnostic.severity === "error" ? "error" : "warning"}`}
                      >
                        <strong>{diagnostic.code}</strong> — {diagnostic.message}
                      </div>
                    ))
                  ) : (
                    <div className="alert success">Normalization completed without adapter diagnostics.</div>
                  )}
                  <h3>Accepted preview</h3>
                  <div className="preview-table-wrap">
                    <table className="preview-table">
                      <thead>
                        <tr>
                          {validation.preview_columns.map((column) => (
                            <th key={column}>{column}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {validation.preview_rows.map((row, rowIndex) => (
                          <tr key={rowIndex}>
                            {validation.preview_columns.map((column) => (
                              <td key={column}>{String(row[column] ?? "")}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : null}

              <div className="field" style={{ marginTop: 18 }}>
                <label htmlFor="lineage">Lineage source system</label>
                <input
                  id="lineage"
                  value={lineageSystem}
                  onChange={(event) => setLineageSystem(event.target.value)}
                />
              </div>

              {exportContent ? (
                <>
                  <h3>Mapping artifact</h3>
                  <pre className="code-block">{exportContent}</pre>
                </>
              ) : null}

              <div className="footer-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setStep("mapping")}>
                  Back to mapping
                </button>
                <button type="button" className="btn btn-primary" disabled={!exportContent} onClick={downloadExport}>
                  Download {exportFilename}
                </button>
              </div>
            </div>
          </section>
        ) : null}
      </main>
    </div>
  );
}
