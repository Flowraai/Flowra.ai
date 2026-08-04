# Flowra Care — App do paciente (Expo)

App do paciente em **Expo / React Native + TypeScript**. Autenticação por **código de
acesso** (token opaco enviado pelo médico), enviado em `X-Patient-Token`.

## Rodar em desenvolvimento

```bash
cd mobile
npm install
npm start            # abre o Expo; leia o QR no app Expo Go, ou tecle i / a
```

Aponte a base da API em `app.json` → `expo.extra.apiBaseUrl`. Para testar num
**celular físico**, use o IP da sua máquina na rede (não `localhost`), ex.:
`http://192.168.0.10:8000`. Suba o backend antes.

## Verificar

```bash
npm run typecheck    # tsc --noEmit
```

O build nativo (iOS/Android) é feito via **EAS Build** (`eas build`) — precisa de conta
Expo e não roda em CI comum.

## Build nativo (EAS)

Os perfis estão em `eas.json` (`development` / `preview` / `production`).

```bash
npm i -g eas-cli
eas login
eas init                 # vincula ao projeto Expo e grava o projectId (usado no push)
eas build --profile preview --platform android   # ou ios
eas build --profile production --platform all
eas submit --profile production                   # publica nas lojas
```

Aponte a API de produção em `app.json` → `expo.extra.apiBaseUrl` (ou via variável no
perfil do `eas.json`). O `projectId` do push é lido de `expo.extra.eas.projectId`
(preenchido pelo `eas init`).

## Fluxo / telas

- **Acesso** — o paciente cola o código de acesso (do link do médico); validamos e
  guardamos com segurança (SecureStore / Keychain-Keystore).
- **Hoje** — saudação e estado do dia; botão para o **check-in diário** (< 1 min),
  renderizado dinamicamente a partir do protocolo do backend (escala, inteiro, escolha,
  sim/não, texto livre).
- **Medicação** — doses do dia com resposta ✓ Tomei / ⏰ Depois / ✕ Não tomei.
- **Conversa** — chat com o médico.
- **Push** — registra o Expo push token no backend (`POST /patient/devices`); só
  funciona em dispositivo físico.

Tema claro/escuro segue o sistema. Retorno do check-in é **neutro** (não expõe o risco
ao paciente). Em emergência, o app orienta procurar ajuda / CVV 188.
