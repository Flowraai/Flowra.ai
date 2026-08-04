import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Subscribe } from "./Subscribe";
import { AuthProvider } from "../auth/AuthContext";

function jsonRes(data: unknown) {
  return Promise.resolve({
    ok: true,
    status: 200,
    json: async () => data,
  } as Response);
}

function mockApi() {
  global.fetch = vi.fn((input: RequestInfo | URL) => {
    const u = String(input);
    if (u.includes("/billing/subscription")) {
      return jsonRes({ status: "pending", plan: null, current_period_end: null, trial_end: null, card_last4: null, checkout_url: null });
    }
    if (u.includes("/billing/plans")) {
      return jsonRes([
        { id: "p1", name: "Essencial", description: "Ideal para começar", price_cents: 14990, cycle: "monthly", patient_limit: 50, trial_days: 7 },
      ]);
    }
    return jsonRes({});
  }) as unknown as typeof fetch;
}

describe("Subscribe", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("mostra os planos ativos e o preço formatado", async () => {
    mockApi();
    render(
      <MemoryRouter>
        <AuthProvider>
          <Subscribe />
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(await screen.findByText("Essencial")).toBeInTheDocument();
    expect(screen.getByText(/149,90/)).toBeInTheDocument();
    expect(screen.getByText(/7 dias de teste grátis/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Assinar e ir para o pagamento/ })).toBeInTheDocument();
  });
});
