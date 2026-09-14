import { useNavigate } from "react-router-dom";
import type { DoctorProfile } from "../api/types";
import "./OnboardingCard.css";

type Step = { key: string; title: string; desc: string; done: boolean; cta: string; onClick: () => void };

export function OnboardingCard({
  doctor,
  patientCount,
  onAddPatient,
  onDismiss,
}: {
  doctor: DoctorProfile;
  patientCount: number;
  onAddPatient: () => void;
  onDismiss: () => void;
}) {
  const navigate = useNavigate();
  const first = doctor.name.split(" ")[0];
  const label = doctor.care?.label ?? doctor.specialty;

  const steps: Step[] = [
    {
      key: "account",
      title: "Conta criada",
      desc: `Seu acompanhamento de ${label} está configurado.`,
      done: true,
      cta: "Feito",
      onClick: () => {},
    },
    {
      key: "patient",
      title: "Cadastre seu primeiro paciente",
      desc: "Ele recebe o acesso ao app e começa os check-ins diários.",
      done: patientCount > 0,
      cta: "Cadastrar",
      onClick: onAddPatient,
    },
    {
      key: "checkin",
      title: "Confira o check-in",
      desc: `As perguntas do dia a dia já vêm prontas para ${label} — ajuste se quiser.`,
      done: false,
      cta: "Revisar",
      onClick: () => navigate("/pesquisa"),
    },
    {
      key: "settings",
      title: "Notificações e WhatsApp",
      desc: "Conecte seu WhatsApp e defina onde receber os alertas.",
      done: false,
      cta: "Configurar",
      onClick: () => navigate("/configuracoes"),
    },
  ];

  const doneCount = steps.filter((s) => s.done).length;

  return (
    <section className="onb">
      <button className="onb-close" onClick={onDismiss} aria-label="Ocultar boas-vindas">✕</button>
      <div className="onb-head">
        <span className="onb-mark" aria-hidden>🌿</span>
        <div>
          <h3>Bem-vindo(a), {first}!</h3>
          <p>Sua conta de <b>{label}</b> está pronta. Vamos preparar seu acompanhamento em poucos passos.</p>
        </div>
        <span className="onb-progress" title="Passos concluídos">{doneCount}/{steps.length}</span>
      </div>

      <ol className="onb-steps">
        {steps.map((s) => (
          <li key={s.key} className={`onb-step ${s.done ? "done" : ""}`}>
            <span className="onb-check" aria-hidden>{s.done ? "✓" : ""}</span>
            <div className="onb-step-body">
              <b>{s.title}</b>
              <span>{s.desc}</span>
            </div>
            {!s.done ? (
              <button className="onb-cta" onClick={s.onClick}>{s.cta}</button>
            ) : null}
          </li>
        ))}
      </ol>

      <button className="onb-dismiss" onClick={onDismiss}>Já conheço — ocultar</button>
    </section>
  );
}
