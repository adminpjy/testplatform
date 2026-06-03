import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { getHealth, getLLMSettings, getPrompts, getSystemInfo, previewPrompt, reloadPrompts, updateLLMSettings } from "../api/platform";
import { JsonCollapseBlock } from "../components/JsonCollapseBlock";
import { StatusBadge } from "../components/StatusBadge";
import type { HealthInfo, LLMProfile, LLMSettings, PromptInfo, PromptPreview, SystemInfo } from "../types/platform";
import { labelBoolean, labelEnvironment, labelPromptVariable } from "../utils/displayLabels";

export function SystemSettingsPage() {
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [prompts, setPrompts] = useState<PromptInfo[]>([]);
  const [selectedPromptKey, setSelectedPromptKey] = useState<string>("");
  const [promptSearch, setPromptSearch] = useState("");
  const [promptFileFilter, setPromptFileFilter] = useState("");
  const [promptPreview, setPromptPreview] = useState<PromptPreview | null>(null);
  const [llmSettings, setLlmSettings] = useState<LLMSettings | null>(null);
  const [llmDraft, setLlmDraft] = useState<LLMSettings | null>(null);
  const [llmMessage, setLlmMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"runtime" | "llm" | "prompts">("runtime");

  useEffect(() => {
    void loadSettings();
  }, []);

  async function loadSettings() {
    setLoading(true);
    setError(null);
    try {
      const [nextHealth, nextSystemInfo, promptList, nextLlmSettings] = await Promise.all([getHealth(), getSystemInfo(), getPrompts(), getLLMSettings()]);
      setHealth(nextHealth);
      setSystemInfo(nextSystemInfo);
      setPrompts(promptList);
      setLlmSettings(nextLlmSettings);
      setLlmDraft(cloneLlmSettings(nextLlmSettings));
      if (!selectedPromptKey && promptList.length > 0) {
        setSelectedPromptKey(promptList[0].key);
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveLlmSettings() {
    if (!llmDraft) return;
    setLoading(true);
    setError(null);
    setLlmMessage(null);
    try {
      const saved = await updateLLMSettings(llmDraft);
      setLlmSettings(saved);
      setLlmDraft(cloneLlmSettings(saved));
      setLlmMessage(`已切换到：${saved.effective?.name || saved.activeProfileId}`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    } finally {
      setLoading(false);
    }
  }

  function updateLlmProfile(profileId: string, patch: Partial<LLMProfile>) {
    setLlmDraft((current) => {
      if (!current) return current;
      return {
        ...current,
        profiles: current.profiles.map((profile) => (profile.id === profileId ? { ...profile, ...patch } : profile)),
      };
    });
  }

  function addLlmProfile() {
    setLlmDraft((current) => {
      const base = current || { activeProfileId: "", profiles: [], effective: null };
      const id = `llm-${Date.now()}`;
      const profile: LLMProfile = {
        id,
        name: "新的 DeepSeek V4 服务",
        provider: "openai_compatible",
        baseUrl: "",
        model: "DeepSeek-V4",
        stream: false,
        verifySsl: true,
        timeoutSeconds: 120,
        maxTokens: 8192,
        temperature: 0,
        topP: 0.95,
        caBundle: "",
        trustEnv: true,
        apiKey: "",
      };
      return { ...base, activeProfileId: base.activeProfileId || id, profiles: [...base.profiles, profile] };
    });
  }

  function removeLlmProfile(profileId: string) {
    setLlmDraft((current) => {
      if (!current || current.profiles.length <= 1) return current;
      const profiles = current.profiles.filter((profile) => profile.id !== profileId);
      const activeProfileId = current.activeProfileId === profileId ? profiles[0].id : current.activeProfileId;
      return { ...current, activeProfileId, profiles };
    });
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
          <button className={activeTab === "llm" ? "tab-button tab-button--active" : "tab-button"} type="button" onClick={() => setActiveTab("llm")}>
            大模型服务
          </button>
          <button className={activeTab === "prompts" ? "tab-button tab-button--active" : "tab-button"} type="button" onClick={() => setActiveTab("prompts")}>
            大模型提示词
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
            <dd>{systemInfo?.environment ? labelEnvironment(systemInfo.environment) : "-"}</dd>
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
            <dt>前端接口地址</dt>
            <dd>{(import.meta.env.VITE_API_BASE_URL as string | undefined) || "同源代理"}</dd>
            <dt>视觉兜底</dt>
            <dd>执行时按测试运行页开关传入</dd>
          </dl>
        </div>
      </section> : null}

      {activeTab === "llm" ? (
        <section className="surface-panel llm-settings-panel">
          <div className="panel-heading">
            <div>
              <h2>大模型服务</h2>
              <span>选择自然语言分析、测试步骤生成、失败分析和人工介入方案使用的模型服务。</span>
            </div>
            <div className="action-bar">
              <button className="secondary-button" type="button" onClick={addLlmProfile}>新增服务</button>
              <button className="primary-button" type="button" disabled={loading || !llmDraft} onClick={() => void handleSaveLlmSettings()}>
                保存并生效
              </button>
            </div>
          </div>
          {llmMessage ? <div className="debug-feedback">{llmMessage}</div> : null}
          {llmSettings?.effective ? (
            <dl className="settings-list llm-effective-summary">
              <dt>当前生效</dt>
              <dd>{llmSettings.effective.name}</dd>
              <dt>模型</dt>
              <dd>{llmSettings.effective.model}</dd>
            <dt>服务地址</dt>
            <dd>{llmSettings.effective.baseUrl}</dd>
            <dt>流式</dt>
            <dd>{llmSettings.effective.stream ? "开启" : "关闭"}</dd>
            </dl>
          ) : null}
          <div className="llm-profile-list">
            {(llmDraft?.profiles || []).map((profile) => (
              <div className={llmDraft?.activeProfileId === profile.id ? "llm-profile-card llm-profile-card--active" : "llm-profile-card"} key={profile.id}>
                <div className="llm-profile-card__header">
                  <label className="switch-row">
                    <input
                      type="radio"
                      checked={llmDraft?.activeProfileId === profile.id}
                      onChange={() => setLlmDraft((current) => (current ? { ...current, activeProfileId: profile.id } : current))}
                    />
                    <span>设为当前服务</span>
                  </label>
                  <button className="ghost-button" type="button" disabled={(llmDraft?.profiles.length || 0) <= 1} onClick={() => removeLlmProfile(profile.id)}>
                    删除
                  </button>
                </div>
                <div className="form-grid">
                  <label>
                    <span>服务编号</span>
                    <input value={profile.id} readOnly />
                  </label>
                  <label>
                    <span>名称</span>
                    <input value={profile.name} onChange={(event) => updateLlmProfile(profile.id, { name: event.target.value })} />
                  </label>
                  <label className="form-grid__wide">
                    <span>服务地址</span>
                    <input value={profile.baseUrl} onChange={(event) => updateLlmProfile(profile.id, { baseUrl: event.target.value })} />
                  </label>
                  <label>
                    <span>接口密钥</span>
                    <input
                      type="password"
                      value={profile.apiKey || ""}
                      onChange={(event) => updateLlmProfile(profile.id, { apiKey: event.target.value })}
                      placeholder={profile.apiKeyMasked ? `已保存：${profile.apiKeyMasked}` : "请输入接口密钥"}
                    />
                  </label>
                  <label>
                    <span>模型</span>
                    <input value={profile.model} onChange={(event) => updateLlmProfile(profile.id, { model: event.target.value })} />
                  </label>
                  <label className="form-grid__wide">
                    <span>企业根证书文件路径</span>
                    <input
                      value={profile.caBundle || ""}
                      onChange={(event) => updateLlmProfile(profile.id, { caBundle: event.target.value })}
                      placeholder="可选：企业根证书文件路径"
                    />
                  </label>
                  <label>
                    <span>最大输出长度</span>
                    <input type="number" value={profile.maxTokens} onChange={(event) => updateLlmProfile(profile.id, { maxTokens: Number(event.target.value) })} />
                  </label>
                  <label>
                    <span>超时秒数</span>
                    <input type="number" value={profile.timeoutSeconds} onChange={(event) => updateLlmProfile(profile.id, { timeoutSeconds: Number(event.target.value) })} />
                  </label>
                  <label>
                    <span>随机性</span>
                    <input type="number" step="0.1" value={profile.temperature} onChange={(event) => updateLlmProfile(profile.id, { temperature: Number(event.target.value) })} />
                  </label>
                  <label>
                    <span>采样范围</span>
                    <input type="number" step="0.01" value={profile.topP} onChange={(event) => updateLlmProfile(profile.id, { topP: Number(event.target.value) })} />
                  </label>
                  <label className="switch-row">
                    <input type="checkbox" checked={profile.stream} onChange={(event) => updateLlmProfile(profile.id, { stream: event.target.checked })} />
                    <span>启用大模型流式输出</span>
                  </label>
                  <label className="switch-row">
                    <input type="checkbox" checked={profile.verifySsl} onChange={(event) => updateLlmProfile(profile.id, { verifySsl: event.target.checked })} />
                    <span>校验 SSL 证书</span>
                  </label>
                  <label className="switch-row">
                    <input type="checkbox" checked={profile.trustEnv} onChange={(event) => updateLlmProfile(profile.id, { trustEnv: event.target.checked })} />
                    <span>读取代理/证书环境变量</span>
                  </label>
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {activeTab === "prompts" ? (
        <section className="surface-panel prompt-manager-panel">
          <div className="panel-heading">
            <h2>大模型提示词</h2>
            <button className="secondary-button" type="button" onClick={() => void handleReloadPrompts()}>
              <RefreshCw size={16} />
              重新加载提示词
            </button>
          </div>
          <div className="prompt-toolbar">
            <input value={promptSearch} onChange={(event) => setPromptSearch(event.target.value)} placeholder="搜索提示词编码或名称" />
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
                    <dd>{selectedPrompt.variables.map(labelPromptVariable).join("，") || "-"}</dd>
                    <dt>模型配置</dt>
                    <dd>{selectedPrompt.model_profile} / {labelOutputFormat(selectedPrompt.output_format)}</dd>
                    <dt>是否启用</dt>
                    <dd>{labelBoolean(selectedPrompt.enabled)}</dd>
                  </dl>
                  <JsonCollapseBlock title="系统提示词" value={selectedPrompt.system} />
                  <JsonCollapseBlock title="用户提示词" value={selectedPrompt.user} />
                  {promptPreview ? <JsonCollapseBlock title="渲染预览" value={promptPreview} /> : null}
                </>
          ) : <div className="empty-state">没有匹配的提示词</div>}
            </div>
          </div>
        </section>
      ) : null}
    </div>
  );
}

function cloneLlmSettings(value: LLMSettings): LLMSettings {
  return {
    activeProfileId: value.activeProfileId,
    effective: value.effective ? { ...value.effective, apiKey: "" } : null,
    profiles: value.profiles.map((profile) => ({ ...profile, apiKey: "" })),
  };
}

function samplePromptVariable(name: string): unknown {
  if (name.endsWith("_json") || name.includes("context") || name.includes("data") || name.includes("systems")) return {};
  if (name === "allowed_actions") return "打开地址、按路径导航、业务目标、校验文本存在";
  if (name === "instruction") return "登录系统，进入工作台/我的待办，确认页面存在我的待办。";
  if (name === "path_segments") return ["工作台", "我的待办"];
  if (name === "target") return "工作台/我的待办";
  return "";
}

function labelOutputFormat(value: string): string {
  const labels: Record<string, string> = {
    json: "结构化输出",
    text: "文本输出",
    markdown: "Markdown 文本"
  };
  return labels[value] || "自定义输出";
}
