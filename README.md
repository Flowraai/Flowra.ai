# Flowra Care — Backend (MVP Psiquiatria)

Backend do **Flowra Care**, produto de **monitoramento contínuo entre consultas**.
O médico cadastra o tratamento (protocolo psiquiátrico pré-definido), o paciente
faz um **check-in diário (< 1 min)**, e uma camada de risco (regras determinísticas
+ análise do texto/áudio livre) prioriza os casos e alerta o médico **somente quando
necessário**.

> ⚠️ **A IA não diagnostica.** É ferramenta de apoio à priorização de casos por
> risco e **não substitui o julgamento clínico**.

Este repositório corresponde ao escopo de **backend da Fase 1 (MVP técnico)** do
planejamento de produto. Frontend do paciente (app/PWA) e painel médico (web) são
clientes desta API.

---

## Stack

- **Python 3.11+ / FastAPI** (async)
- **PostgreSQL** via **SQLAlchemy 2.0 (async) + asyncpg**
- **Alembic** para migrações
- **JWT** (perfil médico) + **token opaco** (perfil paciente)
- Sem dependência de serviço externo para rodar o MVP (analisador de texto livre
  determinístico por padrão; LLM é plugável).

## Estrutura

```
app/
  core/        config e segurança (senha, JWT, token de paciente)
  db/          base declarativa, engine/sessão async
  models/      Paciente, Médico, Protocolo, CheckIn, Alerta, AuditLog, User
  protocol/    definição do protocolo psiquiátrico (fonte única das perguntas)
  risk/        motor de risco (regras) + análise do texto livre (IA plugável)
  schemas/     contratos Pydantic da API
  services/    orquestração do check-in, auditoria, notificações
  api/         rotas (auth, patients, protocols, checkins, alerts, patient app)
  scripts/     init_db (dev) e seed do protocolo
alembic/       migrações (produção)
tests/         motor de risco, texto livre e smoke da API
```

## Como rodar

### Opção A — Docker (recomendado)

```bash
cp .env.example .env
docker compose up --build
# API em http://localhost:8000 — docs interativas em /docs
```

O container da API roda o `init_db` (cria tabelas + popula o protocolo) e sobe o servidor.

### Opção B — Local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # ajuste DATABASE_URL e JWT_SECRET_KEY
# suba um Postgres e então:
python -m app.scripts.init_db   # cria tabelas e popula o protocolo psiquiátrico
uvicorn app.main:app --reload
```

### Migrações (produção)

Em produção, use Alembic em vez do `init_db`:

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
python -m app.scripts.seed_protocol
```

## Fluxo da API (resumo)

Perfil **médico** (JWT — `Authorization: Bearer <token>`):

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/v1/auth/register` | Cadastra médico, retorna access + refresh token |
| POST | `/api/v1/auth/login` | Login (rate-limited), retorna access + refresh token |
| POST | `/api/v1/auth/refresh` | Renova a sessão (rotaciona o refresh token) |
| POST | `/api/v1/auth/forgot-password` | Solicita redefinição (resposta genérica) |
| POST | `/api/v1/auth/reset-password` | Redefine a senha via token (revoga sessões) |
| GET  | `/api/v1/auth/me` | Perfil do médico |
| POST | `/api/v1/patients` | Cadastra paciente (exige consentimento LGPD); retorna o **token do paciente uma única vez** |
| GET  | `/api/v1/patients` | **Painel**: pacientes ordenados por risco |
| GET  | `/api/v1/patients/{id}` | Detalhe do paciente |
| GET  | `/api/v1/patients/{id}/checkins` | Histórico de check-ins |
| POST | `/api/v1/patients/{id}/rotate-token` | Gera novo token do paciente |
| GET  | `/api/v1/protocols/active` | Protocolo psiquiátrico ativo |
| GET  | `/api/v1/alerts` | Lista de alertas (filtro por status) |
| PATCH| `/api/v1/alerts/{id}` | Atualiza status do alerta |

Perfil **paciente** (token opaco — header `X-Patient-Token: <token>`):

| Método | Rota | Descrição |
|---|---|---|
| GET  | `/api/v1/patient/protocol` | Perguntas do dia para renderizar |
| POST | `/api/v1/patient/checkins` | Envia o check-in diário (respostas validadas contra o protocolo) |

## Índice de risco

Calculado a cada check-in de forma **conservadora** (preferir falso positivo a falso
negativo). O risco final é sempre o **maior** entre as contribuições de cada categoria
e do texto livre.

| Nível | | Ação |
|---|---|---|
| 🟢 `green` | Estável | Nenhuma |
| 🟡 `yellow` | Atenção | Monitorar |
| 🟠 `orange` | Acompanhamento | Alerta ao médico (não urgente) |
| 🔴 `red` | Alta prioridade | Alerta imediato ao médico |

Regras e limiares ficam em `app/risk/engine.py` (`RiskThresholds`) e as palavras-chave
do texto livre em `app/risk/free_text.py`. **Ambos devem ser revisados com um médico
consultor antes do piloto** (Fase 2).

### Notificações ao médico

Quando um check-in gera 🟠/🔴, o alerta é despachado para os **canais configurados**
(`NOTIFICATION_CHANNELS`) e **cada entrega é registrada** na tabela `notifications`
(auditável): canal, destino, status (`queued`/`sent`/`failed`) e erro. A falha de um
canal nunca derruba o check-in.

- `log` (default) — sempre disponível, roda sem configuração.
- `email` — SMTP (defina `SMTP_HOST`/`SMTP_FROM` e afins).
- `webhook` — POST `{target, subject, body}` para `NOTIFICATION_WEBHOOK_URL`
  (ponte para WhatsApp/push).

O destino é o e-mail do médico responsável. 🔴 vira notificação urgente; 🟠, de rotina.

### IA no texto livre

O contrato é `FreeTextAnalyzer.analyze(text) -> FreeTextResult`. O padrão do MVP é o
`KeywordFreeTextAnalyzer` (determinístico, auditável, roda sem chave).

Para usar um **LLM**, configure `FREE_TEXT_ANALYZER=llm` e aponte para qualquer endpoint
**compatível com a API OpenAI** (`LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`) — funciona
com OpenAI, Azure, Gemini (endpoint compat), Groq, OpenRouter, modelos locais, etc. O
resultado do LLM é **combinado de forma conservadora** com o determinístico (mantém o
maior risco), e qualquer erro/ausência de chave faz cair no determinístico (nunca
silencia um sinal). A chamada roda numa thread para não bloquear o event loop.

> Áudio (upload + transcrição/speech-to-text) ainda não está implementado — o campo
> `audio_url` existe, mas o pipeline de áudio fica para uma próxima etapa.

## Compliance (não deixar para depois)

- **LGPD** — dado de saúde é categoria sensível: consentimento explícito é exigido no
  cadastro do paciente (`consent_given`), IDs são UUID (não enumeráveis), e o token do
  paciente é armazenado apenas como hash. Em produção, habilite **criptografia em
  repouso** no provedor de banco e mantenha **isolamento** em relação à Flowra AI (CRM).
- **Auditoria** — `audit_logs` registra check-ins, cálculos de risco, alertas gerados e
  ações do médico (proteção jurídica para a plataforma e para o médico).
- **Responsabilidade** — a API deixa explícito que a IA não diagnostica; o retorno do
  check-in ao paciente é neutro (não expõe o risco calculado ao próprio paciente).

## Testes

```bash
pytest            # motor de risco, texto livre e smoke da API (sem banco)
```

## Próximos passos (backend)

- Upload/transcrição de áudio (speech-to-text) para alimentar o campo livre.
- Onboarding do paciente: entrega do link/token via WhatsApp/app.
- Segurança extra: refresh token, reset de senha, rate limiting.
- Ajuste fino dos limiares de risco com médico consultor (Fase 2).
- Endpoints de exportação/relatório para o painel.

Já entregue: migração inicial versionada + CI (lint, migração e testes com Postgres);
testes de integração ponta a ponta; notificação plugável com registro de entrega;
análise do texto livre por LLM (endpoint compatível com OpenAI) combinada de forma
conservadora com o determinístico; validação das respostas do check-in contra o
protocolo (tipos, escalas, opções, obrigatoriedade e campos inesperados → 422);
hardening de autenticação (rate limiting no login, refresh token com rotação e
reset de senha com revogação de sessões).

> Nota: o rate limiting é em memória (uma instância). Para múltiplas
> instâncias/workers, trocar por um backend compartilhado (ex.: Redis) mantendo
> a mesma interface em `app/core/rate_limit.py`.
