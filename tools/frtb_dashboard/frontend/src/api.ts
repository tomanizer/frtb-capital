import type { ImaDeskView, NodeDetail, RunOverview, SaOverview } from "./types";

async function request<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(await response.text());
  return (await response.json()) as T;
}

export const listRuns = () => request<import("./types").RunSummary[]>("/api/runs");
export const getRun = (runId: string) => request<RunOverview>(`/api/runs/${runId}`);
export const getNode = (runId: string, nodeId: string) =>
  request<NodeDetail>(`/api/runs/${runId}/nodes/${nodeId}`);
export const getImaDesk = (runId: string, deskId: string) =>
  request<ImaDeskView>(`/api/runs/${runId}/ima/desks/${deskId}`);
export const getSa = (runId: string) => request<SaOverview>(`/api/runs/${runId}/sa`);

export function formatMoney(value: number | null | undefined, currency: string) {
  if (value == null || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}
