import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { initials } from "../lib/format";
import {
  IconBell,
  IconChat,
  IconFlower,
  IconGrid,
  IconLogout,
  IconSettings,
  IconUsers,
} from "./icons";
import "./AppShell.css";

export function AppShell({
  title,
  subtitle,
  actions,
  children,
  alertCount,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  alertCount?: number;
}) {
  const { doctor, logout } = useAuth();
  const clinic = doctor?.tenant_name ?? doctor?.clinic ?? "Consultório";

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="mark">
            <IconFlower width={17} height={17} color="#fff" />
          </div>
          <div>
            <b>Flowra Care</b>
            <span>{clinic}</span>
          </div>
        </div>
        <nav>
          <div className="nav-label">Atendimento</div>
          <NavLink to="/" end className="nav-item">
            <IconGrid width={17} height={17} /> Painel
          </NavLink>
          <NavLink to="/alertas" className="nav-item">
            <IconBell width={17} height={17} /> Alertas
            {alertCount ? <span className="count">{alertCount}</span> : null}
          </NavLink>
          <NavLink to="/pacientes" className="nav-item">
            <IconUsers width={17} height={17} /> Pacientes
          </NavLink>
          <NavLink to="/mensagens" className="nav-item">
            <IconChat width={17} height={17} /> Mensagens
          </NavLink>
          <NavLink to="/configuracoes" className="nav-item">
            <IconSettings width={17} height={17} /> Configurações
          </NavLink>
        </nav>
        <div className="foot">
          <div className="avatar">{doctor ? initials(doctor.name) : "—"}</div>
          <div className="who">
            <b>{doctor?.name ?? "—"}</b>
            <span>{doctor?.specialty ?? "Médico"}</span>
          </div>
          <button className="logout" title="Sair" aria-label="Sair" onClick={logout}>
            <IconLogout width={16} height={16} />
          </button>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="titles">
            <h2>{title}</h2>
            {subtitle ? <div className="sub">{subtitle}</div> : null}
          </div>
          <div className="topbar-actions">{actions}</div>
        </header>
        <div className="content">{children}</div>
      </div>
    </div>
  );
}
