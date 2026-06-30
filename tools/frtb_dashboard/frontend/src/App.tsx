import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { formatMoney, getImaDesk, getNode, getRun, getSa, listRuns } from "./api";
import type {
  AttributionRow,
  CapitalNode,
  ImaDeskView,
  NodeDetail,
  RunOverview,
  RunSummary,
  SaOverview,
} from "./types";

type SortKey = "absContribution" | "source" | "category";
type ReconFilter = "ALL" | "RECONCILED" | "REVIEW";
type TabId = "summary" | "imcc" | "nmrf" | "pla" | "backtest" | "breakdown" | "attribution" | "diagnostics";
type TabDef = { id: TabId; label: string };

const COMPONENT_FILTERS = ["ALL", "IMA", "SA", "SBM", "DRC", "RRAO"] as const;
const RECON_FILTERS: ReconFilter[] = ["ALL", "RECONCILED", "REVIEW"];
const SORT_KEYS: SortKey[] = ["absContribution", "source", "category"];

type ComponentFilter = (typeof COMPONENT_FILTERS)[number];
type TreeRow = { node: CapitalNode; depth: number; pctOfParent: number | null };

const DEFAULT_RUN_ID = "demo-suite-001";

// Selections that render dedicated panels and therefore do not need the
// generic node-detail payload fetched.
function usesDedicatedPanel(nodeId: string): boolean {
  return (
    nodeId.startsWith("ima-desk") ||
    nodeId === "sa" ||
    nodeId === "sa-sbm" ||
    nodeId === "sa-rrao" ||
    nodeId === "sa-drc" ||
    nodeId.startsWith("sa-drc-")
  );
}

function flattenTree(
  nodes: CapitalNode[],
  parentId: string | null = null,
  depth = 0,
  parent: CapitalNode | null = null,
): TreeRow[] {
  const children = nodes.filter((node) => node.parent_id === parentId);
  return children.flatMap((node) => {
    const pctOfParent =
      parent && parent.amount ? (node.amount ?? 0) / parent.amount : null;
    return [{ node, depth, pctOfParent }, ...flattenTree(nodes, node.node_id, depth + 1, node)];
  });
}

function nodePath(nodes: CapitalNode[], nodeId: string): CapitalNode[] {
  const byId = new Map(nodes.map((node) => [node.node_id, node]));
  const path: CapitalNode[] = [];
  let current = byId.get(nodeId);
  while (current) {
    path.unshift(current);
    current = current.parent_id ? byId.get(current.parent_id) : undefined;
  }
  return path;
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

type ValueKind = "auto" | "money" | "count";

function looksLikeCurrency(unit: string | null | undefined): boolean {
  return !!unit && /^[A-Z]{3}$/.test(unit);
}

// Render a value without guessing that any large number is money — money is
// only formatted when the caller explicitly asks (or the unit is a currency).
export function formatValue(value: unknown, currency: string, kind: ValueKind = "auto"): string {
  if (value == null) return "-";
  if (typeof value === "number") {
    if (Number.isNaN(value)) return "-";
    if (kind === "money") return formatMoney(value, currency);
    if (kind === "count") return Math.round(value).toLocaleString();
    if (!Number.isInteger(value) && Math.abs(value) < 10) return value.toFixed(4);
    return value.toLocaleString();
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
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

function zoneTone(zone: unknown): "green" | "amber" | "red" | "neutral" {
  const normalized = String(zone ?? "").toUpperCase();
  if (normalized === "GREEN") return "green";
  if (normalized === "AMBER" || normalized === "ORANGE") return "amber";
  if (normalized === "RED") return "red";
  return "neutral";
}

export function reconClass(status: string): string {
  const normalized = status.toUpperCase();
  if (normalized === "RECONCILED") return "status-chip ok";
  if (normalized.includes("UNSUPPORTED")) return "status-chip unsupported";
  return "status-chip warn";
}

function ZoneBadge({ zone }: { zone: unknown }) {
  const label = String(zone ?? "-");
  return <span className={zoneClass(zone)}>{label}</span>;
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

function RunPicker({
  runs,
  selectedRunId,
  onSelect,
}: {
  runs: RunSummary[];
  selectedRunId: string;
  onSelect: (runId: string) => void;
}) {
  return (
    <label className="run-picker">
      <span>Capital run</span>
      <select value={selectedRunId} onChange={(event) => onSelect(event.target.value)}>
        {runs.length === 0 ? <option value={selectedRunId}>{selectedRunId}</option> : null}
        {runs.map((run) => (
          <option key={run.run_id} value={run.run_id}>
            {run.run_id} · {run.calculation_date}
          </option>
        ))}
      </select>
    </label>
  );
}

function Breadcrumbs({ path, onSelect }: { path: CapitalNode[]; onSelect: (nodeId: string) => void }) {
  if (path.length <= 1) return null;
  return (
    <nav className="breadcrumbs" aria-label="Capital tree breadcrumb">
      {path.map((node, index) => {
        const isLast = index === path.length - 1;
        return (
          <span key={node.node_id} className="crumb">
            {isLast ? (
              <span aria-current="page">{node.label}</span>
            ) : (
              <button type="button" onClick={() => onSelect(node.node_id)}>
                {node.label}
              </button>
            )}
            {isLast ? null : <i aria-hidden="true">/</i>}
          </span>
        );
      })}
    </nav>
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
          <span className="eyebrow">Capital mix</span>
          <h2>{formatMoney(suiteTotal, overview.currency)}</h2>
        </div>
      </div>

      <div className="stack-lanes">
        {stackItems.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`stack-lane ${item.tone} ${selectedNodeId === item.id ? "active" : ""}`}
            aria-pressed={selectedNodeId === item.id}
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
                aria-pressed={selectedNodeId === target}
                onClick={() => onSelect(target)}
              >
                <span>{component.component}</span>
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
  runs,
  selectedRunId,
  onRunSelect,
  selectedNodeId,
  query,
  componentFilter,
  onQuery,
  onFilter,
  onSelect,
}: {
  rows: TreeRow[];
  runs: RunSummary[];
  selectedRunId: string;
  onRunSelect: (runId: string) => void;
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
          <p>Capital workbench</p>
        </div>
      </div>

      <RunPicker runs={runs} selectedRunId={selectedRunId} onSelect={onRunSelect} />

      <label className="search-box">
        <span>Find node</span>
        <input value={query} onChange={(event) => onQuery(event.target.value)} placeholder="Desk, DRC, PLA..." />
      </label>

      <div className="filter-chips" role="group" aria-label="Component filter">
        {COMPONENT_FILTERS.map((filter) => (
          <button
            key={filter}
            type="button"
            className={componentFilter === filter ? "active" : ""}
            aria-pressed={componentFilter === filter}
            onClick={() => onFilter(filter)}
          >
            {filter}
          </button>
        ))}
      </div>

      <div className="tree-head" aria-hidden="true">
        <span>Node</span>
        <span>% parent</span>
        <span>Capital</span>
      </div>

      <nav className="tree-nav" aria-label="Capital tree">
        {filteredRows.length === 0 ? <p className="empty-state">No nodes match this filter.</p> : null}
        {filteredRows.map(({ node, depth, pctOfParent }) => (
          <button
            key={node.node_id}
            type="button"
            className={`tree-item ${selectedNodeId === node.node_id ? "active" : ""}`}
            style={{ "--depth": depth } as CSSProperties & Record<"--depth", number>}
            aria-current={selectedNodeId === node.node_id ? "page" : undefined}
            onClick={() => onSelect(node.node_id)}
          >
            <span className="tree-main">
              <strong>
                {node.label}
                {node.provisional ? <em className="provisional-dot" title="Indicative placeholder, not modelled" /> : null}
              </strong>
              <small>{node.component} / {node.node_type.toLowerCase()}</small>
            </span>
            <span className="tree-pct">{pctOfParent != null ? `${(pctOfParent * 100).toFixed(0)}%` : "—"}</span>
            <b>{formatMoney(node.amount, node.currency)}</b>
          </button>
        ))}
      </nav>
    </aside>
  );
}

function HealthStrip({ desk, overview }: { desk: ImaDeskView | null; overview: RunOverview }) {
  const plaZone = desk?.pla.zone;
  const aplZone = desk?.backtesting.apl_zone ?? desk?.backtesting.zone;
  const hplZone = desk?.backtesting.hpl_zone;
  const multiplier = desk?.summary.supervisory_multiplier;

  return (
    <section className="health-strip" aria-label="Run health">
      <MetricCard label="IMA / SA mix" value={`${percent(overview.ima_total, overview.suite_total)} / ${percent(overview.sa_total, overview.suite_total)}`} meta="capital split" />
      <MetricCard label="PLA status" value={String(plaZone ?? "-")} meta="distribution alignment" tone={zoneTone(plaZone)} />
      <MetricCard label="Backtesting" value={`${String(aplZone ?? "-")} / ${String(hplZone ?? "-")}`} meta="APL / HPL zones" tone={zoneTone(aplZone)} />
      <MetricCard label="Multiplier" value={multiplier ? `x${multiplier}` : "-"} meta="supervisory scalar" />
    </section>
  );
}

function SummaryPanel({ data, currency }: { data: Record<string, unknown>; currency: string }) {
  return (
    <div className="detail-grid">
      <MetricCard label="Models-based capital" value={formatValue(data.models_based_capital, currency, "money")} tone="blue" />
      <MetricCard label="IMCC" value={formatValue(data.imcc, currency, "money")} />
      <MetricCard label="Total SES" value={formatValue(data.total_ses, currency, "money")} />
      <MetricCard label="Binding term" value={String(data.binding_term ?? "-")} meta="capital driver" />
      <MetricCard label="Supervisory multiplier" value={data.supervisory_multiplier ? `x${data.supervisory_multiplier}` : "-"} />
    </div>
  );
}

function ImccPanel({ data, currency }: { data: Record<string, unknown>; currency: string }) {
  return (
    <div className="panel-flow">
      <div className="detail-grid">
        <MetricCard label="IMCC binding capital" value={formatValue(data.imcc, currency, "money")} tone="blue" />
        <MetricCard label="Unconstrained LHA ES" value={formatValue(data.unconstrained_lha_es, currency, "money")} />
        <MetricCard label="Constrained LHA ES" value={formatValue(data.constrained_lha_es, currency, "money")} />
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
        <MetricCard label="Total SES capital" value={formatValue(data.total_ses, currency, "money")} tone="blue" />
        <MetricCard label="Classifications" value={formatValue(Object.keys(classifications ?? {}).length, currency, "count")} meta="risk factors" />
        <MetricCard label="Methods" value={formatValue(Object.keys(methods ?? {}).length, currency, "count")} meta="NMRF selections" />
        <MetricCard label="Stress periods" value={formatValue(Object.keys(stressPeriods ?? {}).length, currency, "count")} meta="selected windows" />
      </div>
      {classifications ? <KeyValueGrid data={classifications} currency={currency} /> : null}
      {methods ? <KeyValueGrid data={methods} currency={currency} /> : null}
      {stressPeriods ? <KeyValueGrid data={stressPeriods} currency={currency} /> : null}
    </div>
  );
}

function PlaPanel({ data }: { data: Record<string, unknown> }) {
  const notModelled = String(data.add_on_status ?? "").toUpperCase() === "NOT_MODELLED";
  return (
    <div className="panel-flow">
      <div className="detail-grid">
        <article className={`metric-card tone-${zoneTone(data.zone)}`}>
          <span>PLA zone</span>
          <strong><ZoneBadge zone={data.zone} /></strong>
          <small>distribution alignment</small>
        </article>
        <MetricCard label="KS statistic" value={formatValue(data.ks_statistic, "USD")} />
        <MetricCard label="Window size" value={data.window_size ? `${data.window_size} obs` : "-"} />
      </div>
      {notModelled ? (
        <p className="info-note warn">
          PLA zone is assessed, but the capital add-on itself is <strong>not modelled</strong> in this demo
          (shown as an indicative placeholder). A non-green zone would route the desk into add-on review.
        </p>
      ) : (
        <p className="info-note">
          The zone drives whether a PLA add-on applies; amber or red would route the desk into capital add-on review.
        </p>
      )}
    </div>
  );
}

function BacktestPanel({ data, currency }: { data: Record<string, unknown>; currency: string }) {
  return (
    <div className="panel-flow">
      <div className="detail-grid">
        <article className={`metric-card tone-${zoneTone(data.apl_zone ?? data.zone)}`}>
          <span>APL zone</span>
          <strong><ZoneBadge zone={data.apl_zone ?? data.zone} /></strong>
          <small>{formatValue(data.apl_exceptions, currency, "count")} exceptions</small>
        </article>
        <article className={`metric-card tone-${zoneTone(data.hpl_zone)}`}>
          <span>HPL zone</span>
          <strong><ZoneBadge zone={data.hpl_zone} /></strong>
          <small>{formatValue(data.hpl_exceptions, currency, "count")} exceptions</small>
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

// Validates that the displayed contributions tie back to the node total, and
// surfaces how much of the node is covered and how many rows need review.
function ReconciliationStrip({
  rows,
  nodeTotal,
  currency,
}: {
  rows: AttributionRow[];
  nodeTotal: number | null;
  currency: string;
}) {
  if (!rows.length) return null;
  const review = rows.filter((row) => row.reconciliation_status.toUpperCase() !== "RECONCILED").length;
  const sum = rows.reduce((acc, row) => acc + (row.contribution ?? 0), 0);
  const sumAbs = rows.reduce((acc, row) => acc + Math.abs(row.contribution ?? 0), 0);
  const coverage = nodeTotal ? Math.min(100, (sumAbs / Math.abs(nodeTotal)) * 100) : null;
  const tone = review > 0 ? "amber" : "green";

  return (
    <div className={`recon-strip tone-${tone}`} role="status">
      <span className="recon-dot" aria-hidden="true" />
      <span><b>{rows.length}</b> rows shown</span>
      <span>Σ shown <b>{formatMoney(sum, currency)}</b></span>
      {nodeTotal != null ? <span>node total <b>{formatMoney(nodeTotal, currency)}</b></span> : null}
      {coverage != null ? <span>coverage <b>{coverage.toFixed(1)}%</b></span> : null}
      <span className={review > 0 ? "recon-flag warn" : "recon-flag ok"}>
        {review > 0 ? `${review} need review` : "all reconciled"}
      </span>
    </div>
  );
}

function AttributionTable({
  rows,
  currency,
  nodeTotal,
  sortKey,
  onSort,
  reconFilter,
  onReconFilter,
}: {
  rows: AttributionRow[];
  currency: string;
  nodeTotal: number | null;
  sortKey: SortKey;
  onSort: (sortKey: SortKey) => void;
  reconFilter: ReconFilter;
  onReconFilter: (value: ReconFilter) => void;
}) {
  const visibleRows = useMemo(() => {
    const filtered = rows.filter((row) => {
      if (reconFilter === "ALL") return true;
      const reconciled = row.reconciliation_status.toUpperCase() === "RECONCILED";
      return reconFilter === "RECONCILED" ? reconciled : !reconciled;
    });
    const copy = [...filtered];
    if (sortKey === "source") copy.sort((left, right) => left.source_id.localeCompare(right.source_id));
    if (sortKey === "category") copy.sort((left, right) => left.category.localeCompare(right.category));
    if (sortKey === "absContribution") {
      copy.sort((left, right) => Math.abs(right.contribution ?? 0) - Math.abs(left.contribution ?? 0));
    }
    return copy;
  }, [rows, sortKey, reconFilter]);

  const absTotal = visibleRows.reduce((sum, row) => sum + Math.abs(row.contribution ?? 0), 0);
  const reconOptions: Array<[ReconFilter, string]> = [
    ["ALL", "All"],
    ["RECONCILED", "Reconciled"],
    ["REVIEW", "Needs review"],
  ];

  return (
    <div className="attribution-panel panel-flow">
      <ReconciliationStrip rows={rows} nodeTotal={nodeTotal} currency={currency} />
      <div className="table-toolbar">
        <div className="recon-filters" role="group" aria-label="Reconciliation filter">
          {reconOptions.map(([value, label]) => (
            <button
              key={value}
              type="button"
              className={reconFilter === value ? "active" : ""}
              aria-pressed={reconFilter === value}
              onClick={() => onReconFilter(value)}
            >
              {label}
            </button>
          ))}
          <span className="row-count">{visibleRows.length} rows</span>
        </div>
        <div role="group" aria-label="Sort attribution">
          <button type="button" className={sortKey === "absContribution" ? "active" : ""} aria-pressed={sortKey === "absContribution"} onClick={() => onSort("absContribution")}>
            Impact
          </button>
          <button type="button" className={sortKey === "category" ? "active" : ""} aria-pressed={sortKey === "category"} onClick={() => onSort("category")}>
            Category
          </button>
          <button type="button" className={sortKey === "source" ? "active" : ""} aria-pressed={sortKey === "source"} onClick={() => onSort("source")}>
            Source
          </button>
        </div>
      </div>
      {visibleRows.length === 0 ? (
        <p className="empty-state">No attribution rows for this view.</p>
      ) : (
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
              {visibleRows.map((row) => (
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
                    <span className={reconClass(row.reconciliation_status)} title={row.reason || undefined}>
                      {row.reconciliation_status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function BreakdownList({
  breakdown,
  total,
  currency,
}: {
  breakdown: Record<string, unknown>;
  total: number;
  currency: string;
}) {
  const inner = (breakdown.buckets ?? breakdown.lines ?? breakdown.risk_classes ?? {}) as Record<string, unknown>;
  const entries = Object.entries(inner);
  if (!entries.length) return <p className="empty-state">No breakdown available for this node.</p>;
  return (
    <div className="breakdown-list">
      {entries.map(([key, value]) => {
        const amount =
          typeof value === "number"
            ? value
            : typeof value === "object" && value !== null && "capital" in value
              ? Number((value as { capital: number }).capital)
              : 0;
        return (
          <div key={key} className="breakdown-row">
            <span>{key}</span>
            <MiniBar value={amount} total={total} />
            <strong>{formatMoney(amount, currency)}</strong>
          </div>
        );
      })}
    </div>
  );
}

function DiagnosticsPanel({
  rows,
  node,
  currency,
}: {
  rows: AttributionRow[];
  node: CapitalNode | null;
  currency: string;
}) {
  const review = rows.filter((row) => row.reconciliation_status.toUpperCase() !== "RECONCILED");
  return (
    <div className="panel-flow">
      {node?.provisional ? (
        <p className="info-note warn">This figure is an indicative placeholder and is not modelled in this demo run.</p>
      ) : null}
      <div className="detail-grid">
        <MetricCard label="Attribution rows" value={formatValue(rows.length, currency, "count")} />
        <MetricCard label="Reconciled" value={formatValue(rows.length - review.length, currency, "count")} tone={rows.length ? "green" : "neutral"} />
        <MetricCard label="Need review" value={formatValue(review.length, currency, "count")} tone={review.length ? "amber" : "neutral"} />
      </div>
      {review.length ? (
        <div className="preview-table-wrap">
          <table className="preview-table">
            <thead>
              <tr>
                <th>Category</th>
                <th>Source</th>
                <th>Status</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {review.map((row) => (
                <tr key={row.contribution_id}>
                  <td>{row.category}</td>
                  <td className="mono-cell">{row.source_level}:{row.source_id}</td>
                  <td><span className={reconClass(row.reconciliation_status)}>{row.reconciliation_status}</span></td>
                  <td>{row.reason || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="info-note">All shown contributions are reconciled; no unsupported or residual records in this view.</p>
      )}
    </div>
  );
}

function readParam(key: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  return new URLSearchParams(window.location.search).get(key) ?? fallback;
}

function sanitize<T extends string>(value: string, allowed: readonly T[], fallback: T): T {
  return (allowed as readonly string[]).includes(value) ? (value as T) : fallback;
}

export default function App() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selectedRunId, setSelectedRunId] = useState(() => readParam("run", DEFAULT_RUN_ID));
  const [overview, setOverview] = useState<RunOverview | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState(() => readParam("node", "total"));
  const [nodeDetail, setNodeDetail] = useState<NodeDetail | null>(null);
  const [imaDesk, setImaDesk] = useState<ImaDeskView | null>(null);
  const [primaryDesk, setPrimaryDesk] = useState<ImaDeskView | null>(null);
  const [saOverview, setSaOverview] = useState<SaOverview | null>(null);
  const [tab, setTab] = useState<TabId>(() => sanitize<TabId>(readParam("tab", "summary"), ["summary", "imcc", "nmrf", "pla", "backtest", "breakdown", "attribution", "diagnostics"], "summary"));
  const [treeQuery, setTreeQuery] = useState("");
  const [componentFilter, setComponentFilter] = useState<ComponentFilter>(() => sanitize<ComponentFilter>(readParam("comp", "ALL"), COMPONENT_FILTERS, "ALL"));
  const [sortKey, setSortKey] = useState<SortKey>(() => sanitize<SortKey>(readParam("sort", "absContribution"), SORT_KEYS, "absContribution"));
  const [reconFilter, setReconFilter] = useState<ReconFilter>(() => sanitize<ReconFilter>(readParam("recon", "ALL"), RECON_FILTERS, "ALL"));
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runId = selectedRunId;
  const currency = overview?.currency ?? "USD";
  const tree = useMemo(() => (overview ? flattenTree(overview.nodes) : []), [overview]);

  // Reflect the active view in the URL so it is deep-linkable and reproducible.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams();
    params.set("run", selectedRunId);
    params.set("node", selectedNodeId);
    params.set("tab", tab);
    if (reconFilter !== "ALL") params.set("recon", reconFilter);
    if (sortKey !== "absContribution") params.set("sort", sortKey);
    if (componentFilter !== "ALL") params.set("comp", componentFilter);
    const qs = params.toString();
    window.history.replaceState(null, "", qs ? `?${qs}` : window.location.pathname);
  }, [selectedRunId, selectedNodeId, tab, reconFilter, sortKey, componentFilter]);

  useEffect(() => {
    listRuns()
      .then(setRuns)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    setError(null);
    setOverview(null);
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
    let cancelled = false;
    setError(null);
    setDetailLoading(true);

    const dedicated = usesDedicatedPanel(selectedNodeId);
    const tasks: Array<Promise<unknown>> = [];

    // Only fetch the generic node-detail payload when no dedicated panel renders
    // it — desk and SA selections have their own endpoints/panels.
    if (!dedicated) {
      setNodeDetail(null);
      tasks.push(
        getNode(runId, selectedNodeId)
          .then((result) => {
            if (!cancelled) setNodeDetail(result);
          })
          .catch((exc) => {
            if (!cancelled) setError(String(exc));
          }),
      );
    }

    if (selectedNodeId.startsWith("ima-desk")) {
      const deskId = selectedNodeId.replace("ima-desk-", "");
      tasks.push(
        getImaDesk(runId, deskId)
          .then((result) => {
            if (!cancelled) setImaDesk(result);
          })
          .catch(() => {
            if (!cancelled) setImaDesk(null);
          }),
      );
    } else {
      setImaDesk(null);
    }

    Promise.allSettled(tasks).then(() => {
      if (!cancelled) setDetailLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [overview, runId, selectedNodeId]);

  const selectedNode = useMemo(
    () => overview?.nodes.find((node) => node.node_id === selectedNodeId) ?? null,
    [overview, selectedNodeId],
  );
  const breadcrumbPath = useMemo(
    () => (overview ? nodePath(overview.nodes, selectedNodeId) : []),
    [overview, selectedNodeId],
  );
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

  const isSaAggregate = selectedNodeId === "sa";
  const kind: "ima" | "sa" | "sa-component" | "node" = imaDesk
    ? "ima"
    : isSaAggregate
      ? "sa"
      : selectedSaComponent
        ? "sa-component"
        : "node";

  // A deterministic tab set: Summary first, Attribution + Diagnostics always
  // present and last, with node-type-specific analytics in between.
  const tabs: TabDef[] = useMemo(() => {
    const list: TabDef[] = [{ id: "summary", label: "Summary" }];
    if (kind === "ima") {
      list.push(
        { id: "imcc", label: "IMCC / ES" },
        { id: "nmrf", label: "SES & NMRF" },
        { id: "pla", label: "PLA" },
        { id: "backtest", label: "Backtesting" },
      );
    }
    if (kind === "sa" || kind === "sa-component") list.push({ id: "breakdown", label: "Breakdown" });
    list.push({ id: "attribution", label: "Attribution" }, { id: "diagnostics", label: "Diagnostics" });
    return list;
  }, [kind]);

  // Keep the active tab valid when the selection (and therefore tab set) changes.
  // While the data that unlocks extra tabs is still loading, hold off — otherwise
  // a deep link like ?node=ima-desk-X&tab=pla would reset before "pla" exists.
  const awaitingTabs =
    (selectedNodeId.startsWith("ima-desk") && !imaDesk) ||
    ((selectedNodeId === "sa" || selectedNodeId.startsWith("sa-")) && !saOverview);
  useEffect(() => {
    if (awaitingTabs) return;
    if (!tabs.some((entry) => entry.id === tab)) setTab("summary");
  }, [tabs, tab, awaitingTabs]);

  const nodeTotal = selectedNode?.amount ?? null;
  const attributionRows: AttributionRow[] = useMemo(() => {
    if (kind === "ima" && imaDesk) return imaDesk.attributions;
    if (kind === "sa-component" && selectedSaComponent) return selectedSaComponent.top_attribution;
    if (kind === "sa" && saOverview) return saOverview.components.flatMap((component) => component.top_attribution);
    return nodeDetail?.attributions ?? [];
  }, [kind, imaDesk, selectedSaComponent, saOverview, nodeDetail]);

  const contextPill = useMemo(() => {
    if (kind === "ima" && imaDesk) return `${imaDesk.regime} / ${imaDesk.eligibility}`;
    if (kind === "sa-component" && selectedSaComponent && saOverview) return `${percent(selectedSaComponent.total_capital, saOverview.total_capital)} of SA`;
    if (kind === "sa" && saOverview) return saOverview.jurisdiction_family;
    return selectedNode?.component ?? "SUITE";
  }, [kind, imaDesk, selectedSaComponent, saOverview, selectedNode]);

  const eyebrow =
    kind === "ima" ? "IMA desk" : kind === "sa" ? "Standardised Approach" : kind === "sa-component" ? `SA · ${selectedSaComponent?.component}` : "Capital node";

  function renderTabContent() {
    if (tab === "attribution") {
      return (
        <AttributionTable
          rows={attributionRows}
          currency={currency}
          nodeTotal={nodeTotal}
          sortKey={sortKey}
          onSort={setSortKey}
          reconFilter={reconFilter}
          onReconFilter={setReconFilter}
        />
      );
    }
    if (tab === "diagnostics") {
      return <DiagnosticsPanel rows={attributionRows} node={selectedNode} currency={currency} />;
    }

    if (kind === "ima" && imaDesk) {
      if (tab === "imcc") return <ImccPanel data={imaDesk.imcc as Record<string, unknown>} currency={currency} />;
      if (tab === "nmrf") return <NmrfPanel data={imaDesk.ses_nmrf as Record<string, unknown>} currency={currency} />;
      if (tab === "pla") return <PlaPanel data={imaDesk.pla as Record<string, unknown>} />;
      if (tab === "backtest") return <BacktestPanel data={imaDesk.backtesting as Record<string, unknown>} currency={currency} />;
      return <SummaryPanel data={imaDesk.summary as Record<string, unknown>} currency={currency} />;
    }

    if (kind === "sa" && saOverview) {
      if (tab === "breakdown") {
        return (
          <div className="panel-flow">
            {saOverview.components.map((component) => (
              <div key={component.component} className="breakdown-group">
                <h4>{component.component} · {formatMoney(component.total_capital, currency)}</h4>
                <BreakdownList breakdown={component.breakdown ?? {}} total={component.total_capital} currency={currency} />
              </div>
            ))}
          </div>
        );
      }
      return (
        <div className="detail-grid">
          <MetricCard label="SA total" value={formatMoney(saOverview.total_capital, currency)} tone="blue" />
          {saOverview.components.map((component) => (
            <MetricCard
              key={component.component}
              label={component.component}
              value={formatMoney(component.total_capital, currency)}
              meta={`${percent(component.total_capital, saOverview.total_capital)} of SA`}
            />
          ))}
        </div>
      );
    }

    if (kind === "sa-component" && selectedSaComponent && saOverview) {
      if (tab === "breakdown") {
        return <BreakdownList breakdown={selectedSaComponent.breakdown ?? {}} total={selectedSaComponent.total_capital} currency={currency} />;
      }
      return (
        <div className="detail-grid">
          <MetricCard label="Component capital" value={formatMoney(selectedSaComponent.total_capital, currency)} tone="blue" />
          <MetricCard label="% of SA" value={percent(selectedSaComponent.total_capital, saOverview.total_capital)} />
          <MetricCard label="Profile" value={selectedSaComponent.profile_id} />
          <MetricCard label="Input hash" value={selectedSaComponent.input_hash?.slice(0, 12) ?? "-"} meta="prefix" />
          <MetricCard label="Lines" value={formatValue(selectedSaComponent.line_count, currency, "count")} />
        </div>
      );
    }

    // Generic node summary.
    return (
      <div className="panel-flow">
        {selectedNode?.provisional ? (
          <p className="info-note warn">This figure is an indicative placeholder and is not modelled in this demo run.</p>
        ) : null}
        {nodeDetail?.measures.length ? (
          <div className="detail-grid">
            {nodeDetail.measures.map((measure) => (
              <MetricCard
                key={measure.name}
                label={measure.name}
                value={formatValue(measure.value, currency, looksLikeCurrency(measure.unit) ? "money" : "auto")}
                meta={measure.unit ?? undefined}
              />
            ))}
          </div>
        ) : (
          <div className="detail-grid">
            <MetricCard label="Capital" value={formatMoney(selectedNode?.amount ?? null, currency)} tone="blue" />
            <MetricCard label="Component" value={selectedNode?.component ?? "-"} />
            <MetricCard label="Type" value={selectedNode?.node_type ?? "-"} />
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="app-shell">
      <TreeNavigation
        rows={tree}
        runs={runs}
        selectedRunId={selectedRunId}
        onRunSelect={(value) => {
          setSelectedRunId(value);
          setSelectedNodeId("total");
        }}
        selectedNodeId={selectedNodeId}
        query={treeQuery}
        componentFilter={componentFilter}
        onQuery={setTreeQuery}
        onFilter={setComponentFilter}
        onSelect={setSelectedNodeId}
      />

      <main className="main">
        {error ? <div className="alert error" role="alert">{error}</div> : null}

        {overview ? (
          <>
            <header className="run-header">
              <div className="run-header-main">
                <Breadcrumbs path={breadcrumbPath} onSelect={setSelectedNodeId} />
                <h2>
                  {selectedNode?.label ?? "Capital overview"}
                  {selectedNode?.provisional ? <span className="provisional-chip">indicative</span> : null}
                </h2>
                <p>{overview.run.label}. Read-only synthetic results for dashboard inspection, not final regulatory capital.</p>
              </div>
              <div className="run-meta" aria-label="Run metadata">
                {detailLoading ? <span className="status-pill loading" aria-live="polite">Updating…</span> : null}
                <span className="status-pill">{overview.run.calculation_date}</span>
                <span className="status-pill">{overview.run.profile_id}</span>
                {overview.run.jurisdiction_family ? <span className="status-pill">{overview.run.jurisdiction_family}</span> : null}
                <span className="status-pill muted">{overview.run.input_hash?.slice(0, 12) ?? "-"}</span>
              </div>
            </header>

            <div className="workbench">
              <section className={detailLoading ? "workbench-primary is-loading" : "workbench-primary"}>
                <div className="panel">
                  <div className="panel-header">
                    <div>
                      <span className="eyebrow">{eyebrow}</span>
                      <h3>
                        {selectedNode?.label ?? "Capital overview"}
                        {selectedNode?.provisional ? <span className="provisional-chip">indicative</span> : null}
                      </h3>
                    </div>
                    <span className="status-pill">{contextPill}</span>
                  </div>
                  <div className="panel-body">
                    <div className="detail-tabs" role="tablist" aria-label="Node workbench">
                      {tabs.map((entry) => (
                        <button
                          key={entry.id}
                          type="button"
                          role="tab"
                          id={`tab-${entry.id}`}
                          aria-selected={tab === entry.id}
                          aria-controls={`panel-${entry.id}`}
                          className={tab === entry.id ? "active" : ""}
                          onClick={() => setTab(entry.id)}
                        >
                          {entry.label}
                        </button>
                      ))}
                    </div>
                    <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
                      {renderTabContent()}
                    </div>
                  </div>
                </div>
              </section>

              <aside className="workbench-aside" aria-label="Capital context">
                <CapitalStack overview={overview} saOverview={saOverview} selectedNodeId={selectedNodeId} onSelect={setSelectedNodeId} />
                <HealthStrip desk={activeDesk} overview={overview} />
              </aside>
            </div>
          </>
        ) : (
          <div className="loading-state">{error ? "Could not load capital run." : "Loading capital run..."}</div>
        )}
      </main>
    </div>
  );
}
