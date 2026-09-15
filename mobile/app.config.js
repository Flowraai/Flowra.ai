// Config dinâmica do Expo: parte do app.json e injeta a URL da API por ambiente.
// Em dev, mantém o apiBaseUrl do app.json (localhost). Nos builds EAS, o perfil
// define EXPO_PUBLIC_API_BASE_URL (ver eas.json) e ele passa a valer aqui.
// Mantém o app.json como base para que `eas init` continue gravando o projectId
// em extra.eas (preservado pelo spread abaixo).
const base = require("./app.json");

module.exports = () => ({
  ...base,
  expo: {
    ...base.expo,
    extra: {
      ...base.expo.extra,
      apiBaseUrl: process.env.EXPO_PUBLIC_API_BASE_URL ?? base.expo.extra.apiBaseUrl,
    },
  },
});
