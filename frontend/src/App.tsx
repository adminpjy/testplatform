import { useEffect, useState } from "react";

import { idFromHash, routeFromHash, type AppRoute } from "./routes/navigation";
import { AbilityCenterPage } from "./pages/AbilityCenterPage";
import { CaseDetailPage } from "./pages/CaseDetailPage";
import { FailureSamplesPage } from "./pages/FailureSamplesPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { ReportsPage } from "./pages/ReportsPage";
import { SystemSettingsPage } from "./pages/SystemSettingsPage";
import { TestRunPage } from "./pages/TestRunPage";
import { TopNav } from "./components/TopNav";
import "./styles/app.css";

export default function App() {
  const [route, setRoute] = useState<AppRoute>(() => routeFromHash(window.location.hash));

  useEffect(() => {
    const handleHashChange = () => setRoute(routeFromHash(window.location.hash));
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  return (
    <div className="page-shell">
      <TopNav route={route} />
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
    case "project-detail":
      return <ProjectsPage initialProjectId={idFromHash(window.location.hash, "projects")} />;
    case "case-detail":
      return <CaseDetailPage caseId={idFromHash(window.location.hash, "cases")} />;
    case "ability-center":
      return <AbilityCenterPage />;
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
