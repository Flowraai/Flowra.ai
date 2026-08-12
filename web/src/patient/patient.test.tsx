import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Checkin } from "./Checkin";

function jsonRes(data: unknown) {
  return Promise.resolve({ ok: true, status: 200, json: async () => data } as Response);
}

const PROTOCOL = {
  id: "pr1",
  name: "Psiquiatria",
  questions: [
    { id: "q1", code: "mood", category: "humor", text: "Como está seu humor?", type: "scale", position: 1, required: true, options: { min: 0, max: 10 } },
    { id: "q2", code: "livre", category: "livre", text: "Quer contar algo?", type: "free_text", position: 2, required: false, options: null },
  ],
};

describe("Tela do paciente — Check-in", () => {
  afterEach(() => vi.restoreAllMocks());

  it("renderiza as perguntas e libera o envio ao responder", async () => {
    globalThis.fetch = vi.fn(() => jsonRes(PROTOCOL)) as unknown as typeof fetch;
    render(<Checkin onDone={() => {}} onCancel={() => {}} />);

    // pergunta aparece
    expect(await screen.findByText("Como está seu humor?")).toBeInTheDocument();

    // antes de responder, o botão pede a pergunta obrigatória
    expect(screen.getByRole("button", { name: /Responda 1 pergunta/ })).toBeInTheDocument();

    // responde a escala (clica no "7")
    fireEvent.click(screen.getByRole("button", { name: "7" }));

    // agora libera o envio
    expect(screen.getByRole("button", { name: "Enviar check-in" })).toBeInTheDocument();
  });
});
