import { useEffect, useState } from "react";

import { canAccessRoute, idFromHash, routeFromHash, type AppRoute } from "./routes/navigation";
import { getCurrentUser, logout } from "./api/platform";
import { AbilityCenterPage } from "./pages/AbilityCenterPage";
import { CaseDetailPage } from "./pages/CaseDetailPage";
import { EnterpriseCenterPage } from "./pages/EnterpriseCenterPage";
import { FailureSamplesPage } from "./pages/FailureSamplesPage";
import { ProjectWizardPage } from "./pages/ProjectWizardPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { ReportsPage } from "./pages/ReportsPage";
import { SystemSettingsPage } from "./pages/SystemSettingsPage";
import { TestRunPage } from "./pages/TestRunPage";
import { LoginPage } from "./pages/LoginPage";
import { TopNav } from "./components/TopNav";
import type { CurrentUser } from "./types/platform";
import "./styles/app.css";

export default function App() {
  const [route, setRoute] = useState<AppRoute>(() => routeFromHash(window.location.hash));
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    const handleHashChange = () => setRoute(routeFromHash(window.location.hash));
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  useEffect(() => {
    void getCurrentUser()
      .then((user) => {
        setCurrentUser(user);
        if (!canAccessRoute(route, user)) {
          window.location.hash = "#test-run";
          setRoute("test-run");
        }
      })
      .catch(() => setCurrentUser(null))
      .finally(() => setAuthChecked(true));
  }, []);

  useEffect(() => {
    if (currentUser && !canAccessRoute(route, currentUser)) {
      window.location.hash = "#test-run";
      setRoute("test-run");
    }
  }, [currentUser, route]);

  async function handleLogout() {
    await logout();
    setCurrentUser(null);
  }

  if (!authChecked) {
    return <div className="login-page"><div className="surface-panel loading-panel">正在检查登录状态...</div></div>;
  }

  if (!currentUser) {
    return <LoginPage onLogin={(user) => setCurrentUser(user)} />;
  }

  return (
    <div className="page-shell">
      <TopNav route={route} user={currentUser} onLogout={() => void handleLogout()} />
      <main className="page-content">
        {renderPage(route)}
      </main>
    </div>
  );
}

function renderPage(route: AppRoute) {
  switch (route) {
    case "projects":
      return <ProjectsPage />;
    case "project-wizard":
      return <ProjectWizardPage />;
    case "project-detail":
      return <ProjectsPage initialProjectId={idFromHash(window.location.hash, "projects")} />;
    case "case-detail":
      return <CaseDetailPage caseId={idFromHash(window.location.hash, "cases")} />;
    case "ability-center":
      return <AbilityCenterPage />;
    case "enterprise-center":
      return <EnterpriseCenterPage />;
    case "failure-samples":
      return <FailureSamplesPage />;
    case "reports":
      return <ReportsPage />;
    case "settings":
      return <SystemSettingsPage />;
    case "test-run":
    default:
      return <TestRunPage />;
  }
}
