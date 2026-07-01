import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, KeyboardEvent, ReactNode } from "react";
import { formatMoney, getGrid, getInspector, getMetadata, getRun } from "./api";
import type { AttributionRow, AuditRow, Diagnostic, DimensionNode, GridColumn, GridRow, GridView, InspectorView, MetadataView, RunOverview } from "./types";

type Framework = "SA" | "IMA" | "CVA";
type Scenario = "Binding" | "Base" | "High" | "Low";

const RUN_ID = "demo-suite-001";
const FRAMEWORKS: Framework[] = ["SA", "IMA", "CVA"];
const SCENARIOS: Scenario[] = ["Binding", "Base", "High", "Low"];
const INITIAL_EXPANDED = ["sa", "sa-sbm", "sa-drc", "sa-rrao", "ima", "ima-desk-rates-desk"];
const DEFAULT_NODE_ID = "toh";

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function useCache() {
  return useRef(new Map<string, unknown>());
}

function cacheGet<T>(cache: Map<string, unknown>, key: string): T | null {
  return (cache.get(key) as T | undefined) ?? null;
}

function formatPercent(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function formatCell(row: GridRow, column: GridColumn): ReactNode {
  const value = row[column.key as keyof GridRow];
  if (column.key === "status" && row.status === "no_data") return <span className="state-chip muted">no data</span>;
  if (column.key === "pla_zone" || column.key === "backtest_zone") return <ZoneChip value={typeof value === "string" ? value : null} />;
  if (column.kind === "percent") return formatPercent(typeof value === "number" ? value : null);
  if (column.kind === "decimal") return typeof value === "number" ? value.toFixed(2) : "—";
  if (column.kind === "signed") return <span className="muted-cell">—</span>;
  if (typeof value === "number") return formatMoney(value, row.currency);
  if (typeof value === "string" && value.length > 0) return value;
  return "—";
}

function signClass(value: number | null | undefined): string {
  if (value == null || value === 0) return "";
  return value > 0 ? "signed-up" : "signed-down";
}

function ZoneChip({ value }: { value: string | null }) {
  if (!value) return <span className="muted-cell">—</span>;
  return <span className={`zone-chip zone-${value.toLowerCase()}`}>{value}</span>;
}

function rowMatches(row: GridRow, query: string): boolean {
  if (!query.trim()) return true;
  const haystack = `${row.label} ${row.component} ${row.row_type} ${row.group_path.join(" ")}`.toLowerCase();
  return haystack.includes(query.trim().toLowerCase());
}

function visibleRows(rows: GridRow[], expanded: Set<string>, query: string): GridRow[] {
  const byId = new Map(rows.map((row) => [row.row_id, row]));
  return rows.filter((row) => {
    if (!rowMatches(row, query)) return false;
    let parent = row.parent_id ? byId.get(row.parent_id) : null;
    while (parent) {
      if (!expanded.has(parent.row_id)) return false;
      parent = parent.parent_id ? byId.get(parent.parent_id) ?? null : null;
    }
    return true;
  });
}

function childrenByParent(rows: GridRow[]): Map<string, GridRow[]> {
  const map = new Map<string, GridRow[]>();
  for (const row of rows) {
    if (!row.parent_id) continue;
    const children = map.get(row.parent_id) ?? [];
    children.push(row);
    map.set(row.parent_id, children);
  }
  return map;
}

function App() {
  const cache = useCache();
  const [overview, setOverview] = useState<RunOverview | null>(null);
  const [metadata, setMetadata] = useState<MetadataView | null>(null);
  const [grid, setGrid] = useState<GridView | null>(null);
  const [inspector, setInspector] = useState<InspectorView | null>(null);
  const [framework, setFramework] = useState<Framework>("SA");
  const [scenario, setScenario] = useState<Scenario>("Binding");
  const [selectedNodeId, setSelectedNodeId] = useState<string>(DEFAULT_NODE_ID);
  const [selectedRowId, setSelectedRowId] = useState<string>("sa");
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set(INITIAL_EXPANDED));
  const [query, setQuery] = useState("");
  const [activeInspectorTab, setActiveInspectorTab] = useState("attribution");
  const [loadingZone, setLoadingZone] = useState<string | null>("run");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const runKey = `run:${RUN_ID}:${selectedNodeId}`;
    const metadataKey = `metadata:${RUN_ID}`;
    const cachedRun = cacheGet<RunOverview>(cache.current, runKey);
    const cachedMetadata = cacheGet<MetadataView>(cache.current, metadataKey);
    if (cachedRun && cachedMetadata) {
      setOverview(cachedRun);
      setMetadata(cachedMetadata);
      setLoadingZone(null);
      return () => controller.abort();
    }
    setLoadingZone("run");
    Promise.all([
      getRun(RUN_ID, selectedNodeId, controller.signal),
      getMetadata(RUN_ID, controller.signal),
    ])
      .then(([runPayload, metadataPayload]) => {
        cache.current.set(runKey, runPayload);
        cache.current.set(metadataKey, metadataPayload);
        setOverview(runPayload);
        setMetadata(metadataPayload);
        setError(null);
      })
      .catch((fetchError: unknown) => {
        if (!isAbort(fetchError)) setError(String(fetchError));
      })
      .finally(() => setLoadingZone(null));
    return () => controller.abort();
  }, [cache, selectedNodeId]);

  useEffect(() => {
    const controller = new AbortController();
    const key = `grid:${RUN_ID}:${selectedNodeId}:${framework}:${scenario}`;
    const cachedGrid = cacheGet<GridView>(cache.current, key);
    if (cachedGrid) {
      setGrid(cachedGrid);
      setSelectedRowId(cachedGrid.rows[0]?.row_id ?? "");
      return () => controller.abort();
    }
    setLoadingZone("grid");
    getGrid(RUN_ID, framework, scenario, selectedNodeId, controller.signal)
      .then((payload) => {
        cache.current.set(key, payload);
        setGrid(payload);
        setSelectedRowId(payload.rows[0]?.row_id ?? "");
        setExpanded(new Set(INITIAL_EXPANDED.concat(payload.rows.filter((row) => row.level <= 1).map((row) => row.row_id))));
        setError(null);
      })
      .catch((fetchError: unknown) => {
        if (!isAbort(fetchError)) setError(String(fetchError));
      })
      .finally(() => setLoadingZone(null));
    return () => controller.abort();
  }, [cache, framework, scenario, selectedNodeId]);

  useEffect(() => {
    if (!selectedRowId) return;
    const controller = new AbortController();
    const key = `inspector:${RUN_ID}:${selectedNodeId}:${scenario}:${selectedRowId}`;
    const cachedInspector = cacheGet<InspectorView>(cache.current, key);
    if (cachedInspector) {
      setInspector(cachedInspector);
      setActiveInspectorTab(cachedInspector.tabs[0]?.key ?? "attribution");
      return () => controller.abort();
    }
    setLoadingZone("inspector");
    getInspector(RUN_ID, selectedRowId, scenario, selectedNodeId, controller.signal)
      .then((payload) => {
        cache.current.set(key, payload);
        setInspector(payload);
        setActiveInspectorTab(payload.tabs[0]?.key ?? "attribution");
        setError(null);
      })
      .catch((fetchError: unknown) => {
        if (!isAbort(fetchError)) setError(String(fetchError));
      })
      .finally(() => setLoadingZone(null));
    return () => controller.abort();
  }, [cache, scenario, selectedNodeId, selectedRowId]);

  const childMap = useMemo(() => childrenByParent(grid?.rows ?? []), [grid]);
  const rows = useMemo(() => visibleRows(grid?.rows ?? [], expanded, query), [expanded, grid, query]);
  const selectedRow = rows.find((row) => row.row_id === selectedRowId) ?? null;
  const selectedNode = metadata?.dimensions.find((node) => node.node_id === selectedNodeId) ?? null;

  function selectFramework(next: Framework) {
    setFramework(next);
    if (next !== "SA") setScenario("Binding");
  }

  function toggleExpanded(rowId: string) {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(rowId)) next.delete(rowId);
      else next.add(rowId);
      return next;
    });
  }

  function moveSelection(delta: number) {
    if (!rows.length) return;
    const currentIndex = Math.max(0, rows.findIndex((row) => row.row_id === selectedRowId));
    const nextIndex = Math.min(rows.length - 1, Math.max(0, currentIndex + delta));
    setSelectedRowId(rows[nextIndex].row_id);
  }

  function onRowKey(event: KeyboardEvent<HTMLTableRowElement>, row: GridRow) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      moveSelection(1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      moveSelection(-1);
    } else if (event.key === "ArrowRight" && childMap.has(row.row_id)) {
      event.preventDefault();
      setExpanded((current) => new Set(current).add(row.row_id));
    } else if (event.key === "ArrowLeft" && childMap.has(row.row_id)) {
      event.preventDefault();
      setExpanded((current) => {
        const next = new Set(current);
        next.delete(row.row_id);
        return next;
      });
    } else if (event.key === "Enter") {
      event.preventDefault();
      document.getElementById("audit-inspector")?.focus();
    }
  }

  const currency = overview?.currency ?? "USD";
  const regime = overview?.run.profile_id.replace(/_/g, " ") ?? "US NPR 2.0";
  const reviewCount = typeof inspector?.reconciliation.rows_needing_review === "number" ? inspector.reconciliation.rows_needing_review : 0;
  const coverage = typeof inspector?.reconciliation.coverage === "number" ? `${Math.round(inspector.reconciliation.coverage * 100)}%` : "—";

  return (
    <main className="navigator-shell">
      <CommandRibbon overview={overview} loadingZone={loadingZone} />
      <ContextBar
        framework={framework}
        scenario={scenario}
        query={query}
        regime={regime}
        selectedNode={selectedNode}
        onFramework={selectFramework}
        onScenario={setScenario}
        onQuery={setQuery}
      />
      <section className="workbench" aria-label="FRTB Navigator workbench">
        <HierarchyPanel
          nodes={metadata?.dimensions ?? []}
          selectedNodeId={selectedNodeId}
          onSelect={setSelectedNodeId}
        />
        <section className="blotter-zone" aria-label="Aggregate blotter">
          <div className="zone-head">
            <div>
              <span className="eyebrow">Zone 3 / aggregate blotter</span>
              <strong>{grid?.grouping ?? "Component > Risk Class / Bucket"}</strong>
            </div>
            <div className="zone-meta">
              <span>{selectedNode?.label ?? "Top of house"}</span>
              <span>{rows.length} rows</span>
              <span>{grid?.data_state ?? "fixture"}</span>
            </div>
          </div>
          {error ? <div className="error-strip">{error}</div> : null}
          <div className="grid-frame" role="region" aria-label="Capital aggregate grid">
            <table className="capital-grid">
              <thead>
                <tr>
                  <th className="group-col">Row group</th>
                  {(grid?.columns ?? []).map((column) => (
                    <th key={column.key}>{column.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const hasChildren = childMap.has(row.row_id);
                  const isSelected = selectedRowId === row.row_id;
                  return (
                    <tr
                      key={row.row_id}
                      tabIndex={0}
                      className={`${isSelected ? "selected" : ""} ${row.status === "no_data" ? "no-data" : ""}`}
                      onClick={() => setSelectedRowId(row.row_id)}
                      onKeyDown={(event) => onRowKey(event, row)}
                    >
                      <th className="group-col" style={{ "--level": row.level } as CSSProperties}>
                        <button className="twist" type="button" onClick={(event) => { event.stopPropagation(); if (hasChildren) toggleExpanded(row.row_id); }}>
                          {hasChildren ? (expanded.has(row.row_id) ? "▾" : "▸") : ""}
                        </button>
                        <span className={`component-code component-${row.component.toLowerCase()}`}>{row.component}</span>
                        <span>{row.label}</span>
                        {row.selected_scenario ? <span className="scenario-flag">{row.selected_scenario}</span> : null}
                      </th>
                      {(grid?.columns ?? []).map((column) => (
                        <td key={column.key} className={column.kind === "signed" ? signClass(row.delta_vs_baseline) : ""}>{formatCell(row, column)}</td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
        <section id="audit-inspector" className="inspector-zone" aria-label="Audit inspector" tabIndex={-1}>
          <div className="zone-head inspector-head">
            <div>
              <span className="eyebrow">Zone 4 / audit inspector</span>
              <strong>{inspector?.label ?? selectedRow?.label ?? "Select a row"}</strong>
            </div>
            <div className="zone-meta">
              <span>recon {coverage}</span>
              <span>{reviewCount} review</span>
              <span>{inspector?.component ?? framework}</span>
            </div>
          </div>
          <InspectorTabs inspector={inspector} activeTab={activeInspectorTab} onTab={setActiveInspectorTab} />
          <InspectorBody inspector={inspector} activeTab={activeInspectorTab} currency={currency} />
        </section>
      </section>
    </main>
  );
}

function CommandRibbon({ overview, loadingZone }: { overview: RunOverview | null; loadingZone: string | null }) {
  const currency = overview?.currency ?? "USD";
  return (
    <header className="command-ribbon">
      <div className="ribbon-left">
        <label>
          <span>Run</span>
          <select value={overview?.run.run_id ?? RUN_ID} aria-label="Run selector" disabled>
            <option>{overview?.run.label ?? RUN_ID}</option>
          </select>
        </label>
        <label>
          <span>Baseline</span>
          <select value="none" aria-label="Baseline selector" disabled>
            <option>No baseline run</option>
          </select>
        </label>
      </div>
      <div className="kpi-strip" aria-label="Top of house capital">
        <KpiCell label="Binding" value={formatMoney(overview?.binding_total, currency)} delta="—" tag={overview?.binding_side ?? "n/a"} strong />
        <KpiCell label="SA" value={formatMoney(overview?.sa_total, currency)} delta="—" />
        <KpiCell label="IMA" value={formatMoney(overview?.ima_total, currency)} delta="—" />
        <KpiCell label="CVA" value={formatMoney(overview?.cva_total, currency)} delta="—" tag="no data" />
      </div>
      <div className="ribbon-right">
        <span className={`lake-state ${loadingZone ? "loading" : ""}`}>{loadingZone ? `query ${loadingZone}` : "idle"}</span>
        <span className="shortcut">⌘K search</span>
      </div>
    </header>
  );
}

function KpiCell({ label, value, delta, tag, strong = false }: { label: string; value: string; delta: string; tag?: string; strong?: boolean }) {
  return (
    <div className={`kpi-cell ${strong ? "strong" : ""}`}>
      <span>{label}</span>
      <b>{value}</b>
      <small>{delta}</small>
      {tag ? <i>{tag}</i> : null}
    </div>
  );
}

function ContextBar({ framework, scenario, query, regime, selectedNode, onFramework, onScenario, onQuery }: { framework: Framework; scenario: Scenario; query: string; regime: string; selectedNode: DimensionNode | null; onFramework: (framework: Framework) => void; onScenario: (scenario: Scenario) => void; onQuery: (query: string) => void }) {
  return (
    <nav className="context-bar" aria-label="Navigator context">
      <div className="segmented" aria-label="Framework selector">
        {FRAMEWORKS.map((item) => (
          <button key={item} type="button" className={framework === item ? "active" : ""} onClick={() => onFramework(item)}>{item}</button>
        ))}
      </div>
      <div className="dimension-chips" aria-label="Active grouping">
        <span>{selectedNode?.dimension ?? "Scope"}</span>
        <span>{selectedNode?.label ?? "Top of house"}</span>
        <span>{selectedNode?.components.join("+") || "All"}</span>
      </div>
      <div className="scenario-toggle" aria-label="Correlation scenario selector">
        <span>Scenario:</span>
        {SCENARIOS.map((item) => (
          <button key={item} type="button" disabled={framework !== "SA"} className={scenario === item ? "active" : ""} onClick={() => onScenario(item)}>{item}</button>
        ))}
      </div>
      <label className="command-search">
        <span>Search</span>
        <input value={query} onChange={(event) => onQuery(event.target.value)} placeholder="desk, bucket, risk class" />
      </label>
      <span className="regime-label">Regime: {regime}</span>
    </nav>
  );
}

function HierarchyPanel({ nodes, selectedNodeId, onSelect }: { nodes: DimensionNode[]; selectedNodeId: string; onSelect: (nodeId: string) => void }) {
  if (!nodes.length) return <section className="hierarchy-zone" aria-label="Hierarchy"><div className="empty-state">Hierarchy metadata unavailable.</div></section>;
  return (
    <section className="hierarchy-zone" aria-label="Business hierarchy">
      <div className="zone-head">
        <div>
          <span className="eyebrow">Zone 2 / hierarchy</span>
          <strong>Business scope</strong>
        </div>
        <div className="zone-meta"><span>{nodes.length} nodes</span></div>
      </div>
      <div className="hierarchy-list" role="tree" aria-label="Hierarchy nodes">
        {nodes.map((node) => (
          <button
            key={node.node_id}
            type="button"
            role="treeitem"
            aria-selected={selectedNodeId === node.node_id}
            className={`hierarchy-row ${selectedNodeId === node.node_id ? "active" : ""}`}
            style={{ "--level": node.level } as CSSProperties}
            onClick={() => onSelect(node.node_id)}
          >
            <span className="hierarchy-type">{node.dimension}</span>
            <b>{node.label}</b>
            <small>{node.components.join(" + ") || "No components"}</small>
          </button>
        ))}
      </div>
    </section>
  );
}

function InspectorTabs({ inspector, activeTab, onTab }: { inspector: InspectorView | null; activeTab: string; onTab: (tab: string) => void }) {
  if (!inspector) return <div className="tabs"><button type="button" className="active">Attribution</button></div>;
  return (
    <div className="tabs" role="tablist">
      {inspector.tabs.map((tab) => (
        <button key={tab.key} type="button" role="tab" className={activeTab === tab.key ? "active" : ""} onClick={() => onTab(tab.key)} disabled={!tab.enabled}>
          {tab.label}{tab.badge ? <span>{tab.badge}</span> : null}
        </button>
      ))}
    </div>
  );
}

function InspectorBody({ inspector, activeTab, currency }: { inspector: InspectorView | null; activeTab: string; currency: string }) {
  if (!inspector) return <div className="empty-state">Select an aggregate row to inspect source lines.</div>;
  if (activeTab === "source") return <AuditTable rows={inspector.audit_rows} currency={currency} />;
  if (activeTab === "diagnostics") return <Diagnostics diagnostics={inspector.diagnostics} />;
  if (activeTab === "scenario") return <JsonPanel value={inspector.extras.scenario_detail} />;
  if (activeTab === "backtesting") return <JsonPanel value={inspector.extras.backtesting} />;
  return <AttributionTable rows={inspector.attribution} currency={currency} />;
}

function AttributionTable({ rows, currency }: { rows: AttributionRow[]; currency: string }) {
  if (!rows.length) return <div className="empty-state">No attribution rows for this fixture aggregate.</div>;
  return (
    <div className="inspector-table-wrap">
      <table className="inspector-table">
        <thead><tr><th>Category</th><th>Source</th><th>Method</th><th>Contribution</th><th>Status</th><th>Reason</th></tr></thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.contribution_id}>
              <td>{row.category}</td>
              <td>{row.source_level}:{row.source_id}</td>
              <td>{row.method}</td>
              <td className={signClass(row.contribution)}>{formatMoney(row.contribution, currency)}</td>
              <td><span className="state-chip">{row.reconciliation_status}</span></td>
              <td>{row.reason || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AuditTable({ rows, currency }: { rows: AuditRow[]; currency: string }) {
  return (
    <div className="inspector-table-wrap">
      <table className="inspector-table">
        <thead><tr><th>Source system</th><th>Source id</th><th>Desk</th><th>Risk class</th><th>Bucket</th><th>Metric</th><th>Value</th><th>Provenance</th></tr></thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.row_id}>
              <td>{row.source_system}</td>
              <td>{row.source_id}</td>
              <td>{row.desk_id ?? "—"}</td>
              <td>{row.risk_class ?? "—"}</td>
              <td>{row.bucket ?? "—"}</td>
              <td>{row.metric}</td>
              <td>{formatMoney(row.value, row.currency ?? currency)}</td>
              <td>{row.provenance}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Diagnostics({ diagnostics }: { diagnostics: Diagnostic[] }) {
  if (!diagnostics.length) return <div className="empty-state">No diagnostics for the selected row.</div>;
  return (
    <div className="diagnostic-list">
      {diagnostics.map((diagnostic) => (
        <div key={`${diagnostic.code}-${diagnostic.message}`} className={`diagnostic diagnostic-${diagnostic.severity}`}>
          <b>{diagnostic.code}</b>
          <span>{diagnostic.message}</span>
        </div>
      ))}
    </div>
  );
}

function JsonPanel({ value }: { value: unknown }) {
  return <pre className="json-panel">{JSON.stringify(value ?? {}, null, 2)}</pre>;
}

export default App;
