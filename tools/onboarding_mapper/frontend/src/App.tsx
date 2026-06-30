import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  Circle,
  ClipboardList,
  Columns3,
  Copy,
  Database,
  Download,
  FileInput,
  FolderOpen,
  Play,
  RefreshCw,
  Search,
  Table2,
  Trash2,
  UploadCloud,
  WandSparkles,
} from "lucide-react";
import {
  exportMapping,
  getTable,
  importMapping,
  listTables,
  loadSourceDuckDb,
  loadSourcePath,
  suggestMapping,
  uploadSource,
  validateMapping,
} from "./api";
import type {
  ColumnSpecView,
  ColumnMappingState,
  InputTableDetail,
  InputTableSummary,
  SourceColumnPreview,
  SourcePreview,
  ValidationResult,
  WizardStep,
} from "./types";

const COMPONENTS = ["All", "DRC", "SBM", "RRAO", "CVA", "IMA"] as const;

const STEPS: { id: WizardStep; title: string; subtitle: string }[] = [
  { id: "dataset", title: "Target dataset", subtitle: "Choose the canonical input contract" },
  { id: "source", title: "Client source", subtitle: "Load and inspect the client table" },
  { id: "mapping", title: "Column mapping", subtitle: "Align source fields to the target schema" },
  { id: "validate", title: "Validate and export", subtitle: "Normalize a preview and generate the artifact" },
];

type MappingFilter = "all" | "required" | "unmapped" | "mapped" | "issues";
type PreviewMode = "columns" | "rows";

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") return Number.isFinite(value) ? value.toLocaleString() : String(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  return String(value);
}

function tableKey(table: InputTableSummary): string {
  return `${table.package}:${table.id}`;
}

function lower(value: string | null | undefined): string {
  return (value ?? "").toLowerCase();
}

function diagnosticColumnKey(columnName: string | null | undefined): string {
  return lower(columnName).replace(/[^a-z0-9]/g, "");
}

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
  // Non-blocking, success-with-caveat messages (e.g. an import that dropped
  // unknown fields), kept distinct from the red error channel.
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [datasetSearch, setDatasetSearch] = useState("");
  const [sourceTab, setSourceTab] = useState<"upload" | "path" | "duckdb">("upload");
  // The connector that actually produced the loaded session, recorded so export
  // lineage reflects the real source rather than the currently-selected tab.
  const [loadedConnector, setLoadedConnector] = useState<"file" | "path" | "duckdb" | null>(null);
  const [pathValue, setPathValue] = useState("");
  const [duckQuery, setDuckQuery] = useState("SELECT * FROM client_table LIMIT 5000");
  const [duckDatabase, setDuckDatabase] = useState(":memory:");
  const [duckAttachPath, setDuckAttachPath] = useState("");
  const [previewMode, setPreviewMode] = useState<PreviewMode>("columns");
  const [mappingSearch, setMappingSearch] = useState("");
  const [mappingFilter, setMappingFilter] = useState<MappingFilter>("all");
  const [lineageSystem, setLineageSystem] = useState("client_etl");
  const [copied, setCopied] = useState(false);

  const uploadInputRef = useRef<HTMLInputElement>(null);
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const component = componentFilter === "All" ? undefined : componentFilter;
    listTables(component)
      .then((items) => {
        setTables(items);
        setError(null);
      })
      .catch((exc) => setError(String(exc)));
  }, [componentFilter]);

  useEffect(() => {
    if (!selectedTable) {
      setTableDetail(null);
      return;
    }
    getTable(selectedTable.package, selectedTable.id)
      .then((detail) => {
        setTableDetail(detail);
        setError(null);
      })
      .catch((exc) => setError(String(exc)));
  }, [selectedTable]);

  useEffect(() => {
    return () => {
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
    };
  }, []);

  const stepIndex = STEPS.findIndex((item) => item.id === step);

  const mappingState = useMemo<ColumnMappingState | null>(() => {
    if (!sourcePreview || !selectedTable) return null;
    return {
      session_id: sourcePreview.session_id,
      target_package: selectedTable.package,
      target_table_id: selectedTable.id,
      mapping,
    };
  }, [mapping, selectedTable, sourcePreview]);

  const filteredTables = useMemo(() => {
    const query = lower(datasetSearch);
    if (!query) return tables;
    return tables.filter((table) =>
      [
        table.component,
        table.label,
        table.description,
        table.package,
        table.id,
        table.sbm_risk_class ?? "",
        table.sbm_risk_measure ?? "",
      ]
        .join(" ")
        .toLowerCase()
        .includes(query),
    );
  }, [datasetSearch, tables]);

  const sourceColumnsByName = useMemo(() => {
    return new Map(sourcePreview?.columns.map((column) => [column.name, column]) ?? []);
  }, [sourcePreview]);

  const mappedRequired = useMemo(() => {
    if (!tableDetail) return { done: 0, total: 0, missing: [] as ColumnSpecView[] };
    const required = tableDetail.columns.filter((column) => column.required);
    const missing = required.filter((column) => !mapping[column.name]);
    return { done: required.length - missing.length, total: required.length, missing };
  }, [mapping, tableDetail]);

  const mappedTotal = useMemo(() => {
    if (!tableDetail) return { done: 0, total: 0 };
    const done = tableDetail.columns.filter((column) => Boolean(mapping[column.name])).length;
    return { done, total: tableDetail.columns.length };
  }, [mapping, tableDetail]);

  const duplicateSources = useMemo(() => {
    const counts = new Map<string, number>();
    Object.values(mapping).forEach((sourceName) => {
      if (!sourceName) return;
      counts.set(sourceName, (counts.get(sourceName) ?? 0) + 1);
    });
    return [...counts.entries()].filter(([, count]) => count > 1).map(([sourceName]) => sourceName);
  }, [mapping]);

  const diagnosticsByColumn = useMemo(() => {
    const grouped = new Map<string, string[]>();
    validation?.diagnostics.forEach((diagnostic) => {
      const key = diagnosticColumnKey(diagnostic.column_name);
      if (!key) return;
      grouped.set(key, [...(grouped.get(key) ?? []), diagnostic.message]);
    });
    return grouped;
  }, [validation]);

  const visibleMappingColumns = useMemo(() => {
    if (!tableDetail) return [];
    const query = lower(mappingSearch);
    return tableDetail.columns.filter((column) => {
      const sourceName = mapping[column.name] ?? "";
      const sourceColumn = sourceColumnsByName.get(sourceName);
      const hasIssue =
        diagnosticsByColumn.has(diagnosticColumnKey(column.name)) ||
        duplicateSources.includes(sourceName);
      const matchesQuery =
        !query ||
        [
          column.name,
          column.logical_type,
          column.null_policy,
          column.aliases.join(" "),
          sourceName,
          sourceColumn?.sample_values.map(formatValue).join(" ") ?? "",
        ]
          .join(" ")
          .toLowerCase()
          .includes(query);
      const matchesFilter =
        mappingFilter === "all" ||
        (mappingFilter === "required" && column.required) ||
        (mappingFilter === "unmapped" && !sourceName) ||
        (mappingFilter === "mapped" && Boolean(sourceName)) ||
        (mappingFilter === "issues" && hasIssue);
      return matchesQuery && matchesFilter;
    });
  }, [diagnosticsByColumn, duplicateSources, mapping, mappingFilter, mappingSearch, sourceColumnsByName, tableDetail]);

  const unmappedSourceColumns = useMemo(() => {
    if (!sourcePreview) return [];
    const used = new Set(Object.values(mapping).filter(Boolean));
    return sourcePreview.columns.filter((column) => !used.has(column.name));
  }, [mapping, sourcePreview]);

  const validationHasErrors = validation?.diagnostics.some((diagnostic) => diagnostic.severity === "error") ?? false;

  // A step is navigable only once its inputs exist, so the sidebar cannot jump
  // the operator into an empty mapping or validation view.
  const stepReachable = useMemo<Record<WizardStep, boolean>>(() => {
    const hasSource = Boolean(sourcePreview && selectedTable);
    return {
      dataset: true,
      source: Boolean(selectedTable),
      mapping: hasSource && Boolean(tableDetail),
      validate: hasSource,
    };
  }, [selectedTable, sourcePreview, tableDetail]);

  function goToStep(target: WizardStep) {
    if (stepReachable[target]) setStep(target);
  }

  function resetDerivedArtifacts() {
    setValidation(null);
    setExportContent("");
    setCopied(false);
  }

  // Apply a freshly loaded client table. Clearing the mapping is essential: a
  // mapping built against a previous source would reference columns that may not
  // exist in the new table and fail at validation.
  function applyLoadedSource(preview: SourcePreview, connector: "file" | "path" | "duckdb") {
    setSourcePreview(preview);
    setLoadedConnector(connector);
    setMapping({});
    resetDerivedArtifacts();
    setPreviewMode("columns");
    setNotice(null);
  }

  function selectTable(table: InputTableSummary) {
    setSelectedTable(table);
    setMapping({});
    resetDerivedArtifacts();
  }

  function startOver() {
    setSelectedTable(null);
    setTableDetail(null);
    setSourcePreview(null);
    setLoadedConnector(null);
    setMapping({});
    resetDerivedArtifacts();
    setError(null);
    setNotice(null);
    setDatasetSearch("");
    setMappingSearch("");
    setMappingFilter("all");
    setStep("dataset");
  }

  async function handleImportMapping(content: string) {
    if (!content.trim()) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await importMapping({ content });
      // InputTableDetail is a superset of InputTableSummary, so it can seed both
      // the selection and the detail without round-tripping through the list.
      const detail = await getTable(result.target_package, result.target_table_id);
      setSelectedTable(detail);
      setTableDetail(detail);
      setMapping(result.mapping);
      resetDerivedArtifacts();
      if (result.unknown_columns.length) {
        // Successful import with a caveat — a warning, not an error.
        setNotice(
          `Imported mapping; ignored fields not in the target contract: ${result.unknown_columns.join(", ")}`,
        );
      }
      setStep(sourcePreview ? "mapping" : "source");
    } catch (exc) {
      setError(String(exc));
    } finally {
      setBusy(false);
    }
  }

  function handleImportFile(file: File) {
    const reader = new FileReader();
    reader.onload = () => void handleImportMapping(String(reader.result ?? ""));
    reader.onerror = () => setError("Could not read the mapping file");
    reader.readAsText(file);
  }

  async function handleUpload(file: File) {
    setBusy(true);
    setError(null);
    try {
      const preview = await uploadSource(file);
      applyLoadedSource(preview, "file");
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
      applyLoadedSource(preview, "path");
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
      const attach_files = duckAttachPath ? { client_table: duckAttachPath } : undefined;
      const preview = await loadSourceDuckDb({
        database_path: duckDatabase,
        query: duckQuery,
        attach_files,
      });
      applyLoadedSource(preview, "duckdb");
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
      resetDerivedArtifacts();
      setMappingFilter("all");
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
      setExportContent("");
      setCopied(false);
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
        source_connector: loadedConnector ?? "file",
        lineage_source_system: lineageSystem,
      });
      setExportContent(response.content);
      setExportFilename(response.filename);
      setCopied(false);
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

  async function copyExport() {
    if (!exportContent) return;
    await navigator.clipboard.writeText(exportContent);
    setCopied(true);
    if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
    copyTimerRef.current = setTimeout(() => setCopied(false), 2000);
  }

  function renderPreviewRows(columns: string[], rows: Record<string, unknown>[]) {
    return (
      <div className="table-frame">
        <table className="data-table data-table-compact">
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {columns.map((column) => (
                  <td key={column}>{formatValue(row[column])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  function renderSourceColumnProfile(columns: SourceColumnPreview[]) {
    return (
      <div className="table-frame">
        <table className="data-table">
          <thead>
            <tr>
              <th>Source column</th>
              <th>Arrow type</th>
              <th className="numeric">Nulls</th>
              <th className="numeric">Distinct</th>
              <th>Sample values</th>
            </tr>
          </thead>
          <tbody>
            {columns.map((column) => (
              <tr key={column.name}>
                <td className="mono strong">{column.name}</td>
                <td>{column.arrow_type}</td>
                <td className="numeric">{column.null_count.toLocaleString()}</td>
                <td className="numeric">{column.distinct_count?.toLocaleString() ?? "-"}</td>
                <td className="sample-cell">{column.sample_values.map(formatValue).join(", ") || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <ClipboardList aria-hidden="true" className="brand-icon" />
          </div>
          <div>
            <h1>Onboarding Mapper</h1>
            <p>Column contracts for capital inputs</p>
          </div>
        </div>

        <nav className="step-list" aria-label="Workflow">
          {STEPS.map((item, index) => {
            const reachable = stepReachable[item.id];
            const isActive = step === item.id;
            return (
              <button
                key={item.id}
                type="button"
                className={`step-item ${isActive ? "active" : ""} ${index < stepIndex ? "done" : ""}`}
                onClick={() => goToStep(item.id)}
                disabled={!reachable}
                aria-current={isActive ? "step" : undefined}
                aria-disabled={!reachable}
              >
                <span className="step-index">{index + 1}</span>
                <span className="step-copy">
                  <strong>{item.title}</strong>
                  <span>{item.subtitle}</span>
                </span>
              </button>
            );
          })}
        </nav>

        <div className="sidebar-summary">
          <span>Current run</span>
          <dl>
            <div>
              <dt>Target</dt>
              <dd>{selectedTable ? selectedTable.label : "Not selected"}</dd>
            </div>
            <div>
              <dt>Rows</dt>
              <dd>{sourcePreview ? sourcePreview.row_count.toLocaleString() : "-"}</dd>
            </div>
            <div>
              <dt>Required mapped</dt>
              <dd>
                {mappedRequired.total ? `${mappedRequired.done}/${mappedRequired.total}` : "-"}
              </dd>
            </div>
          </dl>
          <button type="button" className="btn btn-secondary btn-small start-over" onClick={startOver}>
            Start over
          </button>
        </div>
      </aside>

      <main className="main" aria-busy={busy}>
        {busy ? (
          <div className="busy-overlay" role="status" aria-live="polite">
            <span className="spinner" aria-hidden="true" />
            <span>Working…</span>
          </div>
        ) : null}
        <header className="page-header">
          <div>
            <span className="eyebrow">FRTB client onboarding</span>
            <h2>{STEPS.find((item) => item.id === step)?.title}</h2>
            <p>{STEPS.find((item) => item.id === step)?.subtitle}</p>
          </div>
          <div className="status-strip" aria-label="Workflow status">
            <span className={selectedTable ? "status-pill complete" : "status-pill"}>
              {selectedTable ? <CheckCircle2 aria-hidden="true" className="icon" /> : <Circle aria-hidden="true" className="icon" />}
              Target
            </span>
            <span className={sourcePreview ? "status-pill complete" : "status-pill"}>
              {sourcePreview ? <CheckCircle2 aria-hidden="true" className="icon" /> : <Circle aria-hidden="true" className="icon" />}
              Source
            </span>
            <span className={mappedRequired.total && mappedRequired.done === mappedRequired.total ? "status-pill complete" : "status-pill"}>
              {mappedRequired.total && mappedRequired.done === mappedRequired.total ? (
                <CheckCircle2 aria-hidden="true" className="icon" />
              ) : (
                <Circle aria-hidden="true" className="icon" />
              )}
              Mapping
            </span>
            <span className={validation ? "status-pill complete" : "status-pill"}>
              {validation ? <CheckCircle2 aria-hidden="true" className="icon" /> : <Circle aria-hidden="true" className="icon" />}
              Validation
            </span>
          </div>
        </header>

        {error ? (
          <div className="alert error" role="alert" aria-live="assertive">
            {error}
          </div>
        ) : null}

        {notice ? (
          <div className="alert warning" role="status" aria-live="polite">
            {notice}
          </div>
        ) : null}

        {step === "dataset" ? (
          <section className="panel">
            <div className="panel-header">
              <div>
                <strong>Select canonical input table</strong>
                <span>{filteredTables.length} of {tables.length} contracts shown</span>
              </div>
              <div className="header-controls">
                <div className="search-control">
                  <label htmlFor="dataset-search">Search</label>
                  <div className="input-with-icon">
                    <Search aria-hidden="true" className="icon" />
                    <input
                      id="dataset-search"
                      value={datasetSearch}
                      onChange={(event) => setDatasetSearch(event.target.value)}
                      placeholder="Component, package, table, risk class"
                    />
                  </div>
                </div>
                <label className="btn btn-secondary btn-small import-control">
                  Import mapping
                  <input
                    type="file"
                    hidden
                    accept=".yaml,.yml,.toml,.json"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) handleImportFile(file);
                      event.target.value = "";
                    }}
                  />
                </label>
              </div>
            </div>
            <div className="panel-body">
              <div className="segmented-control" aria-label="Component filter">
                {COMPONENTS.map((component) => (
                  <button
                    key={component}
                    type="button"
                    className={componentFilter === component ? "active" : ""}
                    onClick={() => setComponentFilter(component)}
                  >
                    {component}
                  </button>
                ))}
              </div>

              <div className="table-frame">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Component</th>
                      <th>Canonical table</th>
                      <th>Package</th>
                      <th className="numeric">Required</th>
                      <th className="numeric">Columns</th>
                      <th>Risk lens</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {filteredTables.map((table) => {
                      const selected = selectedTable ? tableKey(selectedTable) === tableKey(table) : false;
                      return (
                        <tr key={tableKey(table)} className={selected ? "selected-row" : ""}>
                          <td>
                            <span className="badge component">{table.component}</span>
                          </td>
                          <td>
                            <div className="cell-title">{table.label}</div>
                            <div className="cell-note">{table.description}</div>
                          </td>
                          <td className="mono">{table.package}.{table.id}</td>
                          <td className="numeric">{table.required_column_count}</td>
                          <td className="numeric">{table.column_count}</td>
                          <td>{[table.sbm_risk_class, table.sbm_risk_measure].filter(Boolean).join(" / ") || "-"}</td>
                          <td className="row-action">
                            <button
                              type="button"
                              className="btn btn-secondary btn-small"
                              title={selected ? "Selected contract" : "Select contract"}
                              onClick={() => selectTable(table)}
                            >
                              {selected ? <Check aria-hidden="true" className="icon" /> : <ArrowRight aria-hidden="true" className="icon" />}
                              {selected ? "Selected" : "Select"}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {tableDetail ? (
                <div className="detail-band">
                  <div>
                    <span className="eyebrow">Selected contract</span>
                    <h3>{tableDetail.label}</h3>
                    <p>{tableDetail.description}</p>
                  </div>
                  <div className="metric-row">
                    <div>
                      <strong>{tableDetail.required_column_count}</strong>
                      <span>Required fields</span>
                    </div>
                    <div>
                      <strong>{tableDetail.column_count}</strong>
                      <span>Total fields</span>
                    </div>
                    <div>
                      <strong>{tableDetail.component}</strong>
                      <span>Component</span>
                    </div>
                  </div>
                </div>
              ) : null}

              <div className="footer-actions">
                <span />
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={!selectedTable}
                  onClick={() => setStep("source")}
                >
                  <ArrowRight aria-hidden="true" className="icon" />
                  Continue to source
                </button>
              </div>
            </div>
          </section>
        ) : null}

        {step === "source" ? (
          <section className="panel">
            <div className="panel-header">
              <div>
                <strong>Load client dataset</strong>
                <span>{selectedTable ? selectedTable.label : "Select a target contract first"}</span>
              </div>
              {sourcePreview ? <span className="badge success">{sourcePreview.row_count.toLocaleString()} rows loaded</span> : null}
            </div>
            <div className="panel-body source-layout">
              <div className="source-loader">
                <div className="segmented-control full" aria-label="Source type">
                  {(["upload", "path", "duckdb"] as const).map((tab) => (
                    <button
                      key={tab}
                      type="button"
                      className={sourceTab === tab ? "active" : ""}
                      onClick={() => setSourceTab(tab)}
                    >
                      {tab === "upload" ? (
                        <UploadCloud aria-hidden="true" className="icon" />
                      ) : tab === "path" ? (
                        <FolderOpen aria-hidden="true" className="icon" />
                      ) : (
                        <Database aria-hidden="true" className="icon" />
                      )}
                      {tab === "upload" ? "Upload" : tab === "path" ? "Server path" : "DuckDB"}
                    </button>
                  ))}
                </div>

                {sourceTab === "upload" ? (
                  <label
                    className="dropzone"
                    role="button"
                    tabIndex={0}
                    aria-label="Upload client file: CSV, Parquet, or Arrow IPC"
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        uploadInputRef.current?.click();
                      }
                    }}
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={(event) => {
                      event.preventDefault();
                      const file = event.dataTransfer.files?.[0];
                      if (file) void handleUpload(file);
                    }}
                  >
                    <input
                      ref={uploadInputRef}
                      type="file"
                      hidden
                      accept=".csv,.parquet,.pq,.arrow,.ipc"
                      onChange={(event) => {
                        const file = event.target.files?.[0];
                        if (file) void handleUpload(file);
                      }}
                    />
                    <UploadCloud aria-hidden="true" className="dropzone-icon" />
                    <strong>Drop or choose CSV, Parquet, or Arrow IPC</strong>
                    <span>Loaded locally for this browser session.</span>
                  </label>
                ) : null}

                {sourceTab === "path" ? (
                  <>
                    <div className="field">
                      <label htmlFor="path">Absolute or repository-relative path</label>
                      <input
                        id="path"
                        value={pathValue}
                        onChange={(event) => setPathValue(event.target.value)}
                        placeholder="/data/client/drc_positions.parquet"
                      />
                    </div>
                    <button type="button" className="btn btn-primary" disabled={busy || !pathValue} onClick={() => void handleLoadPath()}>
                      <FolderOpen aria-hidden="true" className="icon" />
                      Load file
                    </button>
                  </>
                ) : null}

                {sourceTab === "duckdb" ? (
                  <>
                    <div className="field">
                      <label htmlFor="duckdb">Database path</label>
                      <input id="duckdb" value={duckDatabase} onChange={(event) => setDuckDatabase(event.target.value)} />
                    </div>
                    <div className="field">
                      <label htmlFor="attach">Attach file as `client_table`</label>
                      <input
                        id="attach"
                        value={duckAttachPath}
                        onChange={(event) => setDuckAttachPath(event.target.value)}
                        placeholder="/data/client/positions.parquet"
                      />
                    </div>
                    <div className="field">
                      <label htmlFor="query">SQL query</label>
                      <textarea id="query" rows={6} value={duckQuery} onChange={(event) => setDuckQuery(event.target.value)} />
                    </div>
                    <button type="button" className="btn btn-primary" disabled={busy || !duckQuery} onClick={() => void handleLoadDuckDb()}>
                      <Play aria-hidden="true" className="icon" />
                      Run query
                    </button>
                  </>
                ) : null}
              </div>

              <div className="source-preview">
                {sourcePreview ? (
                  <>
                    <div className="metric-row">
                      <div>
                        <strong>{sourcePreview.row_count.toLocaleString()}</strong>
                        <span>Rows</span>
                      </div>
                      <div>
                        <strong>{sourcePreview.columns.length}</strong>
                        <span>Source columns</span>
                      </div>
                      <div>
                        <strong>{tableDetail?.column_count ?? "-"}</strong>
                        <span>Target columns</span>
                      </div>
                      <div>
                        <strong>{mappedRequired.total || "-"}</strong>
                        <span>Required target fields</span>
                      </div>
                    </div>
                    <div className="preview-toolbar">
                      <div className="segmented-control">
                        <button type="button" className={previewMode === "columns" ? "active" : ""} onClick={() => setPreviewMode("columns")}>
                          <Columns3 aria-hidden="true" className="icon" />
                          Column profile
                        </button>
                        <button type="button" className={previewMode === "rows" ? "active" : ""} onClick={() => setPreviewMode("rows")}>
                          <Table2 aria-hidden="true" className="icon" />
                          Row preview
                        </button>
                      </div>
                    </div>
                    {previewMode === "columns"
                      ? renderSourceColumnProfile(sourcePreview.columns)
                      : renderPreviewRows(sourcePreview.columns.map((column) => column.name), sourcePreview.preview_rows)}
                  </>
                ) : (
                  <div className="empty-state">
                    <strong>No source loaded</strong>
                    <span>Load a file, path, or DuckDB result to inspect fields before mapping.</span>
                  </div>
                )}
              </div>
            </div>
            <div className="panel-body panel-footer">
              <button type="button" className="btn btn-secondary" onClick={() => setStep("dataset")}>
                <ArrowLeft aria-hidden="true" className="icon" />
                Back
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={!sourcePreview || !selectedTable || busy}
                onClick={() => void handleSuggestMapping()}
              >
                <WandSparkles aria-hidden="true" className="icon" />
                Auto-map columns
              </button>
            </div>
          </section>
        ) : null}

        {step === "mapping" && tableDetail && sourcePreview ? (
          <section className="panel">
            <div className="panel-header">
              <div>
                <strong>Map client columns to canonical fields</strong>
                <span>{tableDetail.label}</span>
              </div>
              <div className="toolbar">
                <button type="button" className="btn btn-secondary btn-small" disabled={busy} onClick={() => void handleSuggestMapping()}>
                  <RefreshCw aria-hidden="true" className="icon" />
                  Re-suggest
                </button>
                <button type="button" className="btn btn-secondary btn-small" title="Clear all mappings" onClick={() => setMapping({})}>
                  <Trash2 aria-hidden="true" className="icon" />
                  Clear
                </button>
              </div>
            </div>

            <div className="panel-body">
              <div className="mapping-command-row">
                <div className="progress-card">
                  <div>
                    <strong>{mappedRequired.done}/{mappedRequired.total}</strong>
                    <span>Required fields mapped</span>
                  </div>
                  <div className="progress-track">
                    <span style={{ width: `${mappedRequired.total ? (mappedRequired.done / mappedRequired.total) * 100 : 0}%` }} />
                  </div>
                </div>
                <div className="progress-card">
                  <div>
                    <strong>{mappedTotal.done}/{mappedTotal.total}</strong>
                    <span>Total fields mapped</span>
                  </div>
                  <div className="progress-track neutral">
                    <span style={{ width: `${mappedTotal.total ? (mappedTotal.done / mappedTotal.total) * 100 : 0}%` }} />
                  </div>
                </div>
                <div className="search-control grow">
                  <label htmlFor="mapping-search">Find field</label>
                  <div className="input-with-icon">
                    <Search aria-hidden="true" className="icon" />
                    <input
                      id="mapping-search"
                      value={mappingSearch}
                      onChange={(event) => setMappingSearch(event.target.value)}
                      placeholder="Canonical, source, alias, sample value"
                    />
                  </div>
                </div>
                <div className="field compact">
                  <label htmlFor="mapping-filter">Show</label>
                  <select id="mapping-filter" value={mappingFilter} onChange={(event) => setMappingFilter(event.target.value as MappingFilter)}>
                    <option value="all">All fields</option>
                    <option value="required">Required only</option>
                    <option value="unmapped">Unmapped</option>
                    <option value="mapped">Mapped</option>
                    <option value="issues">Issues</option>
                  </select>
                </div>
              </div>

              {mappedRequired.missing.length ? (
                <div className="alert warning">
                  <strong>{mappedRequired.missing.length} required fields still unmapped:</strong>{" "}
                  {mappedRequired.missing.map((column) => column.name).join(", ")}
                </div>
              ) : null}
              {duplicateSources.length ? (
                <div className="alert warning">
                  <strong>Duplicate source use:</strong> {duplicateSources.join(", ")} mapped to multiple canonical fields.
                </div>
              ) : null}

              <div className="mapping-layout">
                <div className="table-frame tall">
                  <table className="data-table mapping-table">
                    <thead>
                      <tr>
                        <th>Status</th>
                        <th>Canonical field</th>
                        <th>Client source column</th>
                        <th>Source profile</th>
                        <th>Diagnostics</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleMappingColumns.map((column) => {
                        const sourceName = mapping[column.name] ?? "";
                        const sourceColumn = sourceColumnsByName.get(sourceName);
                        const columnDiagnostics = diagnosticsByColumn.get(diagnosticColumnKey(column.name)) ?? [];
                        const isDuplicate = duplicateSources.includes(sourceName);
                        return (
                          <tr key={column.name}>
                            <td>
                              <span className={`badge ${sourceName ? "success" : column.required ? "danger" : "optional"}`}>
                                {sourceName ? "Mapped" : column.required ? "Required" : "Optional"}
                              </span>
                            </td>
                            <td>
                              <div className="cell-title mono">{column.name}</div>
                              <div className="cell-note">
                                {column.logical_type} / {column.null_policy}
                              </div>
                              {column.aliases.length ? <div className="cell-note">Aliases: {column.aliases.join(", ")}</div> : null}
                            </td>
                            <td>
                              <select
                                value={sourceName}
                                onChange={(event) => {
                                  setMapping((current) => ({
                                    ...current,
                                    [column.name]: event.target.value || null,
                                  }));
                                  resetDerivedArtifacts();
                                }}
                              >
                                <option value="">Unmapped</option>
                                {sourcePreview.columns.map((sourceColumnOption) => (
                                  <option key={sourceColumnOption.name} value={sourceColumnOption.name}>
                                    {sourceColumnOption.name}
                                  </option>
                                ))}
                              </select>
                            </td>
                            <td>
                              {sourceColumn ? (
                                <>
                                  <div className="cell-title">{sourceColumn.arrow_type}</div>
                                  <div className="cell-note">
                                    {sourceColumn.null_count.toLocaleString()} nulls
                                    {sourceColumn.distinct_count !== null && sourceColumn.distinct_count !== undefined
                                      ? ` / ${sourceColumn.distinct_count.toLocaleString()} distinct`
                                      : ""}
                                  </div>
                                  <div className="cell-note sample-cell">{sourceColumn.sample_values.map(formatValue).join(", ") || "-"}</div>
                                </>
                              ) : (
                                <span className="muted">No source selected</span>
                              )}
                            </td>
                            <td>
                              {isDuplicate ? <div className="issue-note">Source used more than once.</div> : null}
                              {columnDiagnostics.length ? columnDiagnostics.map((message) => <div key={message} className="issue-note">{message}</div>) : null}
                              {!isDuplicate && !columnDiagnostics.length ? <span className="muted">-</span> : null}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                <aside className="side-panel">
                  <div className="side-panel-header">
                    <strong>Unmapped source columns</strong>
                    <span>{unmappedSourceColumns.length}</span>
                  </div>
                  <div className="source-inventory">
                    {unmappedSourceColumns.map((column) => (
                      <div key={column.name} className="source-chip">
                        <strong>{column.name}</strong>
                        <span>{column.arrow_type}</span>
                      </div>
                    ))}
                    {!unmappedSourceColumns.length ? <div className="empty-inline">Every source column is used.</div> : null}
                  </div>
                </aside>
              </div>
            </div>

            <div className="panel-body panel-footer">
              <button type="button" className="btn btn-secondary" onClick={() => setStep("source")}>
                <ArrowLeft aria-hidden="true" className="icon" />
                Back
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={busy || mappedRequired.done < mappedRequired.total}
                onClick={() => void handleValidate()}
              >
                <CheckCircle2 aria-hidden="true" className="icon" />
                Validate mapping
              </button>
            </div>
          </section>
        ) : null}

        {step === "validate" ? (
          <section className="panel">
            <div className="panel-header">
              <div>
                <strong>Validation and export</strong>
                <span>{selectedTable ? selectedTable.label : "No target selected"}</span>
              </div>
              <div className="toolbar">
                <select value={exportFormat} onChange={(event) => setExportFormat(event.target.value as "yaml" | "toml" | "json")}>
                  <option value="yaml">YAML</option>
                  <option value="toml">TOML</option>
                  <option value="json">JSON</option>
                </select>
                <button type="button" className="btn btn-secondary btn-small" disabled={busy || !validation} onClick={() => void handleExport()}>
                  <FileInput aria-hidden="true" className="icon" />
                  Generate
                </button>
                <button type="button" className="btn btn-primary btn-small" disabled={!exportContent} onClick={downloadExport}>
                  <Download aria-hidden="true" className="icon" />
                  Download
                </button>
              </div>
            </div>
            <div className="panel-body">
              {validation ? (
                <>
                  <div className={validationHasErrors ? "result-banner blocked" : "result-banner"}>
                    <div>
                      <strong>{validationHasErrors ? "Validation needs attention" : "Validation preview completed"}</strong>
                      <span>
                        {validation.accepted_rows.toLocaleString()} accepted / {validation.rejected_rows.toLocaleString()} rejected rows
                      </span>
                    </div>
                    <div className="metric-row compact-row">
                      <div>
                        <strong>{validation.batch_built ? "Yes" : "No"}</strong>
                        <span>Batch built</span>
                      </div>
                      <div>
                        <strong>{validation.input_table_hash?.slice(0, 12) ?? "-"}</strong>
                        <span>Table hash</span>
                      </div>
                    </div>
                  </div>

                  {validation.diagnostics.length ? (
                    <div className="table-frame">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Severity</th>
                            <th>Code</th>
                            <th>Column</th>
                            <th>Row</th>
                            <th>Message</th>
                          </tr>
                        </thead>
                        <tbody>
                          {validation.diagnostics.map((diagnostic, index) => (
                            <tr key={`${diagnostic.code}-${index}`}>
                              <td>
                                <span className={`badge ${diagnostic.severity === "error" ? "danger" : "warning"}`}>
                                  {diagnostic.severity}
                                </span>
                              </td>
                              <td className="mono">{diagnostic.code}</td>
                              <td>{diagnostic.column_name ?? "-"}</td>
                              <td>{diagnostic.row_id ?? "-"}</td>
                              <td>{diagnostic.message}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="alert success">Normalization completed without adapter diagnostics.</div>
                  )}

                  <div className="section-header">
                    <h3>Accepted preview</h3>
                    <span>{validation.preview_rows.length} rows shown</span>
                  </div>
                  {renderPreviewRows(validation.preview_columns, validation.preview_rows)}
                </>
              ) : (
                <div className="empty-state">
                  <strong>No validation result</strong>
                  <span>Return to mapping and validate once required fields are mapped.</span>
                </div>
              )}

              <div className="export-grid">
                <div className="field">
                  <label htmlFor="lineage">Lineage source system</label>
                  <input id="lineage" value={lineageSystem} onChange={(event) => setLineageSystem(event.target.value)} />
                </div>
                <div className="field">
                  <label htmlFor="format">Artifact format</label>
                  <select id="format" value={exportFormat} onChange={(event) => setExportFormat(event.target.value as "yaml" | "toml" | "json")}>
                    <option value="yaml">YAML</option>
                    <option value="toml">TOML</option>
                    <option value="json">JSON</option>
                  </select>
                </div>
              </div>

              {exportContent ? (
                <>
                  <div className="section-header">
                    <h3>Mapping artifact</h3>
                    <button type="button" className="btn btn-secondary btn-small" onClick={() => void copyExport()}>
                      <Copy aria-hidden="true" className="icon" />
                      {copied ? "Copied" : "Copy"}
                    </button>
                  </div>
                  <pre className="code-block">{exportContent}</pre>
                </>
              ) : null}

              <div className="footer-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setStep("mapping")}>
                  <ArrowLeft aria-hidden="true" className="icon" />
                  Back to mapping
                </button>
                <button type="button" className="btn btn-primary" disabled={!exportContent} onClick={downloadExport}>
                  <Download aria-hidden="true" className="icon" />
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
