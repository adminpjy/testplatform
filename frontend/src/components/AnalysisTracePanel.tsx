import { AlertTriangle, Bot, CheckCircle2, Edit3, Loader2, Plus, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import type { TestCaseDSL, TestCaseStep } from "../types/platform";
import type { RuntimeMessage } from "../types/runtime";
import { methodLabel, readableRuntimeTitle } from "../utils/runtimeDisplay";
import { JsonCollapseBlock } from "./JsonCollapseBlock";

export function AnalysisTracePanel({
  messages,
  analyzing,
  dsl,
  onDslChange
}: {
  messages: RuntimeMessage[];
  analyzing: boolean;
  dsl: TestCaseDSL | null;
  onDslChange?: (dsl: TestCaseDSL) => void;
}) {
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const [editorDraft, setEditorDraft] = useState<TestCaseDSL | null>(null);
  const visibleMessages = messages.filter((message) => message.phase !== "llm_chunk");
  const status = useMemo(() => buildAnalysisStatus(visibleMessages, dsl, analyzing), [visibleMessages, dsl, analyzing]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [visibleMessages.length]);

  if (!analyzing && messages.length === 0 && !dsl) {
    return null;
  }

  function openDslEditor(mode: "edit" | "add" = "edit") {
    if (!dsl || !onDslChange) return;
    const draft = cloneDsl(dsl);
    if (mode === "add") {
      draft.steps.push(defaultDslStep());
    }
    setEditorDraft(draft);
  }

  function saveDslEditor() {
    if (editorDraft && onDslChange) {
      onDslChange(editorDraft);
    }
    setEditorDraft(null);
  }

  return (
    <section className="surface-panel analysis-trace-panel">
      <div className="panel-heading">
        <h2>
          <Bot size={16} />
          任务分解观察
        </h2>
        <span>{analyzing ? "流式分析中" : "分析已结束"}</span>
      </div>

      <div className="llm-status-grid">
        <div>
          <span>LLM 交互</span>
          <strong>{status.provider} / {status.model}</strong>
          <small>{status.endpoint || "未配置模型接口"}</small>
        </div>
        <div>
          <span>当前状态</span>
          <strong>{status.currentStage}</strong>
          <small>{status.latestMessage}</small>
        </div>
        <div>
          <span>DSL 步骤</span>
          <strong>{status.dslSteps > 0 ? `${status.dslSteps} 步` : "待生成"}</strong>
          <small>{status.dslDetail}</small>
        </div>
      </div>

      <div className="analysis-trace-grid">
        <div className="analysis-trace-stream">
          {visibleMessages.map((message) => (
            <article className={`analysis-trace-message analysis-trace-message--${message.type}`} key={message.id}>
              <span className="analysis-trace-message__icon">{messageIcon(message, analyzing)}</span>
              <div>
                <div className="analysis-trace-message__title">
                  <time>{formatTime(message.createdAt)}</time>
                  <strong>{readableTitle(message)}</strong>
                </div>
                <p>{message.content}</p>
                <div className="runtime-stream-message__meta">
                  <span>方法：{methodLabel(message.method)}</span>
                  {message.phase ? <span>阶段：{phaseLabel(message.phase)}</span> : null}
                </div>
                {Object.keys(message.metadata).length > 0 ? <JsonCollapseBlock title="查看请求/响应详情" value={message.metadata} /> : null}
              </div>
            </article>
          ))}
          <div ref={bottomRef} />
        </div>

        <aside className="dsl-preview-panel">
          <div className="dsl-preview-panel__heading">
            <div>
              <strong>DSL 步骤预览</strong>
              {dsl ? <span>{dsl.steps.length} 步</span> : <span>等待生成</span>}
            </div>
            {dsl && onDslChange ? (
              <div className="dsl-preview-panel__actions">
                <button className="ghost-button dsl-add-step-button" type="button" onClick={() => openDslEditor("edit")}>
                  <Edit3 size={14} />
                  编辑 DSL
                </button>
                <button className="ghost-button dsl-add-step-button" type="button" onClick={() => openDslEditor("add")}>
                  <Plus size={14} />
                  新增步骤
                </button>
              </div>
            ) : null}
          </div>
          {dsl ? (
            <>
              <datalist id="dsl-action-options">
                {DSL_ACTION_OPTIONS.map((action) => (
                  <option value={action} key={action} />
                ))}
              </datalist>
              <dl className="settings-list">
                <dt>用例</dt>
                <dd>{dsl.caseName || "-"}</dd>
                <dt>入口</dt>
                <dd>{dsl.baseUrl || "-"}</dd>
              </dl>
              <ol className="dsl-step-list">
                {dsl.steps.map((step, index) => (
                  <li key={`${step.action}-${step.target || index}`}>
                    <span>S{String(index + 1).padStart(3, "0")}</span>
                    <strong>{readableDslStepType(step)}</strong>
                    <em>{dslStepSummary(step)}</em>
                    {step.action === "navigate_path" ? (
                      <small>
                        成功判断：{Array.isArray(step.successCriteria) ? step.successCriteria.map(String).join("；") : "页面出现目标菜单并完成导航"}
                      </small>
                    ) : null}
                    {step.action === "business_goal" && step.intent ? <small>业务意图：{readableIntent(String(step.intent))}</small> : null}
                  </li>
                ))}
              </ol>
              {dsl.missingFields && dsl.missingFields.length > 0 ? (
                <div className="dsl-empty-reason">
                  <strong>仍需补充</strong>
                  <ul>
                    {dsl.missingFields.map((field) => (
                      <li key={field}>{field}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              <JsonCollapseBlock title="查看完整 DSL JSON" value={dsl} />
            </>
          ) : (
            <div className="dsl-empty-reason">
              <strong>{status.dslTitle}</strong>
              <p>{status.dslDetail}</p>
              {status.dslReasons.length > 0 ? (
                <ul>
                  {status.dslReasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          )}
        </aside>
      </div>
      {editorDraft && onDslChange ? (
        <DslEditorModal
          draft={editorDraft}
          onCancel={() => setEditorDraft(null)}
          onChange={setEditorDraft}
          onSave={saveDslEditor}
        />
      ) : null}
    </section>
  );
}

const DSL_ACTION_OPTIONS = [
  "open_url",
  "business_goal",
  "navigate_path",
  "click",
  "input",
  "select",
  "wait",
  "wait_for_text",
  "assert_text_exists",
  "assert_url_contains",
  "query_table",
  "query_table_count",
  "open_table_row",
  "process_table_rows",
  "fill_form",
  "auto_fill_form",
  "upload_file",
  "close_dialog_by_common_controls",
  "confirm_dialog",
  "summary_assert",
  "assert_result"
];

function DslEditorModal({
  draft,
  onCancel,
  onChange,
  onSave
}: {
  draft: TestCaseDSL;
  onCancel: () => void;
  onChange: (dsl: TestCaseDSL) => void;
  onSave: () => void;
}) {
  function updateStep(index: number, patch: Partial<TestCaseStep>) {
    onChange({
      ...draft,
      steps: draft.steps.map((step, itemIndex) => (itemIndex === index ? { ...step, ...patch } : step))
    });
  }

  function deleteStep(index: number) {
    onChange({ ...draft, steps: draft.steps.filter((_, itemIndex) => itemIndex !== index) });
  }

  function addStep() {
    onChange({ ...draft, steps: [...draft.steps, defaultDslStep()] });
  }

  return (
    <div className="dsl-editor-backdrop">
      <div className="dsl-editor-modal" role="dialog" aria-modal="true" aria-labelledby="dsl-editor-title">
        <div className="dsl-editor-modal__header">
          <div>
            <h3 id="dsl-editor-title">编辑 DSL</h3>
            <span>{draft.steps.length} 步</span>
          </div>
          <button className="icon-button" type="button" onClick={onCancel} title="关闭">
            <X size={16} />
          </button>
        </div>
        <div className="dsl-editor-modal__body">
          <div className="dsl-editor-meta-grid">
            <label>
              <span>用例</span>
              <input value={draft.caseName || ""} onChange={(event) => onChange({ ...draft, caseName: event.target.value })} />
            </label>
            <label>
              <span>入口</span>
              <input value={draft.baseUrl || ""} onChange={(event) => onChange({ ...draft, baseUrl: event.target.value })} />
            </label>
          </div>
          <ol className="dsl-step-list dsl-step-list--editable">
            {draft.steps.map((step, index) => (
              <EditableDslStep
                step={step}
                index={index}
                key={index}
                onDelete={() => deleteStep(index)}
                onUpdate={(patch) => updateStep(index, patch)}
              />
            ))}
          </ol>
        </div>
        <div className="dsl-editor-modal__footer">
          <button className="ghost-button" type="button" onClick={addStep}>
            <Plus size={14} />
            新增步骤
          </button>
          <div>
            <button className="secondary-button" type="button" onClick={onCancel}>
              取消
            </button>
            <button className="primary-button" type="button" onClick={onSave}>
              <CheckCircle2 size={14} />
              保存
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function EditableDslStep({
  step,
  index,
  onUpdate,
  onDelete
}: {
  step: TestCaseStep;
  index: number;
  onUpdate: (patch: Partial<TestCaseStep>) => void;
  onDelete: () => void;
}) {
  const valueKey = preferredStepValueKey(step);
  const valueText = String((step[valueKey] as string | number | undefined) ?? "");
  const pathSegments = Array.isArray(step.pathSegments) ? step.pathSegments.map(String).join("/") : "";

  function updateAction(action: string) {
    const patch: Partial<TestCaseStep> = { action };
    if (action === "wait" && !step.ms) {
      patch.ms = 1500;
    }
    if (action === "navigate_path" && !step.navigationType) {
      patch.navigationType = "menu_path";
    }
    onUpdate(patch);
  }

  function updatePathSegments(value: string) {
    const segments = parsePathSegmentsFromInput(value);
    onUpdate({
      pathSegments: segments,
      navigationType: navigationTypeForSegments(segments),
      target: segments.join("/")
    });
  }

  function parseTargetAsPath() {
    const segments = parsePathSegmentsFromInput(String(step.target || pathSegments || ""));
    if (segments.length < 2) return;
    onUpdate({
      pathSegments: segments,
      navigationType: navigationTypeForSegments(segments),
      target: segments.join("/")
    });
  }

  return (
    <li className="dsl-step-list__editable">
      <div className="dsl-step-editor__title">
        <span>S{String(index + 1).padStart(3, "0")}</span>
        <strong>{readableDslStepType(step)}</strong>
        <button className="icon-button" type="button" onClick={onDelete} title="删除步骤">
          <Trash2 size={14} />
        </button>
      </div>
      <div className="dsl-step-editor-grid">
        <label>
          <span>动作</span>
          <input list="dsl-action-options" value={String(step.action || "")} onChange={(event) => updateAction(event.target.value)} />
        </label>
        <label>
          <span>目标</span>
          <input value={String(step.target || "")} onChange={(event) => onUpdate({ target: event.target.value })} />
        </label>
        <label>
          <span>{valueKey === "text" ? "文本" : "值"}</span>
          <input value={valueText} onChange={(event) => onUpdate({ [valueKey]: event.target.value })} />
        </label>
        {step.action === "wait" ? (
          <label>
            <span>等待 ms</span>
            <input
              min={100}
              step={100}
              type="number"
              value={Number(step.ms || 1500)}
              onChange={(event) => onUpdate({ ms: Number(event.target.value || 1500) })}
            />
          </label>
        ) : null}
        {step.action === "navigate_path" ? (
          <label className="dsl-step-editor-grid__wide">
            <span>菜单路径</span>
            <input placeholder="工作台/我的待办" value={pathSegments} onChange={(event) => updatePathSegments(event.target.value)} />
          </label>
        ) : null}
        {step.action === "navigate_path" ? (
          <div className="dsl-step-editor-grid__wide dsl-step-editor-actions">
            <button className="secondary-button" type="button" onClick={parseTargetAsPath}>
              解析目标路径
            </button>
          </div>
        ) : null}
        <label className="dsl-step-editor-grid__wide">
          <span>说明</span>
          <input value={String(step.description || "")} onChange={(event) => onUpdate({ description: event.target.value })} />
        </label>
      </div>
    </li>
  );
}

const PORTAL_CATEGORY_HINTS = new Set([
  "我的应用",
  "办公自动化",
  "财务",
  "财务管理",
  "生产",
  "生产经营",
  "设备",
  "设备管理",
  "采购",
  "采购管理",
  "销售",
  "销售管理",
  "安环",
  "安全环保",
  "综合",
  "综合管理",
  "人力资源",
  "信息化"
]);

function cloneDsl(dsl: TestCaseDSL): TestCaseDSL {
  return JSON.parse(JSON.stringify(dsl)) as TestCaseDSL;
}

function defaultDslStep(): TestCaseStep {
  return {
    action: "wait",
    target: "登录后页面稳定",
    ms: 1500,
    description: "等待页面跳转或渲染稳定。"
  };
}

function parsePathSegmentsFromInput(value: string): string[] {
  const text = String(value || "").trim();
  if (!text || text.includes("://")) return [];
  const hasNonHyphenSeparator = /[/>→\\]/.test(text);
  const rawSegments = hasNonHyphenSeparator ? text.split(/\s*(?:\/|>|→|\\)\s*/) : text.split(/\s*-\s*/);
  const segments = rawSegments.map((item, index) => cleanPathSegment(item, index)).filter(Boolean);
  return normalizePortalSegments(segments);
}

function cleanPathSegment(value: string, index: number): string {
  let text = value.trim().replace(/^[“"'，,。；;：:]+|[”"'，,。；;：:]+$/g, "");
  if (index === 0) {
    text = text.replace(/^(进入|打开|点击|导航到|访问|前往|切换到|跳转到)/, "").trim();
  }
  return text;
}

function normalizePortalSegments(segments: string[]): string[] {
  if (segments.length < 3 || segments[0] !== "系统导航") return segments;
  let categoryIndex = 1;
  for (let index = 1; index < Math.min(segments.length, 4); index += 1) {
    if (PORTAL_CATEGORY_HINTS.has(segmentBase(segments[index]))) {
      categoryIndex = index;
      break;
    }
  }
  const appName = segments.slice(categoryIndex + 1).join("-").trim();
  if (!appName) return segments;
  return [segments[0], segments[categoryIndex], appName];
}

function segmentBase(value: string): string {
  return value.replace(/\s*[（(]\d+[）)]\s*$/, "").trim();
}

function navigationTypeForSegments(segments: string[]): string {
  return segments.length >= 3 && segments[0] === "系统导航" ? "portal_app_path" : "menu_path";
}

function preferredStepValueKey(step: TestCaseStep): "text" | "value" {
  if (["wait_for_text", "assert_text_exists", "assert_text_not_exists", "assert_url_contains"].includes(step.action)) return "text";
  if (step.text !== undefined && step.value === undefined) return "text";
  return "value";
}

function navigatePathSummary(step: Record<string, unknown>): string {
  const segments = Array.isArray(step.pathSegments) ? step.pathSegments.map(String) : [];
  return segments.length > 0 ? segments.join(" → ") : String(step.target || "");
}

function readableDslStepType(step: Record<string, unknown>): string {
  const action = String(step.action || "");
  const intent = String(step.intent || "");
  if (action === "navigate_path") return "菜单路径导航";
  if (action === "query_table" || intent === "query_list") return "查询列表";
  if (action === "open_table_row") return "打开表格行";
  if (action === "process_table_rows" || action === "for_each_table_row") return "处理表格行";
  if (action === "fill_form" || action === "auto_fill_form" || intent === "fill_form") return "填写表单";
  if (action === "select" || intent === "select_dropdown") return "选择下拉框";
  if (intent === "select_date" || intent === "select_date_range") return "选择日期";
  if (intent === "select_org") return "选择组织机构";
  if (intent === "select_person") return "选择人员";
  if (intent === "approval_pass") return "审批通过";
  if (intent === "approval_flow_view" || intent === "view_flow") return "查看审批流程";
  if (intent === "create_record") return "新增记录";
  if (intent === "update_record") return "修改记录";
  if (intent === "delete_record") return "删除记录";
  if (action === "assert_result" || action === "summary_assert" || intent === "assert_result") return "断言验证";
  return action || "测试步骤";
}

function readableIntent(intent: string): string {
  const labels: Record<string, string> = {
    approval_pass: "审批通过",
    approval_flow_view: "查看审批流程",
    view_flow: "查看审批流程",
    create_record: "新增记录",
    update_record: "修改记录",
    delete_record: "删除记录",
    query_list: "查询列表",
    fill_form: "填写表单"
  };
  return labels[intent] || intent;
}

function dslStepSummary(step: Record<string, unknown>): string {
  if (step.action === "navigate_path") return navigatePathSummary(step);
  const queryConditions = step.queryConditions;
  if (queryConditions && typeof queryConditions === "object") return `条件：${Object.entries(queryConditions).map(([key, value]) => `${key}=${String(value)}`).join("，")}`;
  const formData = step.formData;
  if (formData && typeof formData === "object") return `字段：${Object.keys(formData).join("，")}`;
  return String(step.target || step.description || "");
}

function readableTitle(message: RuntimeMessage): string {
  if (message.phase === "llm_request") return message.metadata.stage === "plan" ? "正在调用 LLM 生成 DSL" : "正在调用 LLM 分析目标";
  if (message.phase === "llm_response") return message.metadata.stage === "plan" ? "DSL 回复已接收" : "分析回复已接收";
  if (message.phase === "json_repair") return "正在校验 LLM JSON 输出";
  if (message.phase === "analysis_result") return "分析结果已生成";
  if (message.phase === "dsl_generated") return "DSL 已生成";
  return readableRuntimeTitle(message);
}

function phaseLabel(phase: string): string {
  if (phase === "llm_request") return "LLM 请求";
  if (phase === "llm_response") return "LLM 回复";
  if (phase === "json_repair") return "JSON 提取/修复";
  if (phase === "analysis_result") return "信息完整性判断";
  if (phase === "dsl_generated") return "DSL 生成";
  return phase;
}

function buildAnalysisStatus(messages: RuntimeMessage[], dsl: TestCaseDSL | null, analyzing: boolean) {
  const providerMessage = messages.find((message) => metadataValue(message, "provider") || metadataValue(message, "model"));
  const latest = [...messages].reverse().find((message) => message.phase !== "llm_chunk");
  const dslStatus = buildDslStatus(messages, dsl, analyzing);
  return {
    provider: metadataValue(providerMessage, "provider") || "openai_compatible",
    model: metadataValue(providerMessage, "model") || "DeepSeek-V4",
    endpoint: metadataValue(providerMessage, "endpoint"),
    currentStage: latest ? readableTitle(latest) : "等待分析",
    latestMessage: latest?.content || "点击分析后显示 LLM 交互状态",
    dslSteps: dsl?.steps.length || 0,
    ...dslStatus
  };
}

function buildDslStatus(messages: RuntimeMessage[], dsl: TestCaseDSL | null, analyzing: boolean) {
  if (dsl && dsl.steps.length > 0) {
    return {
      dslTitle: "DSL 已生成",
      dslDetail: "已生成可执行步骤，可以开始执行。",
      dslReasons: []
    };
  }
  if (analyzing) {
    return {
      dslTitle: "正在生成 DSL",
      dslDetail: "正在等待 LLM 返回并校验结构化步骤。",
      dslReasons: []
    };
  }
  const errorMessage = [...messages].reverse().find((message) => message.type === "error");
  if (errorMessage) {
    return {
      dslTitle: "DSL 未生成",
      dslDetail: "分析流程失败，未获得可执行 DSL。",
      dslReasons: [errorMessage.content || "分析失败，但后端未返回具体错误。"]
    };
  }
  const analysis = latestAnalysis(messages);
  if (analysis && analysis.readyToExecute === false) {
    const missingFields = Array.isArray(analysis.missingFields) ? analysis.missingFields.map(String) : [];
    const questions = Array.isArray(analysis.clarifyingQuestions) ? analysis.clarifyingQuestions.map(String) : [];
    return {
      dslTitle: "需要补充信息",
      dslDetail: "当前信息不足，暂不生成 DSL。",
      dslReasons: [...missingFields.map((item) => `缺少字段：${item}`), ...questions]
    };
  }
  if (messages.length > 0) {
    return {
      dslTitle: "DSL 未生成",
      dslDetail: "LLM 未返回符合平台 DSL 结构的结果。",
      dslReasons: ["请查看左侧分析消息中的错误，补充信息后重新分析。"]
    };
  }
  return {
    dslTitle: "等待分析",
    dslDetail: "点击“分析”后生成 DSL。",
    dslReasons: []
  };
}

function latestAnalysis(messages: RuntimeMessage[]): Record<string, unknown> | null {
  const message = [...messages].reverse().find((item) => item.metadata.analysis && typeof item.metadata.analysis === "object");
  return message?.metadata.analysis as Record<string, unknown> | null;
}

function metadataValue(message: RuntimeMessage | undefined, key: string): string | null {
  const value = message?.metadata[key];
  if (value === undefined || value === null || value === "") return null;
  return typeof value === "string" || typeof value === "number" || typeof value === "boolean" ? String(value) : null;
}

function messageIcon(message: RuntimeMessage, analyzing: boolean) {
  if (analyzing && message.type === "progress") {
    return <Loader2 className="runtime-stream-message__spinner" size={15} />;
  }
  if (message.type === "success") return <CheckCircle2 size={15} />;
  if (message.type === "warning" || message.type === "error") return <AlertTriangle size={15} />;
  return <Bot size={15} />;
}

function formatTime(value: string | null): string {
  if (!value) return "--:--:--";
  return new Date(value).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
