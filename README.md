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

### Opção A — Docker (desenvolvimento)

```bash
docker compose up --build
# API em http://localhost:8000 — docs interativas em /docs
```

O `docker-entrypoint.sh` aplica as migrações (`alembic upgrade head`) e, no dev,
popula o protocolo (`SEED_PROTOCOL=true`) antes de subir a API.

### Opção B — Local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # ajuste DATABASE_URL e JWT_SECRET_KEY
# suba um Postgres e então:
python -m app.scripts.init_db   # cria tabelas e popula o protocolo psiquiátrico
uvicorn app.main:app --reload
```

### Produção (Docker)

```bash
cp .env.example .env   # preencha JWT_SECRET_KEY, ENCRYPTION_KEY, DATABASE_URL, ...
docker compose -f docker-compose.prod.yml up -d --build
```

- **Imagem** multi-stage (deps num virtualenv isolado), roda como usuário **não-root**,
  serve via **gunicorn + UvicornWorker** (`WEB_CONCURRENCY` workers).
- **Entrypoint** aplica `alembic upgrade head` no boot (`RUN_MIGRATIONS`, seed via
  `SEED_PROTOCOL`).
- **Health checks**: `/health/live` (liveness, não toca no banco) e `/health/ready`
  (readiness — verifica o banco, retorna **503** se indisponível). O `HEALTHCHECK` do
  container e o compose de produção usam esses endpoints.
- **Guardrails de produção** rodam no startup (ver seção Compliance): abortam com
  `JWT_SECRET_KEY` padrão ou `DEBUG=true`.
- **Observabilidade**: logs estruturados em **JSON** (`LOG_FORMAT=json`) com `request_id`
  por requisição (aceita/propaga `X-Request-ID`); o log de acesso registra método, rota,
  status e duração — **sem** query string nem corpo (evita vazar dado sensível).
- **Uploads** persistem em volume (`STORAGE_DIR=/data/uploads`); em escala, troque por
  object storage/S3 (backend de storage plugável).

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
| POST | `/api/v1/devices` | Registra device token (push) do médico |
| POST | `/api/v1/notifications/test-push` | Envia push de teste aos dispositivos do médico |
| POST | `/api/v1/patients` | Cadastra paciente (exige consentimento LGPD); retorna o **token do paciente uma única vez** |
| GET  | `/api/v1/patients` | **Painel**: pacientes ordenados por risco |
| GET  | `/api/v1/patients/{id}` | Detalhe do paciente |
| PATCH | `/api/v1/patients/{id}` | Edita paciente e ativa/desativa (`is_active`) |
| GET  | `/api/v1/patients/{id}/summary` | Resumo do paciente por IA (fallback determinístico) |
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
| POST | `/api/v1/patients/{id}/appointments` | Agenda consulta/retorno |
| GET  | `/api/v1/patients/{id}/appointments` | Consultas do paciente |
| GET  | `/api/v1/appointments/upcoming` | Próximas consultas do médico |
| PATCH | `/api/v1/appointments/{id}` | Reagenda/cancela/conclui uma consulta |
| POST | `/api/v1/patients/{id}/exams` | Registra um exame do paciente |
| GET  | `/api/v1/patients/{id}/exams` | Lista exames do paciente |
| PATCH | `/api/v1/exams/{id}` | Atualiza exame (ao ficar disponível, avisa o paciente) |
| POST | `/api/v1/patients/{id}/prescriptions` | Cria rascunho de receita |
| POST | `/api/v1/prescriptions/{id}/issue` | Emite a receita (provedor) e avisa o paciente |
| POST | `/api/v1/prescriptions/{id}/renew` | Renova (novo rascunho a partir de uma receita) |
| POST | `/api/v1/prescriptions/{id}/cancel` | Cancela a receita |
| POST | `/api/v1/patients/{id}/messages` | Envia mensagem ao paciente (chat) |
| GET  | `/api/v1/patients/{id}/messages` | Thread do chat com o paciente |
| POST | `/api/v1/patients/{id}/attachments` | Anexa arquivo ao contexto do paciente |
| GET  | `/api/v1/alerts` | Lista de alertas (filtro por status) |
| PATCH| `/api/v1/alerts/{id}` | Atualiza status do alerta |

Perfil **paciente** (token opaco — header `X-Patient-Token: <token>`):

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/v1/patient/devices` | Registra device token (push) do paciente |
| GET  | `/api/v1/patient/today` | Estado do dia (já fez o check-in?) para o app |
| GET  | `/api/v1/patient/medications/today` | Doses de medicação de hoje |
| POST | `/api/v1/patient/medications/intakes/{id}/respond` | Responde a uma dose (✓/⏰/❌) |
| GET  | `/api/v1/patient/appointments` | Próximas consultas do paciente |
| POST | `/api/v1/patient/appointments/{id}/confirm` | Confirma presença na consulta |
| GET  | `/api/v1/patient/exams` | Exames do paciente (solicitados/disponíveis) |
| GET  | `/api/v1/patient/prescriptions` | Receitas emitidas do paciente |
| GET  | `/api/v1/patient/prescriptions/{id}` | Detalhe de uma receita emitida |
| POST | `/api/v1/patient/messages` | Envia mensagem ao médico (chat) |
| GET  | `/api/v1/patient/messages` | Thread do chat com o médico |
| POST | `/api/v1/patient/ai-chat` | Conversa com a IA de apoio (responde na hora) |
| GET  | `/api/v1/patient/ai-chat` | Histórico do chat com a IA |
| POST | `/api/v1/patient/attachments` | Envia foto/arquivo/áudio (multipart) |
| GET  | `/api/v1/attachments/{id}` | Baixa um anexo (acesso restrito ao dono) |
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
✓/⏰/❌. A adesão é resumida em `/patients/{id}/medications/adherence`. Quando o paciente
falta **N doses seguidas** (`MEDICATION_MISSED_ALERT_STREAK`, default 3), é gerado um alerta
🟠 ao médico — uma vez por plano até ser resolvido.

**Lembrete de consulta**: `python -m app.scripts.scan_appointments` (cron) avisa o
paciente das consultas dentro da janela de antecedência (`APPOINTMENT_REMINDER_HOURS`,
default 24h). Idempotente.

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

**Push (app)**: paciente e médico registram device tokens (`POST /patient/devices` /
`POST /devices`); o envio resolve os tokens do destinatário e usa o provedor
(`PUSH_PROVIDER`): `log` (default, dev) ou `expo` (Expo Push — RN/Expo, entrega a
FCM/APNs). Para PWA, basta um provedor Web Push. `POST /notifications/test-push` valida
a config. O push já está **ligado** aos pontos de notificação: alerta ao médico,
lembrete de medicação, lembrete de consulta, exame disponível e nova receita — cada um
envia push (para quem tem device registrado) além dos canais log/email/whatsapp.

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

**Anexos (fotos/arquivos/áudio)** — upload em `multipart/form-data` por paciente
(`POST /patient/attachments`) ou médico (`POST /patients/{id}/attachments`). O tipo e
o tamanho são validados (`UPLOAD_ALLOWED_TYPES`, `UPLOAD_MAX_BYTES`); os bytes vão para
um backend de armazenamento **plugável** (`STORAGE_BACKEND=local` por padrão — grava em
`STORAGE_DIR`; produção troca por object storage/S3 implementando o mesmo protocolo) e
os metadados para a tabela `attachments`. O download (`GET /attachments/{id}`) é liberado
**só** para o paciente dono ou o médico responsável (LGPD — arquivos clínicos são
sensíveis; a resposta é 404 para quem não tem acesso, sem revelar a existência). A URL
retornada é referenciável nos `attachments` de uma mensagem ou no `audio_url` do check-in.

**Transcrição de áudio no check-in** — quando o `audio_url` do check-in aponta para um
anexo de áudio e a transcrição está habilitada (`TRANSCRIPTION_PROVIDER=openai`, endpoint
Whisper-compat), o áudio é transcrito e o texto entra na análise de risco **de forma
conservadora** (soma-se ao texto livre, não o substitui) e fica salvo em
`checkins.audio_transcript` para o médico ler. O padrão é `none` (não transcreve — o
áudio fica apenas salvo como anexo); qualquer falha de transcrição não bloqueia o check-in.

**Resumo do paciente** (`GET /patients/{id}/summary`): reúne o contexto (risco,
check-ins recentes, adesão, alertas, próxima consulta) e produz um resumo para o
painel. Com LLM configurado, gera texto natural; sem chave, cai num resumo
determinístico (sempre disponível). A IA não diagnostica.

**Chat paciente↔IA** (`POST /patient/ai-chat`): uma thread separada do chat com o
médico (mesma tabela `messages`, coluna `thread` = `care`/`ai`). Cada mensagem do
paciente passa **sempre** pela análise de risco do texto livre antes de responder —
sinal de risco ≥ 🟠 abre um alerta ao médico (com notificação/push), e em 🔴 a IA
devolve uma **mensagem de segurança** (CVV 188 / pronto-socorro) em vez de conversar.
Fora disso, responde de forma acolhedora e breve via LLM (se configurado) ou com um
retorno determinístico. A IA nunca diagnostica nem prescreve.

## Multi-tenant (fundação)

Toda conta é um **tenant** (`tenants`): uma **clínica** (quando há nome de clínica no
cadastro) ou um **profissional autônomo** (`solo`). Médicos e pacientes carregam
`tenant_id`, e o tenant tem um `config` (JSONB) para configuração por conta. Neste
primeiro passo a **visibilidade continua por médico** — o `tenant_id` fica assentado
como base para os próximos módulos (config por tenant, compartilhamento por clínica,
papéis). O tenant aparece em `/auth/me` (`tenant_id`, `tenant_name`).

## Receita (emissão delegada)

A emissão de receita com **valor legal** (assinatura ICP-Brasil, regras de controlado —
Portaria 344/98) é responsabilidade de uma **plataforma certificada**. O backend modela
a prescrição e delega a emissão a um provedor plugável (`app/services/prescription_provider.py`):
`internal` (default — registra sem valor legal, para MVP/testes) ou `certified` (integra a
plataforma certificada; requer `PRESCRIPTION_API_BASE_URL`/`PRESCRIPTION_API_KEY`). Ao emitir,
o paciente é avisado e a receita passa a aparecer no histórico dele.

## Compliance (não deixar para depois)

- **LGPD** — dado de saúde é categoria sensível: consentimento explícito é exigido no
  cadastro do paciente (`consent_given`), IDs são UUID (não enumeráveis), e o token do
  paciente é armazenado apenas como hash. **Direitos do titular**: exportação
  (`GET /patients/{id}/export`, portabilidade) e eliminação (`DELETE /patients/{id}`) —
  a exclusão remove paciente/check-ins/alertas/notificações/anexos por cascata e
  **preserva o log de auditoria** (referencia só IDs). Em produção, habilite
  **criptografia em repouso** no provedor de banco e mantenha **isolamento** em relação
  à Flowra AI (CRM).
- **Minimização em canais externos** — notificações enviadas a terceiros (WhatsApp/Meta,
  e-mail, webhook) e push (APNs/FCM/Expo, visíveis em tela de bloqueio) **não** incluem
  nome do paciente, nível de risco nem motivo clínico: apenas sinalizam que há um alerta
  e sua urgência, direcionando ao painel. O detalhe clínico fica **só no painel**, sob
  login. O acesso a anexos (fotos/áudio/arquivos) é restrito ao paciente dono ou ao médico
  responsável (404 para terceiros, sem revelar existência).
- **Auditoria sem conteúdo clínico** — `audit_logs` registra check-ins, cálculos de risco,
  alertas gerados e ações do médico (proteção jurídica), mas **não** grava texto livre nem
  sinais derivados do relato do paciente — só níveis/IDs. Assim o log retido após a
  eliminação não carrega dado sensível do titular.
- **Responsabilidade** — a API deixa explícito que a IA não diagnostica; o retorno do
  check-in ao paciente é neutro (não expõe o risco calculado ao próprio paciente).
- **Criptografia em repouso** — campos sensíveis (nome, contato, texto livre do check-in,
  transcrição de áudio e mensagens do chat) são cifrados no banco com **AES-256-GCM**
  (`EncryptedText`), com chave em `ENCRYPTION_KEY` (base64 de 32 bytes). Transparente para
  o ORM; sem chave, os campos ficam em claro (dev) e valores legados em claro continuam
  legíveis (adoção gradual). O hash do token do paciente **não** é cifrado (é usado em
  lookup). Complementa — não substitui — a criptografia de disco do provedor de banco.
- **Guardrails de produção** — no startup, com `ENVIRONMENT=production`, a aplicação
  **aborta** se `JWT_SECRET_KEY` estiver no valor padrão ou `DEBUG=true`, e **avisa** se a
  criptografia em repouso estiver desligada. `/docs`, `/redoc` e `/openapi.json` ficam
  **desabilitados** fora de desenvolvimento (reduz superfície de ataque).
- **IA externa sob DPA** — análise/resumo por LLM e transcrição de áudio enviam contexto
  clínico a terceiros; em produção só são habilitados com `AI_DPA_ACKNOWLEDGED=true`
  (contrato de tratamento de dados reconhecido). Sem isso, caem no comportamento
  determinístico/local — nunca vazam para o provedor externo.

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
