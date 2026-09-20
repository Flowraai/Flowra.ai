import { useEffect, useState, type FormEvent } from "react";
import { AppShell } from "../components/AppShell";
import { ThemeToggle } from "../components/ThemeToggle";
import { PrescriptionIntegrationCard } from "../components/PrescriptionIntegrationCard";
import { WhatsAppConnectCard } from "../components/WhatsAppConnectCard";
import { MessagePrefsCard } from "../components/MessagePrefsCard";
import { QuickRepliesCard } from "../components/QuickRepliesCard";
import { HealthPlansCard } from "../components/HealthPlansCard";
import { TeamCard } from "../components/TeamCard";
import { ClinicBillingCard } from "../components/ClinicBillingCard";
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
  const [pixKey, setPixKey] = useState(doctor?.pix_key ?? "");
  const [pixCity, setPixCity] = useState(doctor?.pix_city ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [specialties, setSpecialties] = useState<{ key: string; label: string }[]>([]);

  useEffect(() => {
    auth.careSpecialties().then(setSpecialties).catch(() => setSpecialties([]));
  }, []);

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
        pix_key: pixKey.trim() || null,
        pix_city: pixCity.trim() || null,
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
              {specialties.length > 0 ? (
                <select value={specialty} onChange={(e) => setSpecialty(e.target.value)}>
                  {/* mantém o valor atual mesmo se não for um pacote conhecido */}
                  {!specialties.some((s) => s.key === specialty) && specialty ? (
                    <option value={specialty}>{specialty}</option>
                  ) : null}
                  {specialties.map((s) => (
                    <option key={s.key} value={s.key}>{s.label}</option>
                  ))}
                </select>
              ) : (
                <input value={specialty} onChange={(e) => setSpecialty(e.target.value)} placeholder="Psiquiatria" />
              )}
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

          <div className="set-section">Cobrança PIX</div>
          <p className="muted set-hint">
            Usados para gerar o PIX copia-e-cola das cobranças particulares. A chave fica
            cifrada. A cidade é exigida pelo padrão do BR Code.
          </p>
          <div className="set-row">
            <label>
              Chave PIX
              <input
                value={pixKey}
                onChange={(e) => setPixKey(e.target.value)}
                placeholder="CPF, telefone, e-mail ou chave aleatória"
              />
            </label>
            <label>
              Cidade
              <input value={pixCity} onChange={(e) => setPixCity(e.target.value)} placeholder="São Paulo" />
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

      {doctor?.clinic_role === "owner" ? <TeamCard /> : null}
      {doctor?.clinic_role === "owner" ? <ClinicBillingCard /> : null}
      <HealthPlansCard />
      <WhatsAppConnectCard />
      <MessagePrefsCard />
      <QuickRepliesCard />
      <PrescriptionIntegrationCard />
    </AppShell>
  );
}
