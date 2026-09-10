# Flowra Care — App do paciente (Android)

App nativo (Expo/React Native) do paciente. Marco 1: **login por CPF+senha**,
tela **Hoje** e **sincronização com o Health Connect** (lê Mi Band/Xiaomi,
Samsung Health e Google Fit e envia o resumo diário — sono, FC de repouso, HRV,
passos — para o Flowra Care).

> Health Connect é um módulo nativo: **não roda no Expo Go**. Use um *dev build*
> (`expo run:android`) ou EAS Build.

## Pré-requisitos (na sua máquina)
- Node 18+ e Java 17 + Android Studio (SDK/emulador) OU um celular Android com
  **depuração USB** ligada.
- O app **Health Connect** instalado no aparelho (Play Store) e a pulseira/relógio
  já sincronizando com ele (via Mi Fitness/Zepp, Samsung Health ou Google Fit).

## Rodar em desenvolvimento
```bash
cd mobile
npm install
# aponte para o servidor (produção já é o default; para testar local, edite
# app.json > expo.extra.apiBaseUrl, ex.: http://192.168.0.10:8000)
npx expo run:android        # compila o dev build e instala no aparelho/emulador
```
Depois de instalado, `npm start` reabre o Metro para desenvolvimento.

## O que testar
1. Entre com o **CPF + senha** de um paciente já ativado (o primeiro acesso/criação
   de senha é pelo link de convite no navegador).
2. Em **Meu dispositivo → Conectar dispositivo**, aceite as permissões do Health
   Connect. O app lê os últimos 14 dias e envia ao servidor.
3. Confira no painel do médico (card **Dispositivo**) que os dados chegaram.

## Publicar (faixa de teste no Google Play)
- Conta de desenvolvedor Google Play (US$ 25, pagamento único).
- `eas build -p android --profile preview` (ou build local) gera o APK/AAB.
- Suba na **Faixa de teste fechada** e convide os pacientes por e-mail.
- Apps que leem dados de saúde exigem a **declaração de uso do Health Connect**
  no console do Google Play (finalidade + política de privacidade).

## Próximos marcos
- **M2:** tela de check-in completa (protocolo, emoji, retroativo).
- **M3:** remédios, calendário, chat e apoio (IA).
