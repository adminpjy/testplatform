import { useEffect, useMemo, useState } from "react";

import { navigationItems, routeFromHash, type AppRoute } from "./routes/navigation";
import { AbilityCenterPage } from "./pages/AbilityCenterPage";
import { FailureSamplesPage } from "./pages/FailureSamplesPage";
import { MockMisDemoPage } from "./pages/MockMisDemoPage";
import { ReportsPage } from "./pages/ReportsPage";
import { SystemSettingsPage } from "./pages/SystemSettingsPage";
import { TestRunPage } from "./pages/TestRunPage";
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
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="brand-block">
          <strong>AI MIS Test</strong>
          <span>智能功能测试平台</span>
        </div>
        <nav className="app-nav" aria-label="主导航">
          {navigationItems.map((item) => {
            const Icon = item.icon;
            return (
              <a className={route === item.id ? "app-nav__item app-nav__item--active" : "app-nav__item"} href={`#${item.id}`} key={item.id}>
                <Icon size={18} />
                <span>{item.label}</span>
              </a>
            );
          })}
        </nav>
      </aside>
      <main className="app-main">
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
    case "mock-mis-demo":
      return <MockMisDemoPage />;
    case "settings":
      return <SystemSettingsPage />;
    case "test-run":
    default:
      return <TestRunPage />;
  }
}
