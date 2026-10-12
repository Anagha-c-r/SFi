import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import { Layout } from "./components/Layout";
import { Spinner } from "./components/ui";
import { Account } from "./pages/Account";
import { AdminInstitutions } from "./pages/AdminInstitutions";
import { Audit } from "./pages/Audit";
import { DashboardPage } from "./pages/Dashboard";
import { DatasetPage } from "./pages/DatasetPage";
import { Datasets } from "./pages/Datasets";
import { Login } from "./pages/Login";
import { SettingsPage } from "./pages/Settings";
import { SubmissionPage } from "./pages/SubmissionPage";
import { Submissions } from "./pages/Submissions";
import { Users } from "./pages/Users";
import "./styles.css";

function Routed() {
  const { user, loading } = useAuth();
  if (loading) return <Spinner label="Starting" />;
  if (!user) return <Login />;
  const home = user.institution ? <DashboardPage /> : <Navigate to="/admin/institutions" replace />;
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={home} />
        <Route path="datasets" element={<Datasets />} />
        <Route path="datasets/:code" element={<DatasetPage />} />
        <Route path="submissions" element={<Submissions />} />
        <Route path="approvals" element={<Submissions approvals />} />
        <Route path="submissions/:id" element={<SubmissionPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="users" element={<Users />} />
        <Route path="audit" element={<Audit />} />
        <Route path="account" element={<Account />} />
        <Route path="admin/institutions" element={<AdminInstitutions />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <Routed />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
