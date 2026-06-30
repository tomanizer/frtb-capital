import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ImaDeskView, RunOverview, RunSummary, SaOverview } from "./types";

const RUN: RunSummary = {
  run_id: "demo-suite-001",
  label: "Synthetic suite demo",
  calculation_date: "2025-12-31",
  profile_id: "US_NPR_2_0",
  base_currency: "USD",
  jurisdiction_family: "US",
  components: ["IMA", "SA"],
  input_hash: "abcdef0123456789",
  prototype: true,
};

const OVERVIEW: RunOverview = {
  run: RUN,
  ima_total: 6_000_000,
  sa_total: 4_000_000,
  suite_total: 10_000_000,
  currency: "USD",
  nodes: [
    { node_id: "total", parent_id: null, label: "Total capital", node_type: "TOTAL", component: "SUITE", amount: 10_000_000, currency: "USD", child_ids: ["ima", "sa"] },
    { node_id: "ima", parent_id: "total", label: "IMA", node_type: "COMPONENT", component: "IMA", amount: 6_000_000, currency: "USD", child_ids: ["ima-desk-DESK1"] },
    { node_id: "ima-desk-DESK1", parent_id: "ima", label: "Desk DESK1", node_type: "DESK", component: "IMA", amount: 6_000_000, currency: "USD", child_ids: ["ima-pla"] },
    { node_id: "ima-pla", parent_id: "ima-desk-DESK1", label: "PLA add-on", node_type: "MEASURE", component: "IMA", amount: 0, currency: "USD", child_ids: [], provisional: true },
    { node_id: "sa", parent_id: "total", label: "Standardised Approach", node_type: "COMPONENT", component: "SA", amount: 4_000_000, currency: "USD", child_ids: [] },
  ],
};

const SA: SaOverview = {
  total_capital: 4_000_000,
  jurisdiction_family: "US",
  components: [
    { component: "SBM", total_capital: 2_000_000, profile_id: "US_NPR_2_0", input_hash: "h", line_count: 2, breakdown: { risk_classes: { "GIRR:DELTA": 2_000_000 } }, top_attribution: [] },
    { component: "DRC", total_capital: 1_500_000, profile_id: "US_NPR_2_0", input_hash: "h", line_count: 3, breakdown: { buckets: {} }, top_attribution: [] },
    { component: "RRAO", total_capital: 500_000, profile_id: "US_NPR_2_0", input_hash: "h", line_count: 1, breakdown: { lines: {} }, top_attribution: [] },
  ],
};

const DESK: ImaDeskView = {
  desk_id: "DESK1",
  regime: "IMA",
  eligibility: "ELIGIBLE",
  summary: { models_based_capital: 6_000_000, supervisory_multiplier: 1.5, binding_term: "imcc", imcc: 5_000_000, total_ses: 1_000_000 },
  imcc: { imcc: 5_000_000, unconstrained_lha_es: 4_800_000, constrained_lha_es: 5_000_000 },
  ses_nmrf: { total_ses: 1_000_000, classifications: {}, methods: {}, selected_stress_periods: {} },
  pla: { zone: "GREEN", ks_statistic: 0.04, window_size: 250, add_on_status: "NOT_MODELLED" },
  backtesting: { apl_zone: "GREEN", hpl_zone: "GREEN", apl_exceptions: 1, hpl_exceptions: 2, window_size: 250 },
  attributions: [
    { contribution_id: "a1", component: "frtb_ima", category: "IMCC", source_level: "desk", source_id: "DESK1", method: "EULER", amount: 5_000_000, contribution: 5_000_000, reconciliation_status: "RECONCILED", reason: "" },
    { contribution_id: "a2", component: "frtb_ima", category: "SES", source_level: "rf", source_id: "RF9", method: "DIRECT", amount: 1_000_000, contribution: 1_000_000, reconciliation_status: "UNSUPPORTED", reason: "non-additive" },
  ],
};

vi.mock("./api", async () => {
  const actual = await vi.importActual<typeof import("./api")>("./api");
  return {
    ...actual,
    listRuns: vi.fn(async () => [RUN]),
    getRun: vi.fn(async () => OVERVIEW),
    getSa: vi.fn(async () => SA),
    getImaDesk: vi.fn(async () => DESK),
    getNode: vi.fn(async () => ({ node: OVERVIEW.nodes[0], measures: [], attributions: [] })),
  };
});

import App from "./App";

beforeEach(() => {
  vi.clearAllMocks();
  window.history.replaceState(null, "", "/");
});

describe("App", () => {
  it("renders the run overview with suite total and capital stack", async () => {
    render(<App />);
    expect(await screen.findByText("Capital mix")).toBeInTheDocument();
    expect(screen.getAllByText("$10,000,000").length).toBeGreaterThan(0);
    expect(screen.getByRole("combobox", { name: /capital run/i })).toBeInTheDocument();
  });

  it("drills into an IMA desk and shows accessible tabs", async () => {
    render(<App />);
    const deskNav = await screen.findByRole("button", { name: /Desk DESK1/ });
    await userEvent.click(deskNav);

    const tablist = await screen.findByRole("tablist", { name: /node workbench/i });
    expect(within(tablist).getByRole("tab", { name: "PLA" })).toBeInTheDocument();

    // PLA tab surfaces the "not modelled" honesty note.
    await userEvent.click(within(tablist).getByRole("tab", { name: "PLA" }));
    expect(await screen.findByText(/not modelled/i)).toBeInTheDocument();
  });

  it("filters attribution rows by reconciliation status", async () => {
    render(<App />);
    await userEvent.click(await screen.findByRole("button", { name: /Desk DESK1/ }));
    const tablist = await screen.findByRole("tablist", { name: /node workbench/i });
    await userEvent.click(within(tablist).getByRole("tab", { name: "Attribution" }));

    // Both rows visible under "All".
    expect(await screen.findByText("UNSUPPORTED")).toBeInTheDocument();
    expect(screen.getByText("RECONCILED")).toBeInTheDocument();

    // "Reconciled" filter hides the unsupported row.
    await userEvent.click(screen.getByRole("button", { name: "Reconciled" }));
    await waitFor(() => expect(screen.queryByText("UNSUPPORTED")).not.toBeInTheDocument());
    expect(screen.getByText("RECONCILED")).toBeInTheDocument();
  });

  it("shows a breadcrumb path when drilling down", async () => {
    render(<App />);
    await userEvent.click(await screen.findByRole("button", { name: /Desk DESK1/ }));
    const breadcrumb = await screen.findByRole("navigation", { name: /breadcrumb/i });
    expect(within(breadcrumb).getByText("Total capital")).toBeInTheDocument();
  });

  it("reflects the selected node in the URL for deep-linking", async () => {
    render(<App />);
    await userEvent.click(await screen.findByRole("button", { name: /Desk DESK1/ }));
    await waitFor(() => expect(window.location.search).toContain("node=ima-desk-DESK1"));
  });

  it("restores the active tab from the URL (deep link)", async () => {
    window.history.replaceState(null, "", "/?node=ima-desk-DESK1&tab=pla");
    render(<App />);
    // Wait for the desk to load (PLA tab only exists once kind === "ima").
    const plaTab = await screen.findByRole("tab", { name: "PLA" });
    await waitFor(() => expect(plaTab).toHaveAttribute("aria-selected", "true"));
    // PLA content (not the summary tab) is what renders.
    expect(await screen.findByText(/not modelled/i)).toBeInTheDocument();
  });

  it("renders a reconciliation strip over the attribution table", async () => {
    render(<App />);
    await userEvent.click(await screen.findByRole("button", { name: /Desk DESK1/ }));
    const tablist = await screen.findByRole("tablist", { name: /node workbench/i });
    await userEvent.click(within(tablist).getByRole("tab", { name: "Attribution" }));
    expect(await screen.findByText(/rows shown/i)).toBeInTheDocument();
    expect(screen.getByText(/need review/i)).toBeInTheDocument();
  });
});
