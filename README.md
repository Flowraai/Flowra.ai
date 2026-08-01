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
| PATCH | `/api/v1/auth/me` | Edita o perfil do médico (clínica, contatos de notificação, etc.) |
| POST | `/api/v1/patients` | Cadastra paciente (exige consentimento LGPD); retorna o **token do paciente uma única vez** |
| GET  | `/api/v1/patients` | **Painel**: pacientes ordenados por risco |
| GET  | `/api/v1/patients/{id}` | Detalhe do paciente |
| PATCH | `/api/v1/patients/{id}` | Edita paciente e ativa/desativa (`is_active`) |
| GET  | `/api/v1/patients/{id}/export` | Exporta todos os dados do paciente (portabilidade LGPD) |
| DELETE | `/api/v1/patients/{id}` | Apaga o paciente e seus dados de saúde (eliminação LGPD) |
| GET  | `/api/v1/patients/{id}/checkins` | Histórico de check-ins |
| POST | `/api/v1/patients/{id}/rotate-token` | Gera novo token do paciente |
| POST | `/api/v1/patients/{id}/resend-onboarding` | Gera novo token e reenvia o link de acesso ao paciente |
| POST | `/api/v1/patients/scan-inactivity` | Gera alertas de não-adesão (pacientes sem check-in) |
| POST | `/api/v1/notifications/test` | Envia notificação de teste (valida os canais do médico) |
| GET  | `/api/v1/protocols/active` | Protocolo psiquiátrico ativo |
| POST | `/api/v1/patients/{id}/medications` | Cria plano de medicação (nome, dose, horários, duração) |
| GET  | `/api/v1/patients/{id}/medications` | Lista planos de medicação do paciente |
| PATCH | `/api/v1/medications/{plan_id}` | Edita/desativa um plano |
| GET  | `/api/v1/patients/{id}/medications/adherence` | Resumo de adesão à medicação |
| GET  | `/api/v1/alerts` | Lista de alertas (filtro por status) |
| PATCH| `/api/v1/alerts/{id}` | Atualiza status do alerta |

Perfil **paciente** (token opaco — header `X-Patient-Token: <token>`):

| Método | Rota | Descrição |
|---|---|---|
| GET  | `/api/v1/patient/today` | Estado do dia (já fez o check-in?) para o app |
| GET  | `/api/v1/patient/medications/today` | Doses de medicação de hoje |
| POST | `/api/v1/patient/medications/intakes/{id}/respond` | Responde a uma dose (✓/⏰/❌) |
| GET  | `/api/v1/patient/protocol` | Perguntas do dia para renderizar |
| POST | `/api/v1/patient/checkins` | Envia o check-in diário (validado; **um por dia** — 2º envio no mesmo dia → 409) |

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

**Risco por tendência** (`app/risk/trend.py`): além do risco pontual de cada check-in,
a janela recente é analisada para detectar "padrão de piora" — risco elevado sustentado,
humor em queda e não-adesão repetida. O índice do paciente (`current_risk`) é o **maior**
entre o risco do check-in atual e o da tendência.

**Lembretes de medicação** (`app/services/medication_service.py`): o médico configura
o plano (nome/dose/horários/duração); o agendador `python -m app.scripts.scan_medications`
(cron) cria as doses que venceram, envia o lembrete pelos canais e marca como "não tomou"
as doses pendentes de dias anteriores. O app do paciente lista as doses do dia e responde
✓/⏰/❌. A adesão é resumida em `/patients/{id}/medications/adherence`.

**Não-adesão** (`app/services/inactivity_service.py`): pacientes ativos sem check-in há
`INACTIVITY_ALERT_DAYS` dias geram um alerta de rotina (idempotente). Dispare por
`POST /patients/scan-inactivity` (médico) ou pelo job `python -m app.scripts.scan_inactivity`
(cron). O painel expõe `days_since_checkin` e `inactive` por paciente.

### Notificações ao médico

Quando um check-in gera 🟠/🔴, o alerta é despachado para os **canais configurados**
(`NOTIFICATION_CHANNELS`) e **cada entrega é registrada** na tabela `notifications`
(auditável): canal, destino, status (`queued`/`sent`/`failed`) e erro. A falha de um
canal nunca derruba o check-in.

- `log` (default) — sempre disponível, roda sem configuração.
- `email` — SMTP (defina `SMTP_HOST`/`SMTP_FROM` e afins).
- `webhook` — POST `{target, subject, body}` para `NOTIFICATION_WEBHOOK_URL` (ponte genérica).
- `whatsapp` — Meta Cloud API (`WHATSAPP_PHONE_NUMBER_ID`/`WHATSAPP_ACCESS_TOKEN`).
  Destino é **telefone**; fora da janela de 24h a Meta exige uma template aprovada
  (`WHATSAPP_TEMPLATE_NAME`).

O destino é resolvido **por canal**: WhatsApp usa o telefone (`Doctor.notification_phone`
para alertas; `contact` do paciente para onboarding); os demais canais usam e-mail. Se o
contato exigido por um canal não existir, aquela entrega é registrada como `failed`.

As listas do painel (`/patients`, `/patients/{id}/checkins`, `/alerts`) aceitam
`limit`/`offset` para paginação (com limites máximos por rota).

O destino é o `notification_email` do médico (se definido no cadastro) ou o e-mail de
login. 🔴 vira notificação urgente; 🟠, de rotina. `POST /notifications/test` envia uma
mensagem de teste pelos canais ativos e retorna o resultado por canal — útil para
validar SMTP/webhook em produção sem esperar um alerta.

**Onboarding do paciente**: ao cadastrar (se houver `contact`), o Flowra Care envia
automaticamente o link de acesso ao paciente pelos canais configurados
(`PATIENT_APP_URL_BASE` monta o link do app). `POST /patients/{id}/resend-onboarding`
gera um novo token e reenvia o link.

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

## Multi-tenant (fundação)

Toda conta é um **tenant** (`tenants`): uma **clínica** (quando há nome de clínica no
cadastro) ou um **profissional autônomo** (`solo`). Médicos e pacientes carregam
`tenant_id`, e o tenant tem um `config` (JSONB) para configuração por conta. Neste
primeiro passo a **visibilidade continua por médico** — o `tenant_id` fica assentado
como base para os próximos módulos (config por tenant, compartilhamento por clínica,
papéis). O tenant aparece em `/auth/me` (`tenant_id`, `tenant_name`).

## Compliance (não deixar para depois)

- **LGPD** — dado de saúde é categoria sensível: consentimento explícito é exigido no
  cadastro do paciente (`consent_given`), IDs são UUID (não enumeráveis), e o token do
  paciente é armazenado apenas como hash. **Direitos do titular**: exportação
  (`GET /patients/{id}/export`, portabilidade) e eliminação (`DELETE /patients/{id}`) —
  a exclusão remove paciente/check-ins/alertas/notificações por cascata e **preserva o
  log de auditoria** (referencia só IDs). Em produção, habilite **criptografia em
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
reset de senha com revogação de sessões); risco por tendência ("padrão de piora")
combinado ao risco pontual; detecção de não-adesão (paciente sem check-in) com
alerta idempotente, endpoint e job para cron; direitos do titular LGPD
(exportação e eliminação de dados, com auditoria preservada).

> Nota: o rate limiting é em memória (uma instância). Para múltiplas
> instâncias/workers, trocar por um backend compartilhado (ex.: Redis) mantendo
> a mesma interface em `app/core/rate_limit.py`.
