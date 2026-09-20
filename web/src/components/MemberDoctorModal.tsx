import { useEffect, useState, type FormEvent } from "react";
import { auth as authApi, clinic } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { MemberDoctor, SpecialtyOption } from "../api/types";
import "./NewPatientModal.css";

export function MemberDoctorModal({
  membershipId,
  onClose,
  onSaved,
}: {
  membershipId: string;
  onClose: () => void;
  onSaved: (name: string) => void;
}) {
  const [doc, setDoc] = useState<MemberDoctor | null>(null);
  const [specialties, setSpecialties] = useState<SpecialtyOption[]>([]);
  const [name, setName] = useState("");
  const [specialty, setSpecialty] = useState("psiquiatria");
  const [clinicName, setClinicName] = useState("");
  const [council, setCouncil] = useState("");
  const [notifEmail, setNotifEmail] = useState("");
  const [notifPhone, setNotifPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    authApi.careSpecialties().then(setSpecialties).catch(() => setSpecialties([]));
  }, []);

  useEffect(() => {
    clinic
      .memberDoctor(membershipId)
      .then((d) => {
        setDoc(d);
        setName(d.name);
        setSpecialty(d.specialty);
        setClinicName(d.clinic ?? "");
        setCouncil(d.council_id ?? "");
        setNotifEmail(d.notification_email ?? "");
        setNotifPhone(d.notification_phone ?? "");
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Falha ao carregar o cadastro."));
  }, [membershipId]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy || !doc) return;
    setBusy(true);
    setError(null);
    try {
      const saved = await clinic.updateMemberDoctor(membershipId, {
        name: name.trim() || doc.name,
        specialty,
        clinic: clinicName.trim() || null,
        council_id: council.trim() || null,
        notification_email: notifEmail.trim() || null,
        notification_phone: notifPhone.trim() || null,
      });
      onSaved(saved.name);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível salvar.");
      setBusy(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <form className="modal-card np-form" onClick={(e) => e.stopPropagation()} onSubmit={onSubmit}>
        <h3>Cadastro do médico</h3>
        {doc ? <p className="muted">{doc.email}</p> : null}

        {!doc && !error ? (
          <p className="muted">Carregando…</p>
        ) : (
          <>
            <label>
              Nome
              <input value={name} onChange={(e) => setName(e.target.value)} required />
            </label>
            <label>
              Especialidade
              <select value={specialty} onChange={(e) => setSpecialty(e.target.value)}>
                {specialties.length === 0 && specialty ? (
                  <option value={specialty}>{specialty}</option>
                ) : null}
                {specialties.map((s) => (
                  <option key={s.key} value={s.key}>{s.label}</option>
                ))}
              </select>
            </label>
            <label>
              Registro (CRM / conselho)
              <input value={council} onChange={(e) => setCouncil(e.target.value)} placeholder="ex.: CRM 00000" />
            </label>
            <label>
              Clínica / consultório <span className="muted">(opcional)</span>
              <input value={clinicName} onChange={(e) => setClinicName(e.target.value)} />
            </label>
            <label>
              E-mail para alertas <span className="muted">(opcional)</span>
              <input type="email" value={notifEmail} onChange={(e) => setNotifEmail(e.target.value)} placeholder="usa o e-mail de login se vazio" />
            </label>
            <label>
              Telefone (WhatsApp) <span className="muted">(opcional)</span>
              <input value={notifPhone} onChange={(e) => setNotifPhone(e.target.value)} placeholder="+55DDDNÚMERO" />
            </label>
            <p className="muted np-note">
              Chave PIX e credenciais de receita ficam com o próprio médico.
            </p>
          </>
        )}

        {error ? <div className="np-error">{error}</div> : null}

        <div className="np-actions">
          <button type="button" className="btn ghost" onClick={onClose}>Fechar</button>
          <button type="submit" className="btn" disabled={busy || !doc}>
            {busy ? "Salvando…" : "Salvar cadastro"}
          </button>
        </div>
      </form>
    </div>
  );
}
