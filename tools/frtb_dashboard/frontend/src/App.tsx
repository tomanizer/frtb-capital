import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { formatMoney, getImaDesk, getNode, getRun, getSa } from "./api";
import type { AttributionRow, CapitalNode, ImaDeskView, NodeDetail, RunOverview, SaOverview } from "./types";

type ImaTab = "summary" | "imcc" | "nmrf" | "pla" | "backtest" | "attribution";
type SortKey = "absContribution" | "source" | "category";
type Density = "comfortable" | "compact";

const COMPONENT_FILTERS = ["ALL", "IMA", "SA", "SBM", "DRC", "RRAO"] as const;
const TAB_LABELS: Array<[ImaTab, string]> = [
  ["summary", "Summary"],
  ["imcc", "IMCC / ES"],
  ["nmrf", "SES & NMRF"],
  ["pla", "PLA"],
  ["backtest", "Backtesting"],
  ["attribution", "Attribution"],
];
const VIEW_MODES = [
  ["total", "Overview"],
  ["ima", "IMA"],
  ["sa", "SA"],
] as const;
const COMPONENT_COLORS: Record<string, string> = {
  ALL: "#7a8793",
  SUITE: "#22272e",
  IMA: "#2f6fed",
  SA: "#0f766e",
  SBM: "#7c5cff",
  DRC: "#bd6b00",
  RRAO: "#0f8ea8",
};

type ComponentFilter = (typeof COMPONENT_FILTERS)[number];
type TreeRow = { node: CapitalNode; depth: number };

function flattenTree(nodes: CapitalNode[], parentId: string | null = null, depth = 0): TreeRow[] {
  const children = nodes.filter((node) => node.parent_id === parentId);
  return children.flatMap((node) => [{ node, depth }, ...flattenTree(nodes, node.node_id, depth + 1)]);
}

function humanKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase())
    .replace(/\bEs\b/g, "ES")
    .replace(/\bImcc\b/g, "IMCC")
    .replace(/\bSes\b/g, "SES")
    .replace(/\bPla\b/g, "PLA")
    .replace(/\bLha\b/g, "LHA")
    .replace(/\bNmrf\b/g, "NMRF")
    .replace(/\bKs\b/g, "KS");
}

function formatValue(value: unknown, currency: string): string {
  if (value == null) return "-";
  if (typeof value === "number") {
    if (Math.abs(value) > 1000) return formatMoney(value, currency);
    if (Math.abs(value) < 10 && Math.abs(value) > 0) return value.toFixed(4);
    return value.toLocaleString();
  }
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function percent(part: number | null | undefined, total: number | null | undefined): string {
  if (!part || !total) return "-";
  return `${((part / total) * 100).toFixed(1)}%`;
}

function zoneClass(zone: unknown): string {
  const normalized = String(zone ?? "").toUpperCase();
  if (normalized === "GREEN") return "zone zone-green";
  if (normalized === "AMBER" || normalized === "ORANGE") return "zone zone-amber";
  if (normalized === "RED") return "zone zone-red";
  return "zone";
}

function ZoneBadge({ zone }: { zone: unknown }) {
  const label = String(zone ?? "-");
  return <span className={zoneClass(zone)}>{label}</span>;
}

function ComponentSwatch({ component }: { component: string }) {
  return (
    <span
      className="component-swatch"
      style={{ "--swatch": COMPONENT_COLORS[component] ?? COMPONENT_COLORS.ALL } as CSSProperties & Record<"--swatch", string>}
      aria-hidden="true"
    />
  );
}

function MiniBar({ value, total }: { value: number | null | undefined; total: number | null | undefined }) {
  const width = total && value ? Math.max(0, Math.min(100, (Math.abs(value) / Math.abs(total)) * 100)) : 0;
  return (
    <span className="mini-bar" aria-hidden="true">
      <span style={{ width: `${width}%` }} />
    </span>
  );
}

function MetricCard({
  label,
  value,
  meta,
  tone = "neutral",
}: {
  label: string;
  value: string;
  meta?: string;
  tone?: "neutral" | "blue" | "amber" | "green" | "red";
}) {
  return (
    <article className={`metric-card tone-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {meta ? <small>{meta}</small> : null}
    </article>
  );
}

function KeyValueGrid({ data, currency, skip = [] }: { data: Record<string, unknown>; currency: string; skip?: string[] }) {
  const rows = Object.entries(data).filter(([key]) => !skip.includes(key));
  if (!rows.length) return null;
  return (
    <div className="kv-grid">
      {rows.map(([key, value]) => (
        <div key={key} className="kv-row">
          <span className="kv-key">{humanKey(key)}</span>
          <span className="kv-val">{formatValue(value, currency)}</span>
        </div>
      ))}
    </div>
  );
}

function CapitalStack({
  overview,
  saOverview,
  selectedNodeId,
  onSelect,
}: {
  overview: RunOverview;
  saOverview: SaOverview | null;
  selectedNodeId: string;
  onSelect: (nodeId: string) => void;
}) {
  const suiteTotal = overview.suite_total ?? 0;
  const stackItems = [
    { id: "ima", label: "IMA", value: overview.ima_total ?? 0, tone: "stack-ima" },
    { id: "sa", label: "SA", value: overview.sa_total ?? 0, tone: "stack-sa" },
  ];

  return (
    <section className="capital-stack" aria-label="Capital stack">
      <div className="stack-header">
        <div>
          <span className="eyebrow">Capital stack</span>
          <h2>{formatMoney(suiteTotal, overview.currency)}</h2>
        </div>
        <span className="status-pill">demo-suite-001</span>
      </div>

      <div className="stack-lanes">
        {stackItems.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`stack-lane ${item.tone} ${selectedNodeId === item.id ? "active" : ""}`}
            onClick={() => onSelect(item.id)}
          >
            <span>
              <strong>{item.label}</strong>
              <small>{percent(item.value, suiteTotal)} of total</small>
            </span>
            <i style={{ width: `${suiteTotal ? (item.value / suiteTotal) * 100 : 0}%` }} />
            <b>{formatMoney(item.value, overview.currency)}</b>
          </button>
        ))}
      </div>

      {saOverview ? (
        <div className="component-ribbon" aria-label="SA components">
          {saOverview.components.map((component) => {
            const target = component.component === "SBM" ? "sa-sbm" : component.component === "DRC" ? "sa-drc" : "sa-rrao";
            return (
              <button
                key={component.component}
                type="button"
                className={selectedNodeId === target ? "active" : ""}
                onClick={() => onSelect(target)}
              >
                <span><ComponentSwatch component={component.component} />{component.component}</span>
                <MiniBar value={component.total_capital} total={saOverview.total_capital} />
                <strong>{formatMoney(component.total_capital, overview.currency)}</strong>
              </button>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}

function TreeNavigation({
  rows,
  selectedNodeId,
  query,
  componentFilter,
  onQuery,
  onFilter,
  onSelect,
}: {
  rows: TreeRow[];
  selectedNodeId: string;
  query: string;
  componentFilter: ComponentFilter;
  onQuery: (value: string) => void;
  onFilter: (value: ComponentFilter) => void;
  onSelect: (nodeId: string) => void;
}) {
  const normalizedQuery = query.trim().toLowerCase();
  const filteredRows = rows.filter(({ node }) => {
    const matchesQuery =
      !normalizedQuery ||
      `${node.label} ${node.node_type} ${node.component}`.toLowerCase().includes(normalizedQuery);
    const matchesComponent =
      componentFilter === "ALL" ||
      node.component === componentFilter ||
      (componentFilter === "SA" && ["SBM", "DRC", "RRAO"].includes(node.component));
    return matchesQuery && matchesComponent;
  });

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">F</div>
        <div>
          <h1>FRTB Capital</h1>
          <p>Desk, stack, attribution</p>
        </div>
      </div>

      <label className="search-box">
        <span>Find node</span>
        <input value={query} onChange={(event) => onQuery(event.target.value)} placeholder="Desk, DRC, PLA..." />
      </label>

      <div className="filter-chips" aria-label="Component filter">
        {COMPONENT_FILTERS.map((filter) => (
          <button
            key={filter}
            type="button"
            className={componentFilter === filter ? "active" : ""}
            onClick={() => onFilter(filter)}
          >
            <ComponentSwatch component={filter} />
            {filter}
          </button>
        ))}
      </div>

      <nav className="tree-nav" aria-label="Capital tree">
        {filteredRows.map(({ node, depth }) => (
          <button
            key={node.node_id}
            type="button"
            className={`tree-item ${selectedNodeId === node.node_id ? "active" : ""}`}
            style={{ "--depth": depth } as CSSProperties & Record<"--depth", number>}
            onClick={() => onSelect(node.node_id)}
          >
            <span>
              <strong><ComponentSwatch component={node.component} />{node.label}</strong>
              <small>{node.component} / {node.node_type.toLowerCase()}</small>
            </span>
            <b>{formatMoney(node.amount, node.currency)}</b>
          </button>
        ))}
      </nav>
    </aside>
  );
}

function CommandBar({
  selectedNodeId,
  density,
  onSelect,
  onDensity,
}: {
  selectedNodeId: string;
  density: Density;
  onSelect: (nodeId: string) => void;
  onDensity: (density: Density) => void;
}) {
  const mode = VIEW_MODES.find(([nodeId]) => selectedNodeId === nodeId)?.[0] ?? "total";
  return (
    <section className="command-bar" aria-label="Dashboard controls">
      <div className="segmented-control" aria-label="View">
        {VIEW_MODES.map(([nodeId, label]) => (
          <button
            key={nodeId}
            type="button"
            className={mode === nodeId ? "active" : ""}
            onClick={() => onSelect(nodeId)}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="segmented-control density-control" aria-label="Density">
        {(["comfortable", "compact"] as const).map((option) => (
          <button
            key={option}
            type="button"
            className={density === option ? "active" : ""}
            onClick={() => onDensity(option)}
          >
            {option === "comfortable" ? "Comfort" : "Compact"}
          </button>
        ))}
      </div>
    </section>
  );
}

function HealthStrip({ desk, overview }: { desk: ImaDeskView | null; overview: RunOverview }) {
  const plaZone = desk?.pla.zone;
  const aplZone = desk?.backtesting.apl_zone ?? desk?.backtesting.zone;
  const hplZone = desk?.backtesting.hpl_zone;
  const multiplier = desk?.summary.supervisory_multiplier;

  return (
    <section className="health-strip">
      <MetricCard label="Suite total" value={formatMoney(overview.suite_total, overview.currency)} meta={overview.run.profile_id} tone="blue" />
      <MetricCard label="IMA / SA mix" value={`${percent(overview.ima_total, overview.suite_total)} / ${percent(overview.sa_total, overview.suite_total)}`} meta="capital split" />
      <MetricCard label="PLA status" value={String(plaZone ?? "-")} meta="distribution alignment" tone={String(plaZone).toUpperCase() === "GREEN" ? "green" : "amber"} />
      <MetricCard label="Backtesting" value={`${String(aplZone ?? "-")} / ${String(hplZone ?? "-")}`} meta="APL / HPL zones" tone={String(aplZone).toUpperCase() === "GREEN" ? "green" : "amber"} />
      <MetricCard label="Multiplier" value={multiplier ? `x${multiplier}` : "-"} meta="supervisory scalar" />
    </section>
  );
}

function SummaryPanel({ data, currency }: { data: Record<string, unknown>; currency: string }) {
  return (
    <div className="detail-grid">
      <MetricCard label="Models-based capital" value={formatValue(data.models_based_capital, currency)} tone="blue" />
      <MetricCard label="IMCC" value={formatValue(data.imcc, currency)} />
      <MetricCard label="Total SES" value={formatValue(data.total_ses, currency)} />
      <MetricCard label="Binding term" value={String(data.binding_term ?? "-")} meta="capital driver" />
      <MetricCard label="Supervisory multiplier" value={data.supervisory_multiplier ? `x${data.supervisory_multiplier}` : "-"} />
    </div>
  );
}

function ImccPanel({ data, currency }: { data: Record<string, unknown>; currency: string }) {
  return (
    <div className="panel-flow">
      <div className="detail-grid">
        <MetricCard label="IMCC binding capital" value={formatValue(data.imcc, currency)} tone="blue" />
        <MetricCard label="Unconstrained LHA ES" value={formatValue(data.unconstrained_lha_es, currency)} />
        <MetricCard label="Constrained LHA ES" value={formatValue(data.constrained_lha_es, currency)} />
      </div>
      <KeyValueGrid data={data} currency={currency} skip={["imcc", "unconstrained_lha_es", "constrained_lha_es"]} />
    </div>
  );
}

function NmrfPanel({ data, currency }: { data: Record<string, unknown>; currency: string }) {
  const classifications = data.classifications as Record<string, unknown> | undefined;
  const methods = data.methods as Record<string, unknown> | undefined;
  const stressPeriods = data.selected_stress_periods as Record<string, unknown> | undefined;

  return (
    <div className="panel-flow">
      <div className="detail-grid">
        <MetricCard label="Total SES capital" value={formatValue(data.total_ses, currency)} tone="blue" />
        <MetricCard label="Classifications" value={String(Object.keys(classifications ?? {}).length)} meta="risk factors" />
        <MetricCard label="Methods" value={String(Object.keys(methods ?? {}).length)} meta="NMRF selections" />
        <MetricCard label="Stress periods" value={String(Object.keys(stressPeriods ?? {}).length)} meta="selected windows" />
      </div>
      {classifications ? <KeyValueGrid data={classifications} currency={currency} /> : null}
      {methods ? <KeyValueGrid data={methods} currency={currency} /> : null}
      {stressPeriods ? <KeyValueGrid data={stressPeriods} currency={currency} /> : null}
    </div>
  );
}

function PlaPanel({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="panel-flow">
      <div className="detail-grid">
        <article className="metric-card tone-green">
          <span>PLA zone</span>
          <strong><ZoneBadge zone={data.zone} /></strong>
          <small>distribution alignment</small>
        </article>
        <MetricCard label="KS statistic" value={formatValue(data.ks_statistic, "USD")} />
        <MetricCard label="Window size" value={data.window_size ? `${data.window_size} obs` : "-"} />
      </div>
      <p className="info-note">
        Green means no PLA add-on in this demo view; amber or red would route the desk into capital add-on review.
      </p>
    </div>
  );
}

function BacktestPanel({ data, currency }: { data: Record<string, unknown>; currency: string }) {
  return (
    <div className="panel-flow">
      <div className="detail-grid">
        <article className="metric-card tone-green">
          <span>APL zone</span>
          <strong><ZoneBadge zone={data.apl_zone ?? data.zone} /></strong>
          <small>{formatValue(data.apl_exceptions, currency)} exceptions</small>
        </article>
        <article className="metric-card tone-green">
          <span>HPL zone</span>
          <strong><ZoneBadge zone={data.hpl_zone} /></strong>
          <small>{formatValue(data.hpl_exceptions, currency)} exceptions</small>
        </article>
        <MetricCard label="Window" value={data.window_size ? `${data.window_size} obs` : "-"} />
      </div>
      <KeyValueGrid
        data={data}
        currency={currency}
        skip={["apl_zone", "zone", "hpl_zone", "apl_exceptions", "hpl_exceptions", "window_size"]}
      />
    </div>
  );
}

function AttributionTable({
  rows,
  currency,
  sortKey,
  onSort,
}: {
  rows: AttributionRow[];
  currency: string;
  sortKey: SortKey;
  onSort: (sortKey: SortKey) => void;
}) {
  const sortedRows = useMemo(() => {
    const copy = [...rows];
    if (sortKey === "source") copy.sort((left, right) => left.source_id.localeCompare(right.source_id));
    if (sortKey === "category") copy.sort((left, right) => left.category.localeCompare(right.category));
    if (sortKey === "absContribution") {
      copy.sort((left, right) => Math.abs(right.contribution ?? 0) - Math.abs(left.contribution ?? 0));
    }
    return copy;
  }, [rows, sortKey]);

  if (!sortedRows.length) return <p className="empty-state">No attribution rows for this view.</p>;
  const absTotal = sortedRows.reduce((sum, row) => sum + Math.abs(row.contribution ?? 0), 0);

  return (
    <div className="attribution-panel">
      <div className="table-toolbar">
        <span>{sortedRows.length} rows</span>
        <div>
          <button type="button" className={sortKey === "absContribution" ? "active" : ""} onClick={() => onSort("absContribution")}>
            Impact
          </button>
          <button type="button" className={sortKey === "category" ? "active" : ""} onClick={() => onSort("category")}>
            Category
          </button>
          <button type="button" className={sortKey === "source" ? "active" : ""} onClick={() => onSort("source")}>
            Source
          </button>
        </div>
      </div>
      <div className="preview-table-wrap">
        <table className="preview-table">
          <thead>
            <tr>
              <th>Category</th>
              <th>Source</th>
              <th>Method</th>
              <th>Contribution</th>
              <th>Share</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((row) => (
              <tr key={row.contribution_id}>
                <td>{row.category}</td>
                <td className="mono-cell">{row.source_level}:{row.source_id}</td>
                <td>{row.method}</td>
                <td className="money-cell">{row.contribution != null ? formatMoney(row.contribution, currency) : "-"}</td>
                <td>
                  <div className="share-cell">
                    <MiniBar value={row.contribution} total={absTotal} />
                    <span>{row.contribution != null && absTotal > 0 ? `${((Math.abs(row.contribution) / absTotal) * 100).toFixed(1)}%` : "-"}</span>
                  </div>
                </td>
                <td>
                  <span className={row.reconciliation_status === "RECONCILED" ? "status-chip ok" : "status-chip"}>
                    {row.reconciliation_status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SaComponentPanel({
  component,
  currency,
  saTotal,
  sortKey,
  onSort,
}: {
  component: SaOverview["components"][number];
  currency: string;
  saTotal: number;
  sortKey: SortKey;
  onSort: (sortKey: SortKey) => void;
}) {
  const breakdown = component.breakdown ?? {};
  const innerBreakdown = (breakdown.buckets ?? breakdown.lines ?? breakdown.risk_classes ?? {}) as Record<string, unknown>;

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <span className="eyebrow">{component.component}</span>
          <h3>{component.profile_id}</h3>
        </div>
        <span className="status-pill">{percent(component.total_capital, saTotal)} of SA</span>
      </div>
      <div className="panel-body panel-flow">
        <div className="detail-grid">
          <MetricCard label="Component capital" value={formatMoney(component.total_capital, currency)} tone="blue" />
          <MetricCard label="Input hash" value={component.input_hash?.slice(0, 12) ?? "-"} meta="prefix" />
          <MetricCard label="Lines" value={String(component.line_count ?? "-")} />
        </div>
        {Object.keys(innerBreakdown).length ? (
          <div className="breakdown-list">
            {Object.entries(innerBreakdown).map(([key, value]) => {
              const componentAmount =
                typeof value === "number"
                  ? value
                  : typeof value === "object" && value !== null && "capital" in value
                    ? Number((value as { capital: number }).capital)
                    : 0;
              return (
                <div key={key} className="breakdown-row">
                  <span><ComponentSwatch component={component.component} />{key}</span>
                  <MiniBar value={componentAmount} total={component.total_capital} />
                  <strong>{formatMoney(componentAmount, currency)}</strong>
                </div>
              );
            })}
          </div>
        ) : null}
        <AttributionTable rows={component.top_attribution} currency={currency} sortKey={sortKey} onSort={onSort} />
      </div>
    </section>
  );
}

export default function App() {
  const [overview, setOverview] = useState<RunOverview | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState("total");
  const [nodeDetail, setNodeDetail] = useState<NodeDetail | null>(null);
  const [imaDesk, setImaDesk] = useState<ImaDeskView | null>(null);
  const [primaryDesk, setPrimaryDesk] = useState<ImaDeskView | null>(null);
  const [saOverview, setSaOverview] = useState<SaOverview | null>(null);
  const [imaTab, setImaTab] = useState<ImaTab>("summary");
  const [treeQuery, setTreeQuery] = useState("");
  const [componentFilter, setComponentFilter] = useState<ComponentFilter>("ALL");
  const [sortKey, setSortKey] = useState<SortKey>("absContribution");
  const [density, setDensity] = useState<Density>("comfortable");
  const [error, setError] = useState<string | null>(null);

  const runId = overview?.run.run_id ?? "demo-suite-001";
  const currency = overview?.currency ?? "USD";
  const tree = useMemo(() => (overview ? flattenTree(overview.nodes) : []), [overview]);

  useEffect(() => {
    getRun(runId)
      .then((result) => {
        setOverview(result);
        const deskNode = result.nodes.find((node) => node.node_id.startsWith("ima-desk-"));
        if (deskNode) {
          getImaDesk(result.run.run_id, deskNode.node_id.replace("ima-desk-", ""))
            .then(setPrimaryDesk)
            .catch(() => undefined);
        }
      })
      .catch((exc) => setError(String(exc)));
    getSa(runId)
      .then(setSaOverview)
      .catch(() => undefined);
  }, [runId]);

  useEffect(() => {
    if (!overview) return;
    getNode(runId, selectedNodeId)
      .then(setNodeDetail)
      .catch((exc) => setError(String(exc)));
    if (selectedNodeId.startsWith("ima-desk")) {
      const deskId = selectedNodeId.replace("ima-desk-", "");
      getImaDesk(runId, deskId)
        .then(setImaDesk)
        .catch(() => setImaDesk(null));
    } else {
      setImaDesk(null);
    }
  }, [overview, runId, selectedNodeId]);

  const selectedNode = nodeDetail?.node;
  const activeDesk = imaDesk ?? primaryDesk;
  const selectedSaComponent = useMemo(() => {
    if (!saOverview) return null;
    if (selectedNodeId === "sa-sbm") return saOverview.components.find((component) => component.component === "SBM") ?? null;
    if (selectedNodeId === "sa-drc" || selectedNodeId.startsWith("sa-drc-")) {
      return saOverview.components.find((component) => component.component === "DRC") ?? null;
    }
    if (selectedNodeId === "sa-rrao") return saOverview.components.find((component) => component.component === "RRAO") ?? null;
    return null;
  }, [selectedNodeId, saOverview]);

  const showSaOverview = selectedNodeId === "sa" && saOverview;
  const showImaDesk = !!imaDesk;
  const showSaComponent = !!selectedSaComponent;
  const showNodeDetail = nodeDetail && !showImaDesk && !showSaOverview && !showSaComponent;

  return (
    <div className={`app-shell density-${density}`}>
      <TreeNavigation
        rows={tree}
        selectedNodeId={selectedNodeId}
        query={treeQuery}
        componentFilter={componentFilter}
        onQuery={setTreeQuery}
        onFilter={setComponentFilter}
        onSelect={setSelectedNodeId}
      />

      <main className="main">
        {error ? <div className="alert error">{error}</div> : null}

        {overview ? (
          <>
            <header className="page-header">
              <div>
                <span className="eyebrow">{overview.run.calculation_date} / {overview.run.jurisdiction_family}</span>
                <h2>{selectedNode?.label ?? "Capital overview"}</h2>
                <p>{overview.run.label}. Synthetic inspection run, not final regulatory capital.</p>
              </div>
              <div className="header-actions">
                <span className="status-pill">{selectedNode?.component ?? "SUITE"}</span>
                <span className="status-pill muted">{overview.run.input_hash?.slice(0, 12) ?? "-"}</span>
              </div>
            </header>

            <CommandBar
              selectedNodeId={selectedNodeId}
              density={density}
              onSelect={setSelectedNodeId}
              onDensity={setDensity}
            />
            <HealthStrip desk={activeDesk} overview={overview} />
            <CapitalStack overview={overview} saOverview={saOverview} selectedNodeId={selectedNodeId} onSelect={setSelectedNodeId} />

            {showImaDesk ? (
              <section className="panel">
                <div className="panel-header">
                  <div>
                    <span className="eyebrow">IMA desk</span>
                    <h3>{imaDesk.desk_id}</h3>
                  </div>
                  <span className="status-pill">{imaDesk.regime} / {imaDesk.eligibility}</span>
                </div>
                <div className="panel-body">
                  <div className="detail-tabs">
                    {TAB_LABELS.map(([id, label]) => (
                      <button
                        key={id}
                        type="button"
                        className={imaTab === id ? "active" : ""}
                        onClick={() => setImaTab(id)}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  {imaTab === "summary" ? <SummaryPanel data={imaDesk.summary as Record<string, unknown>} currency={currency} /> : null}
                  {imaTab === "imcc" ? <ImccPanel data={imaDesk.imcc as Record<string, unknown>} currency={currency} /> : null}
                  {imaTab === "nmrf" ? <NmrfPanel data={imaDesk.ses_nmrf as Record<string, unknown>} currency={currency} /> : null}
                  {imaTab === "pla" ? <PlaPanel data={imaDesk.pla as Record<string, unknown>} /> : null}
                  {imaTab === "backtest" ? <BacktestPanel data={imaDesk.backtesting as Record<string, unknown>} currency={currency} /> : null}
                  {imaTab === "attribution" ? (
                    <AttributionTable rows={imaDesk.attributions} currency={currency} sortKey={sortKey} onSort={setSortKey} />
                  ) : null}
                </div>
              </section>
            ) : null}

            {showSaOverview && saOverview ? (
              <section className="panel">
                <div className="panel-header">
                  <div>
                    <span className="eyebrow">Standardised Approach</span>
                    <h3>{formatMoney(saOverview.total_capital, currency)}</h3>
                  </div>
                  <span className="status-pill">{saOverview.jurisdiction_family}</span>
                </div>
                <div className="panel-body sa-grid">
                  {saOverview.components.map((component) => (
                    <SaComponentPanel
                      key={component.component}
                      component={component}
                      currency={currency}
                      saTotal={saOverview.total_capital}
                      sortKey={sortKey}
                      onSort={setSortKey}
                    />
                  ))}
                </div>
              </section>
            ) : null}

            {showSaComponent && selectedSaComponent && saOverview ? (
              <SaComponentPanel
                component={selectedSaComponent}
                currency={currency}
                saTotal={saOverview.total_capital}
                sortKey={sortKey}
                onSort={setSortKey}
              />
            ) : null}

            {showNodeDetail ? (
              <section className="panel">
                <div className="panel-header">
                  <div>
                    <span className="eyebrow">Node detail</span>
                    <h3>{nodeDetail.node.node_type}</h3>
                  </div>
                  <span className="status-pill">{nodeDetail.node.component}</span>
                </div>
                <div className="panel-body panel-flow">
                  {nodeDetail.measures.length ? (
                    <div className="detail-grid">
                      {nodeDetail.measures.map((measure) => (
                        <MetricCard
                          key={measure.name}
                          label={measure.name}
                          value={formatValue(measure.value, currency)}
                          meta={measure.unit ?? undefined}
                        />
                      ))}
                    </div>
                  ) : null}
                  <AttributionTable rows={nodeDetail.attributions} currency={currency} sortKey={sortKey} onSort={setSortKey} />
                </div>
              </section>
            ) : null}
          </>
        ) : (
          <div className="loading-state">Loading capital run...</div>
        )}
      </main>
    </div>
  );
}
