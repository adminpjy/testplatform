import { ExternalLink, Monitor } from "lucide-react";
import { useState } from "react";

const DEFAULT_DEMO_URL = (import.meta.env.VITE_MOCK_MIS_URL as string | undefined) || "http://127.0.0.1:5174/login";

export function MockMisDemoPage() {
  const [demoUrl, setDemoUrl] = useState(DEFAULT_DEMO_URL);

  return (
    <div className="page-stack">
      <section className="surface-panel">
        <div className="panel-heading">
          <h1>
            <Monitor size={18} />
            Mock MIS Demo
          </h1>
          <a className="secondary-link" href={demoUrl} target="_blank" rel="noreferrer">
            <ExternalLink size={16} />
            新窗口打开
          </a>
        </div>
        <div className="mock-url-row">
          <input value={demoUrl} onChange={(event) => setDemoUrl(event.target.value)} />
          <button className="secondary-button" type="button" onClick={() => setDemoUrl("http://127.0.0.1:5174/login")}>
            登录页
          </button>
          <button
            className="secondary-button"
            type="button"
            onClick={() => setDemoUrl("http://127.0.0.1:5174/login?notice=account-expiry")}
          >
            账号到期
          </button>
          <button
            className="secondary-button"
            type="button"
            onClick={() => setDemoUrl("http://127.0.0.1:5174/todo")}
          >
            我的待办
          </button>
        </div>
      </section>

      <section className="surface-panel mock-frame-panel">
        <iframe title="Mock MIS Demo" src={demoUrl} />
      </section>
    </div>
  );
}
