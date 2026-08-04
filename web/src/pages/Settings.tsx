import { useState, type FormEvent } from "react";
import { AppShell } from "../components/AppShell";
import { ThemeToggle } from "../components/ThemeToggle";
import { useAuth } from "../auth/AuthContext";
import { auth } from "../api/endpoints";
import { ApiError } from "../api/client";
import "./Settings.css";

export function Settings() {
  const { doctor, refresh } = useAuth();
  const [name, setName] = useState(doctor?.name ?? "");
  const [specialty, setSpecialty] = useState(doctor?.specialty ?? "");
  const [clinic, setClinic] = useState(doctor?.clinic ?? "");
  const [councilId, setCouncilId] = useState(doctor?.council_id ?? "");
  const [notifEmail, setNotifEmail] = useState(doctor?.notification_email ?? "");
  const [notifPhone, setNotifPhone] = useState(doctor?.notification_phone ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      await auth.updateMe({
        name: name.trim(),
        specialty: specialty.trim(),
        clinic: clinic.trim() || null,
        council_id: councilId.trim() || null,
        notification_email: notifEmail.trim() || null,
        notification_phone: notifPhone.trim() || null,
      });
      await refresh();
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível salvar. Tente novamente.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell title="Configurações" subtitle="Seu perfil e contatos de notificação" actions={<ThemeToggle />}>
      <div className="card settings-card">
        <form onSubmit={onSubmit}>
          <div className="set-section">Perfil</div>
          <label>
            Nome
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label>
            E-mail de login <span className="muted">(não editável aqui)</span>
            <input value={doctor?.email ?? ""} disabled />
          </label>
          <div className="set-row">
            <label>
              Especialidade
              <input value={specialty} onChange={(e) => setSpecialty(e.target.value)} placeholder="Psiquiatria" />
            </label>
            <label>
              Registro (CRM)
              <input value={councilId} onChange={(e) => setCouncilId(e.target.value)} placeholder="CRM 00000" />
            </label>
          </div>
          <label>
            Clínica / consultório
            <input value={clinic} onChange={(e) => setClinic(e.target.value)} placeholder="opcional" />
          </label>

          <div className="set-section">Notificações de alerta</div>
          <p className="muted set-hint">
            Onde receber avisos de alertas dos pacientes. Deixe em branco para usar o e-mail de login.
          </p>
          <div className="set-row">
            <label>
              E-mail para alertas
              <input
                type="email"
                value={notifEmail}
                onChange={(e) => setNotifEmail(e.target.value)}
                placeholder={doctor?.email ?? ""}
              />
            </label>
            <label>
              Telefone (WhatsApp)
              <input value={notifPhone} onChange={(e) => setNotifPhone(e.target.value)} placeholder="+55…" />
            </label>
          </div>

          {error ? <div className="set-error">{error}</div> : null}
          {saved ? <div className="set-saved">Alterações salvas ✓</div> : null}

          <div className="set-actions">
            <button className="btn" type="submit" disabled={busy}>
              {busy ? "Salvando…" : "Salvar alterações"}
            </button>
          </div>
        </form>
      </div>
    </AppShell>
  );
}
