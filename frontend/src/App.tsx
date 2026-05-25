import { RuntimeStreamPanel } from "./components/RuntimeStreamPanel";
import "./styles/app.css";

export default function App() {
  const params = new URLSearchParams(window.location.search);
  const runId = Number(params.get("runId") || "1");

  return (
    <main className="app-shell">
      <RuntimeStreamPanel runId={Number.isFinite(runId) && runId > 0 ? runId : 1} />
    </main>
  );
}
