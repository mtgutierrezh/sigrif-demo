import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RiskBadge } from "./RiskBadge";

describe("RiskBadge", () => {
  it("renders the level with its risk class", () => {
    render(<RiskBadge level="Alto" />);

    const badge = screen.getByText("Alto");
    expect(badge).toHaveClass("badge", "risk-high");
  });

  it("renders the no-data state", () => {
    render(<RiskBadge level="Sin dato" />);

    expect(screen.getByText("Sin dato")).toHaveClass("risk-none");
  });
});
