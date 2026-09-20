import { useEffect, useState, type FormEvent } from "react";
import { clinic } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { ClinicInvitation, ClinicMember, ClinicRoleName } from "../api/types";
import { MemberDoctorModal } from "./MemberDoctorModal";
import "./TeamCard.css";

const ROLE_LABEL: Record<ClinicRoleName, string> = {
  owner: "Dono",
  doctor: "Médico",
  reception: "Recepção",
};

export function TeamCard() {
  const [members, setMembers] = useState<ClinicMember[] | null>(null);
  const [invites, setInvites] = useState<ClinicInvitation[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<ClinicRoleName>("reception");
  const [finance, setFinance] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [editingDoctor, setEditingDoctor] = useState<string | null>(null);

  function load() {
    clinic.members().then(setMembers).catch(() => setMembers([]));
    clinic.invitations().then(setInvites).catch(() => setInvites([]));
  }
  useEffect(load, []);

  async function invite(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await clinic.invite({ email: email.trim(), role, can_view_finance: finance });
      setEmail("");
      setFinance(false);
      setNotice("Convite enviado por e-mail.");
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível convidar.");
    } finally {
      setBusy(false);
    }
  }

  async function patchMember(m: ClinicMember, patch: Parameters<typeof clinic.updateMember>[1]) {
    try {
      await clinic.updateMember(m.id, patch);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível salvar.");
    }
  }

  async function revoke(id: string) {
    try {
      await clinic.revokeInvite(id);
      load();
    } catch {
      /* ignora */
    }
  }

  return (
    <div className="card settings-card">
      <div className="set-section">Equipe da clínica</div>
      <p className="muted set-hint">
        Convide médicos e recepção. Cada pessoa entra com o próprio acesso; você controla o papel e
        quem enxerga o financeiro.
      </p>

      <form className="team-invite" onSubmit={invite}>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="e-mail da pessoa"
          required
        />
        <select value={role} onChange={(e) => setRole(e.target.value as ClinicRoleName)}>
          <option value="reception">Recepção</option>
          <option value="doctor">Médico</option>
        </select>
        {role === "reception" ? (
          <label className="team-fin">
            <input type="checkbox" checked={finance} onChange={(e) => setFinance(e.target.checked)} />
            vê financeiro
          </label>
        ) : null}
        <button className="btn" type="submit" disabled={busy}>
          {busy ? "Enviando…" : "Convidar"}
        </button>
      </form>

      {error ? <div className="set-error">{error}</div> : null}
      {notice ? <div className="set-saved">{notice}</div> : null}

      {invites.length > 0 ? (
        <>
          <div className="team-sub">Convites pendentes</div>
          <ul className="team-list">
            {invites.map((i) => (
              <li key={i.id} className="team-item">
                <span>
                  <b>{i.email}</b> <span className="muted">· {ROLE_LABEL[i.role]}</span>
                </span>
                <button className="mini" onClick={() => revoke(i.id)}>Cancelar</button>
              </li>
            ))}
          </ul>
        </>
      ) : null}

      <div className="team-sub">Integrantes</div>
      {members == null ? (
        <p className="muted">Carregando…</p>
      ) : (
        <ul className="team-list">
          {members.map((m) => (
            <li key={m.id} className="team-item">
              <span>
                <b>{m.name ?? m.email}</b>{" "}
                <span className="muted">· {ROLE_LABEL[m.role]}{m.is_self ? " (você)" : ""}</span>
                {!m.is_active ? <span className="team-off"> inativo</span> : null}
              </span>
              {m.role !== "owner" && !m.is_self ? (
                <span className="team-actions">
                  {m.role === "reception" ? (
                    <label className="team-fin">
                      <input
                        type="checkbox"
                        checked={m.can_view_finance}
                        onChange={(e) => patchMember(m, { can_view_finance: e.target.checked })}
                      />
                      financeiro
                    </label>
                  ) : null}
                  {m.role === "doctor" ? (
                    <label className="team-share" title="Percentual das consultas que fica com a clínica">
                      Clínica
                      <input
                        type="number"
                        min={0}
                        max={100}
                        defaultValue={m.clinic_share_percent}
                        onBlur={(e) => {
                          const v = Math.max(0, Math.min(100, Number(e.target.value) || 0));
                          if (v !== m.clinic_share_percent) patchMember(m, { clinic_share_percent: v });
                        }}
                      />
                      %
                    </label>
                  ) : null}
                  {m.role === "doctor" ? (
                    <button className="mini" onClick={() => setEditingDoctor(m.id)}>
                      Cadastro
                    </button>
                  ) : null}
                  <button className="mini" onClick={() => patchMember(m, { is_active: !m.is_active })}>
                    {m.is_active ? "Desativar" : "Reativar"}
                  </button>
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      {editingDoctor ? (
        <MemberDoctorModal
          membershipId={editingDoctor}
          onClose={() => setEditingDoctor(null)}
          onSaved={(name) => {
            setEditingDoctor(null);
            setNotice(`Cadastro de ${name} atualizado.`);
            load();
          }}
        />
      ) : null}
    </div>
  );
}
