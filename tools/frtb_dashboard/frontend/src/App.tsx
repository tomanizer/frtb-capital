import { useEffect, useMemo, useState } from "react";
import { formatMoney, getImaDesk, getNode, getRun, getSa } from "./api";
import type { AttributionRow, CapitalNode, ImaDeskView, NodeDetail, RunOverview, SaOverview } from "./types";

type ImaTab = "summary" | "imcc" | "nmrf" | "pla" | "backtest" | "attribution";

// ── Helpers ──────────────────────────────────────────────────────────────────

function flattenTree(nodes: CapitalNode[], parentId: string | null = null, depth = 0): Array<{ node: CapitalNode; depth: number }> {
  const children = nodes.filter((n) => n.parent_id === parentId);
  return children.flatMap((n) => [{ node: n, depth }, ...flattenTree(nodes, n.node_id, depth + 1)]);
}

function humanKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .replace(/\bEs\b/g, "ES")
    .replace(/\bImcc\b/g, "IMCC")
    .replace(/\bSes\b/g, "SES")
    .replace(/\bPla\b/g, "PLA")
    .replace(/\bLha\b/g, "LHA")
    .replace(/\bKs\b/g, "KS");
}

function formatValue(value: unknown, currency: string): string {
  if (value == null) return "—";
  if (typeof value === "number") {
    if (Math.abs(value) > 1000) return formatMoney(value, currency);
    if (Math.abs(value) < 10 && Math.abs(value) > 0) return value.toFixed(4);
    return value.toLocaleString();
  }
  return String(value);
}

function pct(part: number, total: number): string {
  if (!total) return "—";
  return `${((part / total) * 100).toFixed(1)}%`;
}

// ── Zone badge ────────────────────────────────────────────────────────────────

type Zone = "GREEN" | "AMBER" | "RED" | string;

function zoneCls(zone: Zone): string {
  if (zone === "GREEN") return "badge success";
  if (zone === "RED") return "badge danger";
  if (zone === "AMBER" || zone === "ORANGE") return "badge warning";
  return "badge";
}

function ZoneBadge({ zone }: { zone: Zone }) {
  return <span className={zoneCls(zone)}>{zone}</span>;
}

// ── Capital breakdown bars ────────────────────────────────────────────────────

interface BarItem {
  label: string;
  amount: number;
  color: string;
  indent?: boolean;
}

function CapitalBars({ items, total, currency }: { items: BarItem[]; total: number; currency: string }) {
  return (
    <div className="capital-bars">
      {items.map((item) => {
        const fraction = total > 0 ? Math.max(0, Math.min(1, item.amount / total)) : 0;
        return (
          <div key={item.label} className={`bar-row${item.indent ? " bar-indent" : ""}`}>
            <span className="bar-label">{item.label}</span>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${fraction * 100}%`, background: item.color }} />
            </div>
            <span className="bar-amount">{formatMoney(item.amount, currency)}</span>
            <span className="bar-pct">{pct(item.amount, total)}</span>
          </div>
        );
      })}
    </div>
  );
}

// ── Structured panels ─────────────────────────────────────────────────────────

function BacktestPanel({ data, currency }: { data: Record<string, unknown>; currency: string }) {
  const aplZone = String(data.apl_zone ?? data.zone ?? "—");
  const hplZone = String(data.hpl_zone ?? "—");
  const aplEx = data.apl_exceptions as number | undefined;
  const hplEx = data.hpl_exceptions as number | undefined;
  const windowSize = data.window_size as number | undefined;

  return (
    <div>
      <div className="stats-grid" style={{ marginBottom: 16 }}>
        <div className="stat-card">
          <strong><ZoneBadge zone={aplZone} /></strong>
          <span>APL zone</span>
        </div>
        {hplZone !== "—" && (
          <div className="stat-card">
            <strong><ZoneBadge zone={hplZone} /></strong>
            <span>HPL zone</span>
          </div>
        )}
        <div className="stat-card">
          <strong>{aplEx ?? "—"}</strong>
          <span>APL exceptions</span>
        </div>
        {hplEx !== undefined && (
          <div className="stat-card">
            <strong>{hplEx}</strong>
            <span>HPL exceptions</span>
          </div>
        )}
        {windowSize !== undefined && (
          <div className="stat-card">
            <strong>{windowSize} obs</strong>
            <span>Backtesting window</span>
          </div>
        )}
      </div>
      {Object.keys(data).some((k) => !["apl_zone", "hpl_zone", "zone", "apl_exceptions", "hpl_exceptions", "window_size"].includes(k)) && (
        <div className="kv-grid">
          {Object.entries(data)
            .filter(([k]) => !["apl_zone", "hpl_zone", "zone", "apl_exceptions", "hpl_exceptions", "window_size"].includes(k))
            .map(([k, v]) => (
              <div key={k} className="kv-row">
                <span className="kv-key">{humanKey(k)}</span>
                <span className="kv-val">{formatValue(v, currency)}</span>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}

function PlaPanel({ data }: { data: Record<string, unknown> }) {
  const zone = String(data.zone ?? "—");
  const ks = data.ks_statistic as number | undefined;
  const windowSize = data.window_size as number | undefined;

  return (
    <div>
      <div className="stats-grid" style={{ marginBottom: 16 }}>
        <div className="stat-card">
          <strong><ZoneBadge zone={zone} /></strong>
          <span>PLA zone</span>
        </div>
        {ks !== undefined && (
          <div className="stat-card">
            <strong>{ks.toFixed(4)}</strong>
            <span>KS statistic</span>
          </div>
        )}
        {windowSize !== undefined && (
          <div className="stat-card">
            <strong>{windowSize} obs</strong>
            <span>Window size</span>
          </div>
        )}
      </div>
      <div className="info-note">
        GREEN = distribution aligned (no add-on) · AMBER = partial mis-alignment · RED = significant mis-alignment (capital add-on applies)
      </div>
    </div>
  );
}

function ImccPanel({ data, currency }: { data: Record<string, unknown>; currency: string }) {
  const imcc = data.imcc as number | undefined;
  const unconstrained = data.unconstrained_lha_es as number | undefined;
  const constrained = data.constrained_lha_es as number | undefined;

  return (
    <div>
      <div className="stats-grid" style={{ marginBottom: 16 }}>
        {imcc !== undefined && (
          <div className="stat-card accent">
            <strong>{formatMoney(imcc, currency)}</strong>
            <span>IMCC (binding)</span>
          </div>
        )}
        {unconstrained !== undefined && (
          <div className="stat-card">
            <strong>{formatMoney(unconstrained, currency)}</strong>
            <span>Unconstrained LHA ES</span>
          </div>
        )}
        {constrained !== undefined && (
          <div className="stat-card">
            <strong>{formatMoney(constrained, currency)}</strong>
            <span>Constrained LHA ES</span>
          </div>
        )}
      </div>
      {Object.keys(data).some((k) => !["imcc", "unconstrained_lha_es", "constrained_lha_es"].includes(k)) && (
        <div className="kv-grid">
          {Object.entries(data)
            .filter(([k]) => !["imcc", "unconstrained_lha_es", "constrained_lha_es"].includes(k))
            .map(([k, v]) => (
              <div key={k} className="kv-row">
                <span className="kv-key">{humanKey(k)}</span>
                <span className="kv-val">{formatValue(v, currency)}</span>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}

function NmrfPanel({ data, currency }: { data: Record<string, unknown>; currency: string }) {
  const totalSes = data.total_ses as number | undefined;
  const classifications = data.classifications as Record<string, unknown> | undefined;
  const methods = data.methods as Record<string, unknown> | undefined;
  const stressPeriods = data.selected_stress_periods as Record<string, unknown> | undefined;

  return (
    <div>
      {totalSes !== undefined && (
        <div className="stats-grid" style={{ marginBottom: 16 }}>
          <div className="stat-card accent">
            <strong>{formatMoney(totalSes, currency)}</strong>
            <span>Total SES capital</span>
          </div>
        </div>
      )}
      {classifications && Object.keys(classifications).length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <h4 className="panel-section-title">Risk factor classifications</h4>
          <div className="kv-grid">
            {Object.entries(classifications).map(([k, v]) => (
              <div key={k} className="kv-row">
                <span className="kv-key">{k}</span>
                <span className="kv-val">{String(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {methods && Object.keys(methods).length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <h4 className="panel-section-title">NMRF methods selected</h4>
          <div className="kv-grid">
            {Object.entries(methods).map(([k, v]) => (
              <div key={k} className="kv-row">
                <span className="kv-key">{k}</span>
                <span className="kv-val">{String(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {stressPeriods && Object.keys(stressPeriods).length > 0 && (
        <div>
          <h4 className="panel-section-title">Stress periods</h4>
          <div className="kv-grid">
            {Object.entries(stressPeriods).map(([k, v]) => (
              <div key={k} className="kv-row">
                <span className="kv-key">{humanKey(k)}</span>
                <span className="kv-val">{typeof v === "object" ? JSON.stringify(v) : String(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {/* Fallback for any keys not covered above */}
      {Object.entries(data)
        .filter(([k]) => !["total_ses", "classifications", "methods", "selected_stress_periods", "reconciliation"].includes(k))
        .map(([k, v]) => (
          <div key={k} className="kv-row">
            <span className="kv-key">{humanKey(k)}</span>
            <span className="kv-val">{formatValue(v, currency)}</span>
          </div>
        ))}
    </div>
  );
}

function SummaryPanel({ data, currency }: { data: Record<string, unknown>; currency: string }) {
  const bindingTerm = data.binding_term as string | undefined;
  const multiplier = data.supervisory_multiplier as number | undefined;

  return (
    <div>
      <div className="stats-grid" style={{ marginBottom: 16 }}>
        {data.models_based_capital !== undefined && (
          <div className="stat-card accent">
            <strong>{formatMoney(data.models_based_capital as number, currency)}</strong>
            <span>Models-based capital</span>
          </div>
        )}
        {data.imcc !== undefined && (
          <div className="stat-card">
            <strong>{formatMoney(data.imcc as number, currency)}</strong>
            <span>IMCC</span>
          </div>
        )}
        {data.total_ses !== undefined && (
          <div className="stat-card">
            <strong>{formatMoney(data.total_ses as number, currency)}</strong>
            <span>Total SES</span>
          </div>
        )}
        {multiplier !== undefined && (
          <div className="stat-card">
            <strong>×{multiplier}</strong>
            <span>Supervisory multiplier</span>
          </div>
        )}
      </div>
      {bindingTerm && (
        <div className="kv-row" style={{ marginBottom: 8 }}>
          <span className="kv-key">Binding term</span>
          <span className="kv-val">
            <span className="chip">{bindingTerm}</span>
          </span>
        </div>
      )}
    </div>
  );
}

// ── Attribution table ─────────────────────────────────────────────────────────

function AttributionTable({ rows, currency }: { rows: AttributionRow[]; currency: string }) {
  if (!rows.length) return <p className="alias-list">No attribution rows for this view.</p>;
  const absTotal = rows.reduce((sum, r) => sum + Math.abs(r.contribution ?? 0), 0);
  return (
    <div className="preview-table-wrap">
      <table className="preview-table">
        <thead>
          <tr>
            <th>Category</th>
            <th>Source</th>
            <th>Method</th>
            <th style={{ textAlign: "right" }}>Amount</th>
            <th style={{ textAlign: "right" }}>Contribution</th>
            <th style={{ textAlign: "right" }}>Share</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.contribution_id}>
              <td>{row.category}</td>
              <td className="mono-cell">{row.source_level}:{row.source_id}</td>
              <td>{row.method}</td>
              <td style={{ textAlign: "right", fontFamily: "var(--mono)", fontSize: "0.82rem" }}>
                {row.amount != null ? formatMoney(row.amount, currency) : "—"}
              </td>
              <td style={{ textAlign: "right", fontFamily: "var(--mono)", fontSize: "0.82rem" }}>
                {row.contribution != null ? formatMoney(row.contribution, currency) : "—"}
              </td>
              <td style={{ textAlign: "right", color: "var(--text-muted)", fontSize: "0.82rem" }}>
                {row.contribution != null && absTotal > 0
                  ? `${((Math.abs(row.contribution) / absTotal) * 100).toFixed(1)}%`
                  : "—"}
              </td>
              <td>
                <span className={`chip ${row.reconciliation_status === "RECONCILED" ? "chip-ok" : ""}`}>
                  {row.reconciliation_status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── SA component panel ────────────────────────────────────────────────────────

function SaComponentPanel({
  component,
  currency,
  saTotal,
}: {
  component: SaOverview["components"][number];
  currency: string;
  saTotal: number;
}) {
  const breakdown = component.breakdown ?? {};
  const innerBreakdown = (breakdown.buckets ?? breakdown.lines ?? breakdown.risk_classes ?? {}) as Record<string, unknown>;

  return (
    <section className="panel" style={{ marginBottom: 18 }}>
      <div className="panel-header">
        <strong>{component.component} — {component.profile_id}</strong>
        <span className="chip">{formatMoney(component.total_capital, currency)} · {pct(component.total_capital, saTotal)} of SA</span>
      </div>
      <div className="panel-body">
        {Object.keys(innerBreakdown).length > 0 && (
          <>
            <h4 className="panel-section-title">Breakdown</h4>
            <div className="capital-bars" style={{ marginBottom: 18 }}>
              {Object.entries(innerBreakdown).map(([key, val]) => {
                const amount = typeof val === "number" ? val : (typeof val === "object" && val !== null && "capital" in val) ? (val as { capital: number }).capital : 0;
                return (
                  <div key={key} className="bar-row">
                    <span className="bar-label">{key}</span>
                    <div className="bar-track">
                      <div className="bar-fill" style={{ width: `${component.total_capital > 0 ? Math.min(100, (amount / component.total_capital) * 100) : 0}%`, background: "#3b82f6" }} />
                    </div>
                    <span className="bar-amount">{formatMoney(amount, currency)}</span>
                    <span className="bar-pct">{pct(amount, component.total_capital)}</span>
                  </div>
                );
              })}
            </div>
          </>
        )}
        <h4 className="panel-section-title">Top attribution</h4>
        <AttributionTable rows={component.top_attribution} currency={currency} />
      </div>
    </section>
  );
}

// ── Main app ──────────────────────────────────────────────────────────────────

export default function App() {
  const [overview, setOverview] = useState<RunOverview | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState("total");
  const [nodeDetail, setNodeDetail] = useState<NodeDetail | null>(null);
  const [imaDesk, setImaDesk] = useState<ImaDeskView | null>(null);
  const [saOverview, setSaOverview] = useState<SaOverview | null>(null);
  const [imaTab, setImaTab] = useState<ImaTab>("summary");
  const [error, setError] = useState<string | null>(null);

  const runId = overview?.run.run_id ?? "demo-suite-001";
  const currency = overview?.currency ?? "USD";
  const tree = useMemo(() => (overview ? flattenTree(overview.nodes) : []), [overview]);

  useEffect(() => {
    getRun(runId)
      .then(setOverview)
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

  // Which SA component is directly selected?
  const selectedSaComponent = useMemo(() => {
    if (!saOverview) return null;
    if (selectedNodeId === "sa-sbm") return saOverview.components.find((c) => c.component === "SBM") ?? null;
    if (selectedNodeId === "sa-drc" || selectedNodeId.startsWith("sa-drc-"))
      return saOverview.components.find((c) => c.component === "DRC") ?? null;
    if (selectedNodeId === "sa-rrao") return saOverview.components.find((c) => c.component === "RRAO") ?? null;
    return null;
  }, [selectedNodeId, saOverview]);

  const showSaOverview = selectedNodeId === "sa" && saOverview;
  const showImaDesk = !!imaDesk;
  const showSaComponent = !!selectedSaComponent;
  // Don't show generic node detail when a richer panel is shown
  const showNodeDetail = nodeDetail && !showImaDesk && !showSaOverview && !showSaComponent;

  // Capital breakdown bars data
  const capitalBars = useMemo((): BarItem[] => {
    if (!overview) return [];
    const ima = overview.ima_total ?? 0;
    const sa = overview.sa_total ?? 0;
    const bars: BarItem[] = [
      { label: "IMA", amount: ima, color: "#3b82f6" },
      { label: "SA", amount: sa, color: "#0ea5e9" },
    ];
    if (saOverview) {
      for (const comp of saOverview.components) {
        bars.push({ label: `  ${comp.component}`, amount: comp.total_capital, color: "#7dd3fc", indent: true });
      }
    }
    return bars;
  }, [overview, saOverview]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">F</div>
          <div>
            <h1>FRTB Dashboard</h1>
            <p>IMA &amp; SA capital explorer</p>
          </div>
        </div>
        {overview ? (
          <>
            <span className="chip">{overview.run.profile_id}</span>
            <p style={{ color: "#9fb0cb", fontSize: "0.8rem", marginTop: 12 }}>{overview.run.label}</p>
            <p style={{ color: "#9fb0cb", fontSize: "0.75rem", marginTop: 4 }}>{overview.run.calculation_date} · {overview.run.jurisdiction_family}</p>
            <div className="tree-nav">
              {tree.map(({ node, depth }) => (
                <button
                  key={node.node_id}
                  type="button"
                  className={`tree-item ${selectedNodeId === node.node_id ? "active" : ""}`}
                  style={{ paddingLeft: `${10 + depth * 14}px` }}
                  onClick={() => setSelectedNodeId(node.node_id)}
                >
                  {node.label}
                  <span className="amount">{formatMoney(node.amount, node.currency)}</span>
                </button>
              ))}
            </div>
          </>
        ) : null}
      </aside>

      <main className="main">
        <div className="prototype-banner">
          Prototype dashboard — outputs are illustrative only and are not final regulatory capital.
        </div>

        {error ? <div className="alert error">{error}</div> : null}

        {overview ? (
          <>
            <header className="page-header">
              <div>
                <h2>{selectedNode?.label ?? "Capital overview"}</h2>
                <p>
                  As of {overview.run.calculation_date} · {overview.run.jurisdiction_family} ·{" "}
                  {overview.run.components.join(" + ")}
                </p>
              </div>
              <span className="chip">{selectedNode?.component ?? "SUITE"}</span>
            </header>

            {/* Capital breakdown */}
            <section className="panel" style={{ marginBottom: 18 }}>
              <div className="panel-header">
                <strong>Capital composition</strong>
                <span className="chip accent-chip">{formatMoney(overview.suite_total, currency)}</span>
              </div>
              <div className="panel-body">
                <CapitalBars items={capitalBars} total={overview.suite_total ?? 0} currency={currency} />
                <div className="stats-grid" style={{ marginTop: 16 }}>
                  <div className="stat-card accent">
                    <strong>{formatMoney(overview.suite_total, currency)}</strong>
                    <span>Suite total</span>
                  </div>
                  <div className="stat-card">
                    <strong>{formatMoney(overview.ima_total, currency)}</strong>
                    <span>IMA</span>
                  </div>
                  <div className="stat-card">
                    <strong>{formatMoney(overview.sa_total, currency)}</strong>
                    <span>Standardised Approach</span>
                  </div>
                  <div className="stat-card">
                    <strong className="mono-small">{overview.run.input_hash?.slice(0, 12) ?? "—"}</strong>
                    <span>Input hash prefix</span>
                  </div>
                </div>
              </div>
            </section>

            {/* IMA desk detail */}
            {showImaDesk && (
              <section className="panel" style={{ marginBottom: 18 }}>
                <div className="panel-header">
                  <strong>IMA desk — {imaDesk.desk_id}</strong>
                  <span className="chip">{imaDesk.regime} · {imaDesk.eligibility}</span>
                </div>
                <div className="panel-body">
                  <div className="detail-tabs">
                    {(
                      [
                        ["summary", "Summary"],
                        ["imcc", "IMCC / ES"],
                        ["nmrf", "SES & NMRF"],
                        ["pla", "PLA"],
                        ["backtest", "Backtesting"],
                        ["attribution", "Attribution"],
                      ] as const
                    ).map(([id, label]) => (
                      <button
                        key={id}
                        type="button"
                        className={`source-tab ${imaTab === id ? "active" : ""}`}
                        onClick={() => setImaTab(id)}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  {imaTab === "summary" && <SummaryPanel data={imaDesk.summary as Record<string, unknown>} currency={currency} />}
                  {imaTab === "imcc" && <ImccPanel data={imaDesk.imcc as Record<string, unknown>} currency={currency} />}
                  {imaTab === "nmrf" && <NmrfPanel data={imaDesk.ses_nmrf as Record<string, unknown>} currency={currency} />}
                  {imaTab === "pla" && <PlaPanel data={imaDesk.pla as Record<string, unknown>} />}
                  {imaTab === "backtest" && <BacktestPanel data={imaDesk.backtesting as Record<string, unknown>} currency={currency} />}
                  {imaTab === "attribution" && <AttributionTable rows={imaDesk.attributions} currency={currency} />}
                </div>
              </section>
            )}

            {/* SA total overview */}
            {showSaOverview && saOverview && (
              <section className="panel" style={{ marginBottom: 18 }}>
                <div className="panel-header">
                  <strong>Standardised Approach composition</strong>
                  <span className="chip">{formatMoney(saOverview.total_capital, currency)}</span>
                </div>
                <div className="panel-body">
                  <div className="capital-bars" style={{ marginBottom: 18 }}>
                    {saOverview.components.map((comp) => (
                      <div key={comp.component} className="bar-row">
                        <span className="bar-label">{comp.component}</span>
                        <div className="bar-track">
                          <div className="bar-fill" style={{ width: `${saOverview.total_capital > 0 ? (comp.total_capital / saOverview.total_capital) * 100 : 0}%`, background: "#3b82f6" }} />
                        </div>
                        <span className="bar-amount">{formatMoney(comp.total_capital, currency)}</span>
                        <span className="bar-pct">{pct(comp.total_capital, saOverview.total_capital)}</span>
                      </div>
                    ))}
                  </div>
                  {saOverview.components.map((comp) => (
                    <SaComponentPanel
                      key={comp.component}
                      component={comp}
                      currency={currency}
                      saTotal={saOverview.total_capital}
                    />
                  ))}
                </div>
              </section>
            )}

            {/* Individual SA component */}
            {showSaComponent && selectedSaComponent && saOverview && (
              <SaComponentPanel
                component={selectedSaComponent}
                currency={currency}
                saTotal={saOverview.total_capital}
              />
            )}

            {/* Generic node detail (only when no richer panel is shown) */}
            {showNodeDetail && (
              <section className="panel">
                <div className="panel-header">
                  <strong>Node detail</strong>
                  <span className="chip">{nodeDetail.node.node_type}</span>
                </div>
                <div className="panel-body">
                  {nodeDetail.measures.length > 0 && (
                    <div className="stats-grid" style={{ marginBottom: 16 }}>
                      {nodeDetail.measures.map((measure) => (
                        <div key={measure.name} className="stat-card">
                          <strong>{formatValue(measure.value, currency)}</strong>
                          <span>{measure.name}{measure.unit ? ` (${measure.unit})` : ""}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {nodeDetail.attributions.length > 0 && (
                    <>
                      <h4 className="panel-section-title">Attribution</h4>
                      <AttributionTable rows={nodeDetail.attributions} currency={currency} />
                    </>
                  )}
                </div>
              </section>
            )}
          </>
        ) : (
          <p>Loading capital run…</p>
        )}
      </main>
    </div>
  );
}
