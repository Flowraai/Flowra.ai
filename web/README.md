# Flowra Care — Painel do médico (web)

Painel do médico em **React + Vite + TypeScript**, consumindo a API do backend.

## Rodar em desenvolvimento

```bash
cd web
npm install
npm run dev          # http://localhost:5173
```

O Vite faz proxy de `/api` para `http://localhost:8000` (o backend) — sem CORS em dev.
Suba o backend antes (`docker compose up` na raiz, ou `uvicorn app.main:app`).

## Build de produção

```bash
npm run build        # tsc (typecheck) + vite build -> web/dist/
npm run preview      # serve a build localmente
```

Sirva `web/dist/` como estático (Nginx, CDN, etc.) e configure a base da API:

```bash
VITE_API_BASE_URL=https://api.exemplo.com.br npm run build
```

## Estrutura

```
src/
  api/         cliente HTTP (JWT), tipos e chamadas por domínio
  auth/        contexto de autenticação (login/sessão)
  components/  AppShell, RiskBadge, ThemeToggle, Sparkline, ChatPanel, ícones
  lib/         tema (claro/escuro/sistema), formatação, hook de fetch
  pages/       Login, Dashboard (painel priorizado), PatientDetail
```

## Telas

- **Login** — autenticação JWT do médico.
- **Painel** — KPIs do dia + lista de pacientes ordenada por risco (🟢🟡🟠🔴), busca e filtros.
- **Detalhe do paciente** — resumo por IA, check-ins recentes, alertas e chat com o paciente.

Tema **claro / escuro / seguir o sistema**, persistido no navegador. A cor de risco é
semântica (separada da cor da marca) e o estado se lê pela forma, não só pela cor.
