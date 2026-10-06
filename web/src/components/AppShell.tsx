import { useEffect, useState, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { initials } from "../lib/format";
import {
  IconBell,
  IconCalendar,
  IconCard,
  IconChart,
  IconChat,
  IconClipboard,
  IconClose,
  IconFlower,
  IconGrid,
  IconLogout,
  IconMenu,
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
  const { session, doctor, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  // Fecha o menu ao trocar de rota (navegação no tablet/celular).
  useEffect(() => setMenuOpen(false), [location.pathname]);
  const clinic = session?.tenant_name ?? doctor?.clinic ?? "Consultório";
  const isReception = session?.role === "reception";
  const showFinance = !isReception || Boolean(session?.can_view_finance);
  const displayName = session?.name ?? doctor?.name ?? "—";
  const roleLabel =
    session?.role === "owner" ? "Dono" :
    session?.role === "reception" ? "Recepção" :
    doctor?.specialty ?? "Médico";

  return (
    <div className={`shell${menuOpen ? " menu-open" : ""}`}>
      <button
        className="nav-backdrop"
        aria-hidden={!menuOpen}
        tabIndex={-1}
        onClick={() => setMenuOpen(false)}
      />
      <aside className="sidebar">
        <div className="brand">
          <div className="mark">
            <IconFlower width={17} height={17} color="#fff" />
          </div>
          <div>
            <b>Flowra Care</b>
            <span>{clinic}</span>
          </div>
          <button
            className="nav-close"
            aria-label="Fechar menu"
            onClick={() => setMenuOpen(false)}
          >
            <IconClose width={18} height={18} />
          </button>
        </div>
        <nav>
          {session?.role === "owner" ? (
            <>
              <div className="nav-label">Gestão</div>
              <NavLink to="/gestor" className="nav-item">
                <IconChart width={17} height={17} /> Painel do gestor
              </NavLink>
            </>
          ) : null}
          <div className="nav-label">Atendimento</div>
          {!isReception ? (
            <>
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
            </>
          ) : null}
          <NavLink to="/agenda" className="nav-item">
            <IconCalendar width={17} height={17} /> Agenda
          </NavLink>
          {!isReception ? (
            <>
              <NavLink to="/mensagens" className="nav-item">
                <IconChat width={17} height={17} /> Mensagens
              </NavLink>
              <NavLink to="/pesquisa" className="nav-item">
                <IconClipboard width={17} height={17} /> Pesquisa
              </NavLink>
            </>
          ) : null}
          {showFinance ? (
            <NavLink to="/financeiro" className="nav-item">
              <IconChart width={17} height={17} /> Financeiro
            </NavLink>
          ) : null}
          {!isReception ? (
            <NavLink to="/configuracoes" className="nav-item">
              <IconSettings width={17} height={17} /> Configurações
            </NavLink>
          ) : null}

          {!isReception ? (
            <>
              <div className="nav-label">Conta</div>
              <NavLink to="/assinatura" className="nav-item">
                <IconCard width={17} height={17} /> Assinatura
              </NavLink>
              {doctor?.is_admin ? (
                <NavLink to="/admin/planos" className="nav-item">
                  <IconGrid width={17} height={17} /> Planos
                </NavLink>
              ) : null}
            </>
          ) : null}
        </nav>
        <div className="foot">
          <div className="avatar">{displayName !== "—" ? initials(displayName) : "—"}</div>
          <div className="who">
            <b>{displayName}</b>
            <span>{roleLabel}</span>
          </div>
          <button className="logout" title="Sair" aria-label="Sair" onClick={logout}>
            <IconLogout width={16} height={16} />
          </button>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <button
            className="nav-toggle"
            aria-label="Abrir menu"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen(true)}
          >
            <IconMenu width={20} height={20} />
          </button>
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
