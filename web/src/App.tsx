import { BrowserRouter, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { useEffect, type ReactNode } from "react";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { Login } from "./pages/Login";
import { AcceptInvite } from "./pages/AcceptInvite";
import { Dashboard } from "./pages/Dashboard";
import { PatientDetail } from "./pages/PatientDetail";
import { PatientReport } from "./pages/PatientReport";
import { CertificatePrint } from "./pages/CertificatePrint";
import { Alerts } from "./pages/Alerts";
import { Agenda } from "./pages/Agenda";
import { Messages } from "./pages/Messages";
import { FinancialPanel } from "./pages/FinancialPanel";
import { Settings } from "./pages/Settings";
import { SurveyPage } from "./pages/Survey";
import { Subscribe } from "./pages/Subscribe";
import { AdminPlans } from "./pages/AdminPlans";
import { ResetPassword } from "./pages/ResetPassword";
import { PatientApp } from "./patient/PatientApp";

function FullScreenLoader() {
  return (
    <div className="state" style={{ minHeight: "100vh" }}>
      <div className="spinner" />
    </div>
  );
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { session, loading } = useAuth();
  if (loading) return <FullScreenLoader />;
  if (!session) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

/** Rotas clínicas: exige acesso a dado clínico. Recepção cai na Agenda. */
function RequireClinical({ children }: { children: ReactNode }) {
  const { session, loading } = useAuth();
  if (loading) return <FullScreenLoader />;
  if (!session) return <Navigate to="/login" replace />;
  if (session.role === "reception") return <Navigate to="/agenda" replace />;
  return <>{children}</>;
}

function RedirectIfAuthed({ children }: { children: ReactNode }) {
  const { session, loading } = useAuth();
  if (loading) return <FullScreenLoader />;
  if (session) return <Navigate to={session.role === "reception" ? "/agenda" : "/"} replace />;
  return <>{children}</>;
}

/** Ao receber 402 (assinatura necessária) de qualquer chamada, leva à tela de planos. */
function PaymentRequiredWatcher() {
  const navigate = useNavigate();
  useEffect(() => {
    const onNeed = () => navigate("/assinatura");
    window.addEventListener("flowra:payment-required", onNeed);
    return () => window.removeEventListener("flowra:payment-required", onNeed);
  }, [navigate]);
  return null;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <PaymentRequiredWatcher />
        <Routes>
          <Route
            path="/login"
            element={
              <RedirectIfAuthed>
                <Login />
              </RedirectIfAuthed>
            }
          />
          <Route path="/convite" element={<AcceptInvite />} />
          <Route
            path="/"
            element={
              <RequireClinical>
                <Dashboard />
              </RequireClinical>
            }
          />
          <Route
            path="/pacientes"
            element={
              <RequireClinical>
                <Dashboard />
              </RequireClinical>
            }
          />
          <Route
            path="/pacientes/:id"
            element={
              <RequireClinical>
                <PatientDetail />
              </RequireClinical>
            }
          />
          <Route
            path="/pacientes/:id/relatorio"
            element={
              <RequireClinical>
                <PatientReport />
              </RequireClinical>
            }
          />
          <Route
            path="/pacientes/:id/atestado/:certId"
            element={
              <RequireClinical>
                <CertificatePrint />
              </RequireClinical>
            }
          />
          <Route
            path="/agenda"
            element={
              <RequireAuth>
                <Agenda />
              </RequireAuth>
            }
          />
          <Route
            path="/alertas"
            element={
              <RequireClinical>
                <Alerts />
              </RequireClinical>
            }
          />
          <Route
            path="/mensagens"
            element={
              <RequireClinical>
                <Messages />
              </RequireClinical>
            }
          />
          <Route
            path="/pesquisa"
            element={
              <RequireClinical>
                <SurveyPage />
              </RequireClinical>
            }
          />
          <Route
            path="/financeiro"
            element={
              <RequireAuth>
                <FinancialPanel />
              </RequireAuth>
            }
          />
          <Route
            path="/configuracoes"
            element={
              <RequireClinical>
                <Settings />
              </RequireClinical>
            }
          />
          <Route
            path="/assinatura"
            element={
              <RequireClinical>
                <Subscribe />
              </RequireClinical>
            }
          />
          <Route
            path="/admin/planos"
            element={
              <RequireClinical>
                <AdminPlans />
              </RequireClinical>
            }
          />
          <Route path="/redefinir-senha" element={<ResetPassword />} />
          {/* Área do paciente (público, autenticado por token do link de convite) */}
          <Route path="/checkin" element={<PatientApp />} />
          <Route path="/paciente" element={<PatientApp />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
