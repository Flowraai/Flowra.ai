import { useState } from "react";
import { setPatientToken } from "./api";

export function Access({ expired }: { expired?: boolean }) {
  const [code, setCode] = useState("");

  function enter() {
    const t = code.trim();
    if (!t) return;
    setPatientToken(t);
    window.location.reload();
  }

  return (
    <div className="pt-shell">
      <div className="pt-top">
        <div className="pt-mark">✿</div>
        <div>
          <b>Flowra Care</b>
          <span>Acompanhamento do paciente</span>
        </div>
      </div>
      <div className="pt-center" style={{ flexDirection: "column", gap: 16 }}>
        <div className="pt-mark" style={{ width: 54, height: 54, fontSize: 26, borderRadius: 16 }}>
          ✿
        </div>
        <div>
          <h1 className="pt-h1">{expired ? "Acesso expirado" : "Bem-vindo(a)"}</h1>
          <p className="pt-sub" style={{ marginBottom: 0 }}>
            {expired
              ? "Seu link de acesso não é mais válido. Peça um novo link ao seu médico."
              : "Para entrar, abra o link de convite que seu médico enviou por mensagem."}
          </p>
        </div>
        <div className="pt-card" style={{ width: "100%", textAlign: "left" }}>
          <h3>Tem um código?</h3>
          <p className="pt-muted" style={{ marginTop: 4, marginBottom: 10 }}>
            Se você recebeu um código de acesso, cole aqui.
          </p>
          <input
            className="pt-input"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="Código de acesso"
          />
          <button className="pt-btn" style={{ marginTop: 10 }} onClick={enter} disabled={!code.trim()}>
            Entrar
          </button>
        </div>
      </div>
    </div>
  );
}
