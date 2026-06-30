import { describe, expect, it } from "vitest";
import { formatValue, reconClass } from "./App";

describe("formatValue", () => {
  it("does not money-format plain counts (regression: magnitude heuristic)", () => {
    // A count like 1,250 exceptions must not render as currency.
    expect(formatValue(1250, "USD")).toBe("1,250");
    expect(formatValue(1250, "USD", "count")).toBe("1,250");
  });

  it("formats money only when explicitly asked", () => {
    expect(formatValue(2_500_000, "USD", "money")).toContain("$");
    expect(formatValue(2_500_000, "USD")).not.toContain("$");
  });

  it("keeps small fractional statistics readable", () => {
    expect(formatValue(0.0423, "USD")).toBe("0.0423");
  });

  it("handles null and NaN", () => {
    expect(formatValue(null, "USD")).toBe("-");
    expect(formatValue(Number.NaN, "USD")).toBe("-");
  });
});

describe("reconClass", () => {
  it("maps reconciliation status to chip variants", () => {
    expect(reconClass("RECONCILED")).toBe("status-chip ok");
    expect(reconClass("PARTIAL_RESIDUAL")).toBe("status-chip warn");
    expect(reconClass("UNSUPPORTED")).toBe("status-chip unsupported");
  });
});
