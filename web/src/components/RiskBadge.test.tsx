import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { RiskBadge } from "./RiskBadge";

describe("RiskBadge", () => {
  it("mostra o rótulo do nível", () => {
    render(<RiskBadge level="orange" />);
    expect(screen.getByText("Acompanhar")).toBeInTheDocument();
  });

  it("aceita rótulo customizado", () => {
    render(<RiskBadge level="red" label="Risco: Urgente" />);
    expect(screen.getByText("Risco: Urgente")).toBeInTheDocument();
  });
});
