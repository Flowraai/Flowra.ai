import { useEffect, useState } from "react";
import { patients, notes as notesApi } from "../api/endpoints";
import { ApiError } from "../api/client";
import type { ClinicalNote, NoteKind } from "../api/types";
import { NoteModal } from "./NoteModal";
import { IconDoc } from "./icons";
import "./ClinicalCard.css";

const KIND: Record<NoteKind, { label: string; cls: string }> = {
  note: { label: "Anotação", cls: "b-accent" },
  diagnosis: { label: "Diagnóstico", cls: "b-ok" },
  other: { label: "Outro", cls: "b-muted" },
};

function when(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit",
  });
}

export function ClinicalNotesCard({ patientId }: { patientId: string }) {
  const [list, setList] = useState<ClinicalNote[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<ClinicalNote | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  function load() {
    setError(null);
    patients
      .notes(patientId)
      .then(setList)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Falha ao carregar as anotações."));
  }
  useEffect(load, [patientId]);

  async function remove(n: ClinicalNote) {
    if (!window.confirm("Excluir esta anotação?")) return;
    setBusy(n.id);
    try {
      await notesApi.remove(n.id);
      setList((prev) => (prev ? prev.filter((x) => x.id !== n.id) : prev));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="card">
      <div className="hd">
        <IconDoc width={16} height={16} color="var(--muted)" />
        <h4>Anotações e diagnósticos</h4>
        <button className="btn sm" style={{ marginLeft: "auto" }} onClick={() => setAdding(true)}>
          + Nova anotação
        </button>
      </div>
      <div className="bd">
        {error ? (
          <span className="muted">{error}</span>
        ) : !list ? (
          <div className="state"><div className="spinner" /></div>
        ) : list.length === 0 ? (
          <span className="muted" style={{ fontSize: 13 }}>
            Nenhuma anotação. Registre evolução, diagnóstico e outros pontos do prontuário.
          </span>
        ) : (
          <div className="note-list">
            {list.map((n) => {
              const k = KIND[n.kind];
              return (
                <div className="note-item" key={n.id}>
                  <div className="note-top">
                    <span className={`badge ${k.cls}`}>{k.label}</span>
                    {n.appointment_id ? <span className="badge b-muted">consulta</span> : null}
                    <span className="note-when">{when(n.created_at)}</span>
                    <div className="note-actions">
                      <button className="mini" disabled={busy === n.id} onClick={() => setEditing(n)}>
                        Editar
                      </button>
                      <button className="mini danger" disabled={busy === n.id} onClick={() => remove(n)}>
                        Excluir
                      </button>
                    </div>
                  </div>
                  <p className="note-body">{n.body}</p>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {adding ? (
        <NoteModal
          patientId={patientId}
          onClose={() => setAdding(false)}
          onSaved={() => {
            setAdding(false);
            load();
          }}
        />
      ) : null}
      {editing ? (
        <NoteModal
          patientId={patientId}
          note={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            load();
          }}
        />
      ) : null}
    </div>
  );
}
