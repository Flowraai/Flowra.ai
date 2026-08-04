import { AppShell } from "../components/AppShell";
import { ThemeToggle } from "../components/ThemeToggle";

export function Placeholder({ title }: { title: string }) {
  return (
    <AppShell title={title} actions={<ThemeToggle />}>
      <div className="card">
        <div className="state">
          <b>{title}</b>
          <span className="muted">Esta seção chega numa próxima etapa do painel.</span>
        </div>
      </div>
    </AppShell>
  );
}
