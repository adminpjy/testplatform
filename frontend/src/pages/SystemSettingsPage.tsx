import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { getHealth, getPrompts, getSystemInfo, previewPrompt, reloadPrompts } from "../api/platform";
import { JsonCollapseBlock } from "../components/JsonCollapseBlock";
import { StatusBadge } from "../components/StatusBadge";
import type { HealthInfo, PromptInfo, PromptPreview, SystemInfo } from "../types/platform";

export function SystemSettingsPage() {
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [prompts, setPrompts] = useState<PromptInfo[]>([]);
  const [selectedPromptKey, setSelectedPromptKey] = useState<string>("");
  const [promptSearch, setPromptSearch] = useState("");
  const [promptFileFilter, setPromptFileFilter] = useState("");
  const [promptPreview, setPromptPreview] = useState<PromptPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"runtime" | "prompts">("runtime");

  useEffect(() => {
    void loadSettings();
  }, []);

  async function loadSettings() {
    setLoading(true);
    setError(null);
    try {
      const [nextHealth, nextSystemInfo, promptList] = await Promise.all([getHealth(), getSystemInfo(), getPrompts()]);
      setHealth(nextHealth);
      setSystemInfo(nextSystemInfo);
      setPrompts(promptList);
      if (!selectedPromptKey && promptList.length > 0) {
        setSelectedPromptKey(promptList[0].key);
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    } finally {
      setLoading(false);
    }
  }

  async function handleReloadPrompts() {
    setLoading(true);
    setError(null);
    try {
      await reloadPrompts();
      const promptList = await getPrompts();
      setPrompts(promptList);
      setPromptPreview(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    } finally {
      setLoading(false);
    }
  }

  async function handlePreviewPrompt(prompt: PromptInfo) {
    setError(null);
    try {
      const variables = Object.fromEntries(prompt.variables.map((name) => [name, samplePromptVariable(name)]));
      setPromptPreview(await previewPrompt(prompt.key, variables));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    }
  }

  const promptFiles = Array.from(new Set(prompts.map((prompt) => prompt.file))).sort();
  const filteredPrompts = prompts.filter((prompt) => {
    const text = `${prompt.key} ${prompt.name} ${prompt.file}`.toLowerCase();
    return text.includes(promptSearch.toLowerCase()) && (!promptFileFilter || prompt.file === promptFileFilter);
  });
  const selectedPrompt = prompts.find((prompt) => prompt.key === selectedPromptKey) || filteredPrompts[0] || null;

  return (
    <div className="page-stack">
      <section className="surface-panel">
        <div className="panel-heading">
          <h1>系统设置</h1>
          <button className="secondary-button" type="button" onClick={() => void loadSettings()}>
            <RefreshCw size={16} />
            {loading ? "刷新中" : "刷新"}
          </button>
        </div>
        {error ? <pre className="error-detail error-detail--collapsed">{error}</pre> : null}
        <div className="tab-strip">
          <button className={activeTab === "runtime" ? "tab-button tab-button--active" : "tab-button"} type="button" onClick={() => setActiveTab("runtime")}>
            运行设置
          </button>
          <button className={activeTab === "prompts" ? "tab-button tab-button--active" : "tab-button"} type="button" onClick={() => setActiveTab("prompts")}>
            LLM 提示词
          </button>
        </div>
      </section>

      {activeTab === "runtime" ? <section className="settings-grid">
        <div className="surface-panel">
          <div className="panel-heading">
            <h2>服务状态</h2>
            <StatusBadge value={health?.status || "unknown"} />
          </div>
          <dl className="settings-list">
            <dt>服务名称</dt>
            <dd>{systemInfo?.service || health?.service || "-"}</dd>
            <dt>版本</dt>
            <dd>{systemInfo?.version || "-"}</dd>
            <dt>环境</dt>
            <dd>{systemInfo?.environment || "-"}</dd>
          </dl>
        </div>

        <div className="surface-panel">
          <div className="panel-heading">
            <h2>数据连接</h2>
            <StatusBadge value={systemInfo?.database.connected ? "connected" : "error"} />
          </div>
          <dl className="settings-list">
            <dt>数据库</dt>
            <dd>{systemInfo?.database.connected ? "已连接" : "未连接"}</dd>
            <dt>项目数量</dt>
            <dd>{systemInfo?.project_count ?? "-"}</dd>
            <dt>被测系统</dt>
            <dd>{systemInfo?.system_count ?? "-"}</dd>
            <dt>能力规则</dt>
            <dd>{systemInfo?.ability_rule_count ?? "-"}</dd>
          </dl>
        </div>

        <div className="surface-panel">
          <div className="panel-heading">
            <h2>前端运行</h2>
          </div>
          <dl className="settings-list">
            <dt>API Base</dt>
            <dd>{(import.meta.env.VITE_API_BASE_URL as string | undefined) || "同源代理"}</dd>
            <dt>视觉兜底</dt>
            <dd>执行时按测试运行页开关传入</dd>
          </dl>
        </div>
      </section> : null}

      {activeTab === "prompts" ? (
        <section className="surface-panel prompt-manager-panel">
          <div className="panel-heading">
            <h2>LLM 提示词</h2>
            <button className="secondary-button" type="button" onClick={() => void handleReloadPrompts()}>
              <RefreshCw size={16} />
              重新加载 Prompt
            </button>
          </div>
          <div className="prompt-toolbar">
            <input value={promptSearch} onChange={(event) => setPromptSearch(event.target.value)} placeholder="搜索 prompt_key / 名称" />
            <select value={promptFileFilter} onChange={(event) => setPromptFileFilter(event.target.value)}>
              <option value="">全部文件</option>
              {promptFiles.map((file) => <option key={file} value={file}>{file}</option>)}
            </select>
          </div>
          <div className="prompt-manager-grid">
            <div className="prompt-list">
              {filteredPrompts.map((prompt) => (
                <button
                  className={selectedPrompt?.key === prompt.key ? "prompt-list-item prompt-list-item--active" : "prompt-list-item"}
                  key={prompt.key}
                  type="button"
                  onClick={() => {
                    setSelectedPromptKey(prompt.key);
                    setPromptPreview(null);
                  }}
                >
                  <strong>{prompt.key}</strong>
                  <span>{prompt.file}</span>
                  <StatusBadge value={prompt.enabled ? "active" : "disabled"} />
                </button>
              ))}
            </div>
            <div className="prompt-detail">
              {selectedPrompt ? (
                <>
                  <div className="panel-heading">
                    <div>
                      <h3>{selectedPrompt.name}</h3>
                      <span>{selectedPrompt.key} / v{selectedPrompt.version} / {selectedPrompt.file}</span>
                    </div>
                    <button className="ghost-button" type="button" onClick={() => void handlePreviewPrompt(selectedPrompt)}>预览渲染</button>
                  </div>
                  <dl className="settings-list">
                    <dt>变量</dt>
                    <dd>{selectedPrompt.variables.join(", ") || "-"}</dd>
                    <dt>模型配置</dt>
                    <dd>{selectedPrompt.model_profile} / {selectedPrompt.output_format}</dd>
                  </dl>
                  <JsonCollapseBlock title="system prompt" value={selectedPrompt.system} />
                  <JsonCollapseBlock title="user prompt" value={selectedPrompt.user} />
                  {promptPreview ? <JsonCollapseBlock title="渲染预览" value={promptPreview} /> : null}
                </>
              ) : <div className="empty-state">没有匹配的 Prompt</div>}
            </div>
          </div>
        </section>
      ) : null}
    </div>
  );
}

function samplePromptVariable(name: string): unknown {
  if (name.endsWith("_json") || name.includes("context") || name.includes("data") || name.includes("systems")) return {};
  if (name === "allowed_actions") return "open_url, navigate_path, business_goal, assert_text_exists";
  if (name === "instruction") return "登录系统，进入工作台/我的待办，确认页面存在我的待办。";
  if (name === "path_segments") return ["工作台", "我的待办"];
  if (name === "target") return "工作台/我的待办";
  return "";
}
