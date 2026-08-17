# Deploy do Flowra Care na VPS

Sobe **db + api + painel (web)** atrás do **Caddy** (HTTPS automático), num domínio.
O app do paciente (Expo) é publicado à parte, pelas lojas via EAS (seção no fim).

> Este é um produto que trata **dado de saúde**. Leia a seção **Segurança & LGPD**
> antes de colocar pacientes reais.

## 1. Pré-requisitos

- Uma VPS Linux (Ubuntu 22.04+/Debian 12+), com acesso root/sudo.
- **DNS**: um registro **A** do seu domínio (ex.: `app.flowraai.com.br`) apontando
  para o **IP da VPS**. O Caddy precisa disso para emitir o certificado.
- **Portas 80 e 443 abertas** no firewall/security group.
- Docker Engine + plugin Compose:

```bash
curl -fsSL https://get.docker.com | sh
docker compose version   # confirmar que o plugin existe
```

## 2. Obter o código

```bash
sudo mkdir -p /opt/flowra && sudo chown "$USER" /opt/flowra
git clone <URL_DO_REPO> /opt/flowra
cd /opt/flowra
```

## 3. Configurar `.env` (segredos)

```bash
cp .env.example .env
```

Gere segredos fortes e preencha no `.env`:

```bash
echo "JWT_SECRET_KEY=$(openssl rand -base64 48 | tr -d '\n')"
echo "ENCRYPTION_KEY=$(openssl rand -base64 32 | tr -d '\n')"   # exatamente 32 bytes
echo "POSTGRES_PASSWORD=$(openssl rand -base64 24 | tr -d '\n')"
```

No `.env`, garanta pelo menos:

```
ENVIRONMENT=production
DEBUG=false
LOG_FORMAT=json
DOMAIN=app.flowraai.com.br
ACME_EMAIL=voce@flowraai.com.br
POSTGRES_PASSWORD=<gerado acima>
JWT_SECRET_KEY=<gerado acima>
ENCRYPTION_KEY=<gerado acima>
```

> ⚠️ **Guarde a `ENCRYPTION_KEY` num cofre.** Sem ela, os campos cifrados (nome,
> contato, texto livre, mensagens) ficam **ilegíveis** — inclusive nos backups.
> Com `ENVIRONMENT=production`, a aplicação **recusa subir** se `JWT_SECRET_KEY` for
> o valor padrão ou `DEBUG=true`.

> **Já existe um nginx/proxy na VPS (ex.: Hostinger com nginx nativo no 80/443)?**
> Não use o Caddy. Pule para a seção **“Atrás de um proxy existente”** no fim.

## 4. Subir

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

O primeiro boot aplica as migrações e popula o protocolo. Acompanhe:

```bash
docker compose -f docker-compose.prod.yml logs -f api caddy
```

## 5. Verificar

```bash
curl -fsS https://$DOMAIN/healthz && echo            # painel (nginx) ok

# API + banco: a health fica em /health/ready (raiz da API, NÃO sob /api) e a API
# não é publicada no host — verifique pelo próprio container:
docker compose -f docker-compose.prod.yml exec -T api \
  python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8000/health/ready').read().decode())"
# esperado: {"status": "ready", "database": "reachable"}
# (ou simplesmente `docker compose -f docker-compose.prod.yml ps` → api/db/web "healthy")
```

Abra `https://SEU_DOMINIO` no navegador → tela de login do painel.
Crie a primeira conta do médico em **Criar conta** (o backend expõe o cadastro).

## 6. Backups (obrigatório)

Agende o backup diário do banco:

```bash
crontab -e
# adicione:
0 3 * * * cd /opt/flowra && ./scripts/backup-db.sh >> /var/log/flowra-backup.log 2>&1
```

Os dumps ficam em `/opt/flowra/backups` (rotação de 14 por padrão). **Copie-os para
fora da VPS** (S3/Backblaze/etc.) e proteja a `ENCRYPTION_KEY` no mesmo nível.

Restaurar um backup:

```bash
gunzip -c backups/flowra-AAAAMMDD-HHMMSS.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T db psql -U flowra -d flowra_care
```

## 7. Scans agendados (lembretes + alertas automáticos)

Os **alertas de inatividade**, a **não-adesão à medicação** e os **lembretes de
consulta** precisam de algo que os dispare periodicamente.

**Já vem resolvido:** o compose sobe um serviço **`worker`** (o agendador) que roda
as três varreduras sozinho, a cada `SCHEDULER_INTERVAL_SECONDS` (padrão 10 min).
Não precisa configurar cron. Acompanhe com:

```bash
docker compose -f docker-compose.prod.yml logs -f worker   # (ou -f docker-compose.behind-proxy.yml)
```

> ⚠️ As varreduras **geram** os alertas/lembretes; eles só **chegam** ao médico/paciente
> se houver um **canal de notificação configurado** (seção 9). No padrão
> (`NOTIFICATION_CHANNELS=log`) tudo cai só em log.

**Alternativa (cron no host):** se preferir agendar fora do compose, remova o serviço
`worker` e use o cron (não rode os dois — evita trabalho duplicado):

```bash
crontab -e
*/15 * * * * cd /opt/flowra && ./scripts/run-scans.sh >> /var/log/flowra-scans.log 2>&1
17 * * * *   cd /opt/flowra && ./scripts/check-scans-heartbeat.sh >> /var/log/flowra-scans.log 2>&1
```

## 8. Atualizar (deploy de nova versão)

```bash
cd /opt/flowra && git pull
docker compose -f docker-compose.prod.yml up -d --build
```

As migrações rodam sozinhas no boot. Faça um backup antes de atualizar.

## 9. Integrações (para um produto de verdade)

No modo padrão, notificações caem em **log**. Configure no `.env` conforme o uso
(ver comentários no `.env.example`):

- **E-mail** (SMTP): `SMTP_HOST`, `SMTP_FROM`, credenciais → e adicione `email` em `NOTIFICATION_CHANNELS`.
- **Push** (app): `PUSH_PROVIDER=expo` + `EXPO_ACCESS_TOKEN`.
- **WhatsApp** (Meta Cloud API): `WHATSAPP_*` → e adicione `whatsapp` em `NOTIFICATION_CHANNELS`.
- **IA** (resumo/análise): `FREE_TEXT_ANALYZER=llm` + `LLM_*` e `AI_DPA_ACKNOWLEDGED=true`
  (só com DPA assinado — envia contexto clínico a terceiros).
- **Receita com valor legal**: `PRESCRIPTION_PROVIDER=certified` + credenciais da plataforma
  certificada (o provedor `internal` é só registro, sem valor legal).

## 10. App do paciente (Expo → lojas)

O app **não** vai na VPS. Publique pelas lojas:

```bash
cd mobile
# aponte a API de produção:
#   app.json -> expo.extra.apiBaseUrl = "https://SEU_DOMINIO"
npm i -g eas-cli && eas login && eas init
eas build --profile production --platform all
eas submit --profile production
```

Para o **deep link** abrir pelo link web do médico, configure universal/app links
(associação de domínio: `apple-app-site-association` e `assetlinks.json`) — ver `mobile/README.md`.

## Segurança & LGPD (antes de pacientes reais)

- **TLS** ✔ (Caddy). Mantenha só 80/443 abertos; feche a porta do banco (o compose já
  não publica db/api).
- **Segredos** fora do git; `ENCRYPTION_KEY` com backup seguro.
- **Backups** testados (faça uma restauração de teste).
- **Consentimento, política de privacidade, encarregado (DPO)** e **DPA** com cada
  processador (host, LLM, WhatsApp, e-mail).
- **Enquadramento clínico**: a IA é apoio à priorização, **não diagnostica**; valide os
  limiares de risco com um psiquiatra antes de confiar clinicamente.
- Atualizações de SO e imagens (`docker compose pull` para db/caddy) em dia.

## Atrás de um proxy existente (ex.: nginx nativo — Hostinger)

Quando a VPS já tem um nginx segurando 80/443 (com outros produtos), o Care sobe
**sem Caddy**, publicando o painel só em `127.0.0.1:8090`, e o seu nginx roteia
`care.SEUDOMINIO` para ele.

1. **DNS**: registro **A** `care` → IP da VPS.

2. **Suba o Care** (sem Caddy):
   ```bash
   cd /opt/flowra
   cp .env.example .env         # preencha os segredos (passo 3 acima)
   docker compose -f docker-compose.behind-proxy.yml up -d --build
   curl -fsS http://127.0.0.1:8090/healthz && echo   # painel respondendo local
   ```

3. **Bloco do nginx do host** (usa `deploy/nginx/care.conf` como modelo):
   ```bash
   # descubra onde ficam os sites do seu nginx:
   nginx -T 2>/dev/null | grep -E 'sites-enabled|conf.d' | head

   sed 's/care.SEUDOMINIO/care.flowraai.com.br/' deploy/nginx/care.conf \
     | sudo tee /etc/nginx/sites-available/care.conf
   sudo ln -sf /etc/nginx/sites-available/care.conf /etc/nginx/sites-enabled/care.conf
   sudo nginx -t && sudo systemctl reload nginx
   ```
   (Se o seu nginx usa `conf.d` em vez de `sites-*`, grave em `/etc/nginx/conf.d/care.conf`.)

4. **HTTPS** (certbot com o plugin do nginx):
   ```bash
   sudo apt install -y certbot python3-certbot-nginx
   sudo certbot --nginx -d care.flowraai.com.br
   ```
   O certbot adiciona o TLS ao bloco e recarrega o nginx.

5. **Verifique**: abra `https://care.flowraai.com.br` → login do painel.
   Backups e atualizações seguem iguais, trocando o `-f` para
   `docker-compose.behind-proxy.yml`.

> Isolamento: o Care tem **banco e volumes próprios** (`flowra_prod_*`), separados
> dos outros produtos — não compartilhe Postgres/volumes com BeautyFlow/moda (LGPD).
