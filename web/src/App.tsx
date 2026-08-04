import { BrowserRouter, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { useEffect, type ReactNode } from "react";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { PatientDetail } from "./pages/PatientDetail";
import { Alerts } from "./pages/Alerts";
import { Messages } from "./pages/Messages";
import { Settings } from "./pages/Settings";
import { Subscribe } from "./pages/Subscribe";
import { AdminPlans } from "./pages/AdminPlans";
import { ResetPassword } from "./pages/ResetPassword";

function FullScreenLoader() {
  return (
    <div className="state" style={{ minHeight: "100vh" }}>
      <div className="spinner" />
    </div>
  );
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { doctor, loading } = useAuth();
  if (loading) return <FullScreenLoader />;
  if (!doctor) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function RedirectIfAuthed({ children }: { children: ReactNode }) {
  const { doctor, loading } = useAuth();
  if (loading) return <FullScreenLoader />;
  if (doctor) return <Navigate to="/" replace />;
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
          <Route
            path="/"
            element={
              <RequireAuth>
                <Dashboard />
              </RequireAuth>
            }
          />
          <Route
            path="/pacientes"
            element={
              <RequireAuth>
                <Dashboard />
              </RequireAuth>
            }
          />
          <Route
            path="/pacientes/:id"
            element={
              <RequireAuth>
                <PatientDetail />
              </RequireAuth>
            }
          />
          <Route
            path="/alertas"
            element={
              <RequireAuth>
                <Alerts />
              </RequireAuth>
            }
          />
          <Route
            path="/mensagens"
            element={
              <RequireAuth>
                <Messages />
              </RequireAuth>
            }
          />
          <Route
            path="/configuracoes"
            element={
              <RequireAuth>
                <Settings />
              </RequireAuth>
            }
          />
          <Route
            path="/assinatura"
            element={
              <RequireAuth>
                <Subscribe />
              </RequireAuth>
            }
          />
          <Route
            path="/admin/planos"
            element={
              <RequireAuth>
                <AdminPlans />
              </RequireAuth>
            }
          />
          <Route path="/redefinir-senha" element={<ResetPassword />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
