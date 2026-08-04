import { describe, expect, it, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Login } from "./Login";
import { AuthProvider } from "../auth/AuthContext";

function renderLogin() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <Login />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("Login", () => {
  beforeEach(() => {
    try {
      localStorage.clear();
    } catch {
      /* ignore */
    }
  });

  it("começa no modo entrar", () => {
    renderLogin();
    expect(screen.getByRole("heading", { name: "Entrar" })).toBeInTheDocument();
    expect(screen.queryByText("Nome")).not.toBeInTheDocument();
  });

  it("alterna para criar conta (mostra o campo Nome)", () => {
    renderLogin();
    fireEvent.click(screen.getByRole("button", { name: "Criar conta" }));
    expect(screen.getByRole("heading", { name: "Criar conta" })).toBeInTheDocument();
    expect(screen.getByText("Nome")).toBeInTheDocument();
  });

  it("mostra o fluxo de recuperar senha", () => {
    renderLogin();
    fireEvent.click(screen.getByRole("button", { name: "Esqueci a senha" }));
    expect(screen.getByRole("heading", { name: "Recuperar acesso" })).toBeInTheDocument();
  });
});
