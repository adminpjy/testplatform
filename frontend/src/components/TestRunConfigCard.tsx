import { Bot, Bug, ChevronDown, ChevronUp, Play, Search, UserRoundCheck } from "lucide-react";

import type { AnalyzeResult, TestProject, TestSystem } from "../types/platform";

export function TestRunConfigCard({
  collapsed,
  testDataOpen,
  projects,
  systems,
  selectedProjectId,
  selectedSystemId,
  baseUrl,
  username,
  password,
  visionFallback,
  instruction,
  testDataJson,
  analysis,
  isAnalyzing,
  isExecuting,
  hasActiveRun,
  onToggleCollapsed,
  onToggleTestData,
  onProjectChange,
  onSystemChange,
  onBaseUrlChange,
  onUsernameChange,
  onPasswordChange,
  onVisionFallbackChange,
  onInstructionChange,
  onTestDataChange,
  onAnalyze,
  onExecute,
  onIntervention,
  onDebug
}: {
  collapsed: boolean;
  testDataOpen: boolean;
  projects: TestProject[];
  systems: TestSystem[];
  selectedProjectId: number | "";
  selectedSystemId: number | "";
  baseUrl: string;
  username: string;
  password: string;
  visionFallback: boolean;
  instruction: string;
  testDataJson: string;
  analysis: AnalyzeResult | null;
  isAnalyzing: boolean;
  isExecuting: boolean;
  hasActiveRun: boolean;
  onToggleCollapsed: () => void;
  onToggleTestData: () => void;
  onProjectChange: (projectId: number) => void;
  onSystemChange: (systemId: number | "") => void;
  onBaseUrlChange: (value: string) => void;
  onUsernameChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onVisionFallbackChange: (value: boolean) => void;
  onInstructionChange: (value: string) => void;
  onTestDataChange: (value: string) => void;
  onAnalyze: () => void;
  onExecute: () => void;
  onIntervention: () => void;
  onDebug: () => void;
}) {
  return (
    <section className="surface-panel test-config-card">
      <div className="panel-heading test-config-card__heading">
        <div>
          <h2>测试配置</h2>
          <span>配置目标系统、测试账号和自然语言目标</span>
        </div>
        <button className="secondary-button" type="button" onClick={onToggleCollapsed}>
          {collapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
          {collapsed ? "展开配置" : "收起配置"}
        </button>
      </div>

      {!collapsed ? (
        <>
          <div className="compact-form-grid">
            <label>
              <span>项目</span>
              <select value={selectedProjectId} onChange={(event) => onProjectChange(Number(event.target.value))}>
                {projects.map((project) => (
                  <option value={project.id} key={project.id}>
                    {project.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>被测系统</span>
              <select
                value={selectedSystemId}
                onChange={(event) => onSystemChange(event.target.value ? Number(event.target.value) : "")}
              >
                <option value="">未选择</option>
                {systems.map((system) => (
                  <option value={system.id} key={system.id}>
                    {system.system_name}
                  </option>
                ))}
              </select>
            </label>
            <label className="compact-form-grid__wide">
              <span>baseUrl</span>
              <input value={baseUrl} onChange={(event) => onBaseUrlChange(event.target.value)} />
            </label>
            <label>
              <span>用户名</span>
              <input value={username} onChange={(event) => onUsernameChange(event.target.value)} />
            </label>
            <label>
              <span>密码</span>
              <input type="password" value={password} onChange={(event) => onPasswordChange(event.target.value)} />
            </label>
            <label className="switch-row">
              <input type="checkbox" checked={visionFallback} onChange={(event) => onVisionFallbackChange(event.target.checked)} />
              <span>启用视觉兜底</span>
            </label>
          </div>

          <label className="stacked-field compact-textarea">
            <span>自然语言测试目标</span>
            <textarea value={instruction} rows={4} onChange={(event) => onInstructionChange(event.target.value)} />
          </label>

          <div className="json-editor-toggle">
            <button className="ghost-button" type="button" onClick={onToggleTestData}>
              {testDataOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              {testDataOpen ? "收起测试数据 JSON" : "展开测试数据 JSON"}
            </button>
          </div>
          {testDataOpen ? (
            <label className="stacked-field compact-json-editor">
              <span>测试数据补充</span>
              <textarea value={testDataJson} rows={5} onChange={(event) => onTestDataChange(event.target.value)} />
            </label>
          ) : null}

          {analysis ? <AnalysisPanel analysis={analysis} /> : null}
        </>
      ) : null}

      <div className="action-bar test-config-card__actions">
        <button className="secondary-button" type="button" onClick={onAnalyze} disabled={isAnalyzing || !instruction}>
          <Search size={16} />
          {isAnalyzing ? "分析中" : "分析"}
        </button>
        <button className="primary-button" type="button" onClick={onExecute} disabled={isExecuting || !instruction}>
          <Play size={16} />
          {isExecuting ? "执行中" : "开始执行"}
        </button>
        <button className="secondary-button" type="button" onClick={onIntervention} disabled={!hasActiveRun}>
          <UserRoundCheck size={16} />
          人工介入
        </button>
        <button className="ghost-button" type="button" onClick={onDebug} disabled={!hasActiveRun}>
          <Bug size={16} />
          调试详情
        </button>
      </div>
    </section>
  );
}

function AnalysisPanel({ analysis }: { analysis: AnalyzeResult }) {
  return (
    <section className="analysis-panel analysis-panel--compact">
      <div className="analysis-panel__title">
        <Bot size={16} />
        <strong>{analysis.readyToExecute ? "信息足够，可以执行" : "需要补充信息"}</strong>
        <span>置信度 {Math.round(analysis.confidence * 100)}%</span>
      </div>
      <p>{analysis.understoodGoal || analysis.normalizedInstruction}</p>
      {analysis.clarifyingQuestions.length > 0 ? (
        <ul>
          {analysis.clarifyingQuestions.map((question) => (
            <li key={question}>{question}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
