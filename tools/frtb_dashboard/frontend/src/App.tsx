import { useEffect, useMemo, useState } from "react";
import { formatMoney, getImaDesk, getNode, getRun, getSa } from "./api";
import type { AttributionRow, CapitalNode, ImaDeskView, NodeDetail, RunOverview, SaOverview } from "./types";

type ImaTab = "summary" | "imcc" | "nmrf" | "pla" | "backtest" | "attribution";

function flattenTree(nodes: CapitalNode[], parentId: string | null = null, depth = 0): Array<{ node: CapitalNode; depth: number }> {
  const children = nodes.filter((node) => node.parent_id === parentId);
  return children.flatMap((node) => [{ node, depth }, ...flattenTree(nodes, node.node_id, depth + 1)]);
}

function AttributionTable({ rows }: { rows: AttributionRow[] }) {
  if (!rows.length) return <p className="alias-list">No attribution rows for this view.</p>;
  return (
    <div className="preview-table-wrap">
      <table className="preview-table">
        <thead>
          <tr>
            <th>Category</th>
            <th>Source</th>
            <th>Method</th>
            <th>Contribution</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.contribution_id}>
              <td>{row.category}</td>
              <td>
                {row.source_level}:{row.source_id}
              </td>
              <td>{row.method}</td>
              <td>{row.contribution?.toLocaleString() ?? "—"}</td>
              <td>{row.reconciliation_status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function KeyValueGrid({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="dataset-grid">
      {Object.entries(data).map(([key, value]) => (
        <div key={key} className="stat-card">
          <strong>{typeof value === "number" ? value.toLocaleString() : String(value ?? "—")}</strong>
          <span>{key}</span>
        </div>
      ))}
    </div>
  );
}

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

            <div className="stats-grid">
              <div className="stat-card">
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
                <strong>{overview.run.input_hash?.slice(0, 12) ?? "—"}</strong>
                <span>Input hash prefix</span>
              </div>
            </div>

            {imaDesk ? (
              <section className="panel" style={{ marginBottom: 18 }}>
                <div className="panel-header">
                  <strong>IMA desk — {imaDesk.desk_id}</strong>
                  <span className="chip">{imaDesk.eligibility}</span>
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
                  {imaTab === "summary" ? <KeyValueGrid data={imaDesk.summary} /> : null}
                  {imaTab === "imcc" ? <KeyValueGrid data={imaDesk.imcc} /> : null}
                  {imaTab === "nmrf" ? <KeyValueGrid data={imaDesk.ses_nmrf} /> : null}
                  {imaTab === "pla" ? <KeyValueGrid data={imaDesk.pla} /> : null}
                  {imaTab === "backtest" ? (
                    <pre className="code-block">{JSON.stringify(imaDesk.backtesting, null, 2)}</pre>
                  ) : null}
                  {imaTab === "attribution" ? <AttributionTable rows={imaDesk.attributions} /> : null}
                </div>
              </section>
            ) : null}

            {selectedNodeId === "sa" && saOverview ? (
              <section className="panel" style={{ marginBottom: 18 }}>
                <div className="panel-header">
                  <strong>SA composition</strong>
                  <span className="chip">{formatMoney(saOverview.total_capital, currency)}</span>
                </div>
                <div className="panel-body">
                  {saOverview.components.map((component) => (
                    <div key={component.component} className="panel" style={{ marginBottom: 12, boxShadow: "none" }}>
                      <div className="panel-header">
                        <strong>{component.component}</strong>
                        <span>{formatMoney(component.total_capital, currency)}</span>
                      </div>
                      <div className="panel-body">
                        <AttributionTable rows={component.top_attribution} />
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            ) : null}

            {nodeDetail ? (
              <section className="panel">
                <div className="panel-header">
                  <strong>Node detail</strong>
                  <span className="chip">{nodeDetail.node.node_type}</span>
                </div>
                <div className="panel-body">
                  <div className="stats-grid">
                    {nodeDetail.measures.map((measure) => (
                      <div key={measure.name} className="stat-card">
                        <strong>{String(measure.value ?? "—")}</strong>
                        <span>{measure.name}</span>
                      </div>
                    ))}
                  </div>
                  <h3>Attribution</h3>
                  <AttributionTable rows={nodeDetail.attributions} />
                </div>
              </section>
            ) : null}
          </>
        ) : (
          <p>Loading capital run…</p>
        )}
      </main>
    </div>
  );
}
