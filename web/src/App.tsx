import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { PatientDetail } from "./pages/PatientDetail";
import { Alerts } from "./pages/Alerts";
import { Messages } from "./pages/Messages";
import type { ReactNode } from "react";

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

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
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
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
