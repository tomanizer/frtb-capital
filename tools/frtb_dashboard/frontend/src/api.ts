import type { GridView, ImaDeskView, InspectorView, MetadataView, NodeDetail, RunOverview, RunSummary, SaOverview } from "./types";

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal });
  if (!response.ok) throw new Error(await response.text());
  return (await response.json()) as T;
}

export const listRuns = (signal?: AbortSignal) => request<RunSummary[]>("/api/runs", signal);
export const getRun = (runId: string, hierarchyNodeId: string, signal?: AbortSignal) => {
  const params = new URLSearchParams({ hierarchyNodeId });
  return request<RunOverview>(`/api/runs/${runId}?${params.toString()}`, signal);
};
export const getMetadata = (runId: string, signal?: AbortSignal) => request<MetadataView>(`/api/runs/${runId}/metadata`, signal);
export const getGrid = (runId: string, framework: string, scenario: string, hierarchyNodeId: string, signal?: AbortSignal) => {
  const params = new URLSearchParams({ framework, scenario, hierarchyNodeId });
  return request<GridView>(`/api/runs/${runId}/grid?${params.toString()}`, signal);
};
export const getInspector = (runId: string, rowId: string, scenario: string, hierarchyNodeId: string, signal?: AbortSignal) => {
  const params = new URLSearchParams({ row_id: rowId, scenario, hierarchyNodeId });
  return request<InspectorView>(`/api/runs/${runId}/inspector?${params.toString()}`, signal);
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
