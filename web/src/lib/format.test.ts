import { describe, expect, it } from "vitest";
import { RISK_LABEL, RISK_ORDER, initials, money, num, relativeDate } from "./format";

describe("format helpers", () => {
  it("gera iniciais a partir do nome", () => {
    expect(initials("João da Silva")).toBe("JS");
    expect(initials("Ana")).toBe("A");
    expect(initials("  maria  clara ")).toBe("MC");
  });

  it("lê números de respostas (string ou number)", () => {
    expect(num(4)).toBe(4);
    expect(num("3,5")).toBe(3.5);
    expect(num("8")).toBe(8);
    expect(num("abc")).toBeNull();
    expect(num(null)).toBeNull();
  });

  it("rotula e ordena os níveis de risco", () => {
    expect(RISK_LABEL.green).toBe("Estável");
    expect(RISK_LABEL.red).toBe("Urgente");
    expect(RISK_ORDER.red).toBeGreaterThan(RISK_ORDER.green);
  });

  it("formata data relativa", () => {
    expect(relativeDate(null)).toBe("—");
    expect(relativeDate(new Date().toISOString())).toMatch(/^hoje/);
  });

  it("formata centavos como moeda BRL", () => {
    const s = money(14990);
    expect(s).toMatch(/R\$/);
    expect(s).toContain("149,90");
    expect(money(0)).toContain("0,00");
  });
});
