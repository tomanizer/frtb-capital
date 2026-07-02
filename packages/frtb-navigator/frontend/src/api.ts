import type { ArtifactDetailView, ArtifactSummaryView, GridView, ImaDeskView, InspectorView, MetadataView, NodeDetail, RunOverview, RunSummary, SaOverview } from "./types";

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal });
  if (!response.ok) throw new Error(await response.text());
  return (await response.json()) as T;
}

export const listRuns = (source: string, signal?: AbortSignal) => {
  const params = new URLSearchParams({ source });
  return request<RunSummary[]>(`/api/runs?${params.toString()}`, signal);
};
export const getRun = (source: string, runId: string, hierarchyNodeId: string, signal?: AbortSignal) => {
  const params = new URLSearchParams({ source, hierarchyNodeId });
  return request<RunOverview>(`/api/runs/${encodeURIComponent(runId)}?${params.toString()}`, signal);
};
export const getMetadata = (source: string, runId: string, signal?: AbortSignal) => {
  const params = new URLSearchParams({ source });
  return request<MetadataView>(`/api/runs/${encodeURIComponent(runId)}/metadata?${params.toString()}`, signal);
};
export const getGrid = (source: string, runId: string, framework: string, scenario: string, hierarchyNodeId: string, signal?: AbortSignal) => {
  const params = new URLSearchParams({ source, framework, scenario, hierarchyNodeId });
  return request<GridView>(`/api/runs/${encodeURIComponent(runId)}/grid?${params.toString()}`, signal);
};
export const getInspector = (source: string, runId: string, rowId: string, scenario: string, hierarchyNodeId: string, signal?: AbortSignal) => {
  const params = new URLSearchParams({ source, row_id: rowId, scenario, hierarchyNodeId });
  return request<InspectorView>(`/api/runs/${encodeURIComponent(runId)}/inspector?${params.toString()}`, signal);
};
export const getArtifacts = (source: string, runId: string, framework: string, scenario: string, hierarchyNodeId: string, rowId: string | null, signal?: AbortSignal) => {
  const params = new URLSearchParams({ source, framework, scenario, hierarchyNodeId });
  if (rowId) params.set("row_id", rowId);
  return request<ArtifactSummaryView>(`/api/runs/${encodeURIComponent(runId)}/artifacts?${params.toString()}`, signal);
};
export const getArtifactDetail = (source: string, runId: string, artifactId: string, signal?: AbortSignal) => {
  const params = new URLSearchParams({ source, limit: "50" });
  return request<ArtifactDetailView>(`/api/runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifactId)}?${params.toString()}`, signal);
};
export const getNode = (runId: string, nodeId: string, signal?: AbortSignal) =>
  request<NodeDetail>(`/api/runs/${runId}/nodes/${nodeId}`, signal);
export const getImaDesk = (runId: string, deskId: string, signal?: AbortSignal) =>
  request<ImaDeskView>(`/api/runs/${runId}/ima/desks/${deskId}`, signal);
export const getSa = (runId: string, signal?: AbortSignal) => request<SaOverview>(`/api/runs/${runId}/sa`, signal);

export function formatMoney(value: number | null | undefined, currency: string) {
  if (value == null || Number.isNaN(value)) return "n/a";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}
