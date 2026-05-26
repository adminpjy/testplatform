import { useEffect, useMemo, useState } from "react";

import { navigationItems, routeFromHash, type AppRoute } from "./routes/navigation";
import { AbilityCenterPage } from "./pages/AbilityCenterPage";
import { FailureSamplesPage } from "./pages/FailureSamplesPage";
import { ReportsPage } from "./pages/ReportsPage";
import { SystemSettingsPage } from "./pages/SystemSettingsPage";
import { TestRunPage } from "./pages/TestRunPage";
import { TestSystemsPage } from "./pages/TestSystemsPage";
import { TopNav } from "./components/TopNav";
import "./styles/app.css";

export default function App() {
  const [route, setRoute] = useState<AppRoute>(() => routeFromHash(window.location.hash));

  useEffect(() => {
    const handleHashChange = () => setRoute(routeFromHash(window.location.hash));
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  const activeItem = useMemo(() => navigationItems.find((item) => item.id === route), [route]);

  return (
    <div className="page-shell">
      <TopNav route={route} />
      <main className="page-content">
        <header className="app-topbar">
          <div>
            <h1>{activeItem?.label || "测试运行"}</h1>
            <p>{activeItem?.description || ""}</p>
          </div>
        </header>
        {renderPage(route)}
      </main>
    </div>
  );
}

function renderPage(route: AppRoute) {
  switch (route) {
    case "ability-center":
      return <AbilityCenterPage />;
    case "failure-samples":
      return <FailureSamplesPage />;
    case "reports":
      return <ReportsPage />;
    case "systems":
      return <TestSystemsPage />;
    case "settings":
      return <SystemSettingsPage />;
    case "test-run":
    default:
      return <TestRunPage />;
  }
}
