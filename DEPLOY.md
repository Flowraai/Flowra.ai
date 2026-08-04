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
curl -fsS https://$DOMAIN/api/v1/health/ready && echo # API + banco ok
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

## 7. Atualizar (deploy de nova versão)

```bash
cd /opt/flowra && git pull
docker compose -f docker-compose.prod.yml up -d --build
```

As migrações rodam sozinhas no boot. Faça um backup antes de atualizar.

## 8. Integrações (para um produto de verdade)

No modo padrão, notificações caem em **log**. Configure no `.env` conforme o uso
(ver comentários no `.env.example`):

- **E-mail** (SMTP): `SMTP_HOST`, `SMTP_FROM`, credenciais → e adicione `email` em `NOTIFICATION_CHANNELS`.
- **Push** (app): `PUSH_PROVIDER=expo` + `EXPO_ACCESS_TOKEN`.
- **WhatsApp** (Meta Cloud API): `WHATSAPP_*` → e adicione `whatsapp` em `NOTIFICATION_CHANNELS`.
- **IA** (resumo/análise): `FREE_TEXT_ANALYZER=llm` + `LLM_*` e `AI_DPA_ACKNOWLEDGED=true`
  (só com DPA assinado — envia contexto clínico a terceiros).
- **Receita com valor legal**: `PRESCRIPTION_PROVIDER=certified` + credenciais da plataforma
  certificada (o provedor `internal` é só registro, sem valor legal).

## 9. App do paciente (Expo → lojas)

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
