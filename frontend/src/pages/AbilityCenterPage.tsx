import { BarChart3, BookOpen, FileWarning, History, Lightbulb, RefreshCw, ScrollText, Settings2, WandSparkles } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import {
  enableRuleDraft,
  getAbilityKnowledge,
  getAbilityRules,
  getAbilityStats,
  getFailureSamples,
  getHumanInterventions,
  getPrompts,
  getRuleDrafts,
  previewPrompt,
  reloadPrompts,
  updateAbilityRule
} from "../api/platform";
import { fileUrl } from "../api/client";
import { DataTable } from "../components/DataTable";
import { JsonCollapseBlock } from "../components/JsonCollapseBlock";
import { StatusBadge } from "../components/StatusBadge";
import type {
  AbilityKnowledge,
  AbilityOperationOverview,
  AbilityRule,
  AbilityStats,
  FailureSample,
  HumanIntervention,
  PromptInfo,
  PromptPreview,
  RuleDraft
} from "../types/platform";

type AbilityTab = "overview" | "rules" | "knowledge" | "failures" | "interventions" | "drafts" | "prompts" | "stats";

const tabs: Array<{ id: AbilityTab; label: string }> = [
  { id: "overview", label: "操作能力总览" },
  { id: "rules", label: "规则库" },
  { id: "knowledge", label: "页面知识库" },
  { id: "failures", label: "失败样本" },
  { id: "interventions", label: "人工介入记录" },
  { id: "drafts", label: "规则草案" },
  { id: "prompts", label: "Prompt 配置" },
  { id: "stats", label: "能力统计" }
];

const jsonFields = [
  "match_config_json",
  "action_config_json",
  "success_criteria_json",
  "fallback_strategies_json",
  "failure_patterns_json",
  "recovery_strategies_json"
] as const;

export function AbilityCenterPage() {
  const [activeTab, setActiveTab] = useState<AbilityTab>("overview");
  const [rules, setRules] = useState<AbilityRule[]>([]);
  const [knowledge, setKnowledge] = useState<AbilityKnowledge[]>([]);
  const [failureSamples, setFailureSamples] = useState<FailureSample[]>([]);
  const [interventions, setInterventions] = useState<HumanIntervention[]>([]);
  const [ruleDrafts, setRuleDrafts] = useState<RuleDraft[]>([]);
  const [prompts, setPrompts] = useState<PromptInfo[]>([]);
  const [stats, setStats] = useState<AbilityStats | null>(null);
  const [selectedRule, setSelectedRule] = useState<AbilityRule | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [ruleList, knowledgeList, sampleList, interventionList, draftList, promptList, statsPayload] = await Promise.all([
        getAbilityRules(),
        getAbilityKnowledge(),
        getFailureSamples(),
        getHumanInterventions(),
        getRuleDrafts(),
        getPrompts(),
        getAbilityStats()
      ]);
      setRules(ruleList);
      setKnowledge(knowledgeList);
      setFailureSamples(sampleList);
      setInterventions(interventionList);
      setRuleDrafts(draftList);
      setPrompts(promptList);
      setStats(statsPayload);
      setSelectedRule((current) => {
        if (!current) return ruleList[0] || null;
        return ruleList.find((rule) => rule.id === current.id) || ruleList[0] || null;
      });
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    } finally {
      setLoading(false);
    }
  }

  async function handleEnableDraft(draftId: number) {
    setError(null);
    try {
      await enableRuleDraft(draftId);
      await loadData();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    }
  }

  async function handleUpdateRule(ruleId: number, payload: Partial<AbilityRule>) {
    setError(null);
    try {
      const updated = await updateAbilityRule(ruleId, payload);
      setRules((current) => current.map((rule) => (rule.id === updated.id ? updated : rule)));
      setSelectedRule(updated);
      setStats(await getAbilityStats());
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    }
  }

  return (
    <div className="page-stack ability-page">
      <section className="surface-panel ability-center-header">
        <div className="panel-heading">
          <h1>能力中心</h1>
          <button className="secondary-button" type="button" onClick={() => void loadData()}>
            <RefreshCw size={16} />
            {loading ? "刷新中" : "刷新"}
          </button>
        </div>
        <div className="tab-strip">
          {tabs.map((tab) => (
            <button
              className={activeTab === tab.id ? "tab-button tab-button--active" : "tab-button"}
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
        {error ? <pre className="error-detail error-detail--collapsed">{error}</pre> : null}
      </section>

      {activeTab === "overview" ? <OperationOverviewView overview={stats?.operationOverview || fallbackOverview(rules)} /> : null}
      {activeTab === "rules" ? <RulesView rules={rules} selectedRule={selectedRule} onSelectRule={setSelectedRule} onUpdateRule={handleUpdateRule} /> : null}
      {activeTab === "knowledge" ? <KnowledgeView knowledge={knowledge} /> : null}
      {activeTab === "failures" ? <FailureSamplesView samples={failureSamples} drafts={ruleDrafts} interventions={interventions} /> : null}
      {activeTab === "interventions" ? <InterventionView interventions={interventions} /> : null}
      {activeTab === "drafts" ? <RuleDraftView drafts={ruleDrafts} onEnableDraft={handleEnableDraft} /> : null}
      {activeTab === "prompts" ? <PromptConfigView prompts={prompts} onReload={loadData} /> : null}
      {activeTab === "stats" ? <AbilityStatsView stats={stats} /> : null}
    </div>
  );
}

function OperationOverviewView({ overview }: { overview: AbilityOperationOverview[] }) {
  return (
    <section className="ability-overview-grid">
      {overview.map((item) => (
        <article className="surface-panel ability-overview-card" key={item.key}>
          <div className="ability-overview-card__heading">
            <strong>{item.label}</strong>
            <span>{item.ruleTypes.join(" / ")}</span>
          </div>
          <dl>
            <div>
              <dt>规则</dt>
              <dd>{item.ruleCount}</dd>
            </div>
            <div>
              <dt>active</dt>
              <dd>{item.activeCount}</dd>
            </div>
            <div>
              <dt>命中</dt>
              <dd>{item.recentHitCount}</dd>
            </div>
            <div>
              <dt>失败</dt>
              <dd>{item.recentFailureCount}</dd>
            </div>
          </dl>
        </article>
      ))}
    </section>
  );
}

function RulesView({
  rules,
  selectedRule,
  onSelectRule,
  onUpdateRule
}: {
  rules: AbilityRule[];
  selectedRule: AbilityRule | null;
  onSelectRule: (rule: AbilityRule) => void;
  onUpdateRule: (ruleId: number, payload: Partial<AbilityRule>) => Promise<void>;
}) {
  const ruleTypes = useMemo(() => Array.from(new Set(rules.map((rule) => rule.rule_type))).sort(), [rules]);
  const [ruleTypeFilter, setRuleTypeFilter] = useState("");
  const filteredRules = rules.filter((rule) => !ruleTypeFilter || rule.rule_type === ruleTypeFilter);
  return (
    <div className="ability-rules-layout">
      <section className="surface-panel ability-rules-list">
        <div className="panel-heading ability-rules-toolbar">
          <h2>
            <ScrollText size={18} />
            规则库
          </h2>
          <select className="ability-rule-type-filter" value={ruleTypeFilter} onChange={(event) => setRuleTypeFilter(event.target.value)}>
            <option value="">全部 rule_type</option>
            {ruleTypes.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </div>
        <DataTable
          columns={[
            { key: "code", title: "规则编码", render: (rule) => <button className="link-button" type="button" onClick={() => onSelectRule(rule)}>{rule.rule_code}</button> },
            { key: "name", title: "名称", render: (rule) => rule.rule_name },
            { key: "type", title: "类型", render: (rule) => rule.rule_type },
            { key: "intent", title: "意图", render: (rule) => rule.intent || "-" },
            { key: "risk", title: "风险", render: (rule) => rule.risk_level },
            { key: "status", title: "状态", render: (rule) => <StatusBadge value={rule.status} /> }
          ]}
          rows={filteredRules}
          emptyText="暂无规则"
          getRowKey={(rule) => rule.id}
        />
      </section>
      <RuleDetailEditor rule={selectedRule} onUpdateRule={onUpdateRule} />
    </div>
  );
}

function RuleDetailEditor({
  rule,
  onUpdateRule
}: {
  rule: AbilityRule | null;
  onUpdateRule: (ruleId: number, payload: Partial<AbilityRule>) => Promise<void>;
}) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [editorError, setEditorError] = useState<string | null>(null);

  useEffect(() => {
    if (!rule) {
      setDrafts({});
      return;
    }
    setDrafts(
      Object.fromEntries(jsonFields.map((field) => [field, stringifyJson(rule[field])]))
    );
    setEditorError(null);
  }, [rule]);

  if (!rule) {
    return <section className="surface-panel empty-state">请选择一条规则查看详情</section>;
  }

  async function handleSave() {
    if (!rule) return;
    try {
      const payload: Partial<AbilityRule> = {};
      for (const field of jsonFields) {
        payload[field] = parseJsonDraft(drafts[field]);
      }
      await onUpdateRule(rule.id, payload);
      setEditorError(null);
    } catch (error) {
      setEditorError(error instanceof Error ? error.message : String(error));
    }
  }

  return (
    <section className="surface-panel ability-rule-detail">
      <div className="panel-heading">
        <div>
          <h2>{rule.rule_code}</h2>
          <span>{rule.rule_name} / {rule.rule_type} / v{rule.version || "1.0.0"}</span>
        </div>
        <button className="primary-button" type="button" onClick={() => void handleSave()}>
          保存 JSON 配置
        </button>
      </div>
      {editorError ? <pre className="error-detail error-detail--collapsed">{editorError}</pre> : null}
      <dl className="settings-list">
        <dt>状态</dt>
        <dd><StatusBadge value={rule.status} /></dd>
        <dt>来源</dt>
        <dd>{rule.source || "-"}</dd>
        <dt>置信度阈值</dt>
        <dd>{rule.confidence_threshold}</dd>
      </dl>
      <div className="ability-rule-json-grid">
        {jsonFields.map((field) => (
          <div className="ability-rule-json-editor" key={field}>
            <JsonCollapseBlock title={`查看 ${field}`} value={rule[field]} />
            <label>
              编辑 {field}
              <textarea
                value={drafts[field] || ""}
                onChange={(event) => setDrafts((current) => ({ ...current, [field]: event.target.value }))}
              />
            </label>
          </div>
        ))}
      </div>
    </section>
  );
}

function FailureSamplesView({
  samples,
  drafts,
  interventions
}: {
  samples: FailureSample[];
  drafts: RuleDraft[];
  interventions: HumanIntervention[];
}) {
  return (
    <section className="surface-panel">
      <div className="panel-heading">
        <h2>
          <FileWarning size={18} />
          失败样本
        </h2>
        <span>{samples.length} 条</span>
      </div>
      <DataTable
        columns={[
          { key: "type", title: "failureType", render: (sample) => sample.failure_type || "-" },
          { key: "step", title: "step", render: (sample) => sample.step_id ? `#${sample.step_id}` : "-" },
          { key: "shot", title: "screenshot", render: (sample) => sample.screenshot_path ? <img className="ability-thumb" src={fileUrl(sample.screenshot_path)} alt="失败截图" /> : "暂无截图" },
          { key: "recovery", title: "suggestedRecovery", render: (sample) => <RecoverySummary sample={sample} /> },
          { key: "draft", title: "规则草案", render: (sample) => draftCreated(sample, drafts) ? "已生成" : "未生成" },
          { key: "intervene", title: "人工介入", render: (sample) => interventionCreated(sample, interventions) ? "已介入" : "未介入" },
          { key: "status", title: "状态", render: (sample) => <StatusBadge value={sample.status} /> }
        ]}
        rows={samples}
        emptyText="暂无失败样本"
        getRowKey={(sample) => sample.id}
      />
    </section>
  );
}

function RecoverySummary({ sample }: { sample: FailureSample }) {
  const recovery = readRecovery(sample);
  if (recovery.length === 0) return <span>-</span>;
  return (
    <div className="ability-recovery-list">
      {recovery.slice(0, 3).map((item, index) => (
        <span key={`${item.code || item.label || index}`}>{item.label || item.code || String(item)}</span>
      ))}
      <JsonCollapseBlock title="查看恢复建议详情" value={recovery} />
    </div>
  );
}

function KnowledgeView({ knowledge }: { knowledge: AbilityKnowledge[] }) {
  return (
    <section className="surface-panel">
      <div className="panel-heading">
        <h2>
          <BookOpen size={18} />
          页面知识库
        </h2>
        <span>{knowledge.length} 条</span>
      </div>
      <DataTable
        columns={[
          { key: "id", title: "知识", render: (item) => `#${item.id}` },
          { key: "type", title: "类型", render: (item) => item.knowledge_type },
          { key: "target", title: "语义目标", render: (item) => item.semantic_target || "-" },
          { key: "intent", title: "业务意图", render: (item) => item.business_intent || "-" },
          { key: "locator", title: "成功定位", render: (item) => <JsonCollapseBlock title="查看 JSON" value={item.success_locator_json || {}} /> },
          { key: "status", title: "状态", render: (item) => <StatusBadge value={item.status} /> }
        ]}
        rows={knowledge}
        emptyText="暂无知识记录"
        getRowKey={(item) => item.id}
      />
    </section>
  );
}

function InterventionView({ interventions }: { interventions: HumanIntervention[] }) {
  return (
    <section className="surface-panel">
      <div className="panel-heading">
        <h2>
          <History size={18} />
          人工介入记录
        </h2>
        <span>{interventions.length} 条</span>
      </div>
      <DataTable
        columns={[
          { key: "id", title: "记录", render: (item) => `#${item.id}` },
          { key: "run", title: "运行", render: (item) => `#${item.run_id}` },
          { key: "instruction", title: "用户指令", render: (item) => item.user_instruction || "-" },
          { key: "plan", title: "计划", render: (item) => <JsonCollapseBlock title="查看计划" value={item.llm_plan_json || {}} /> },
          { key: "status", title: "状态", render: (item) => <StatusBadge value={item.status} /> }
        ]}
        rows={interventions}
        emptyText="暂无人工介入记录"
        getRowKey={(item) => item.id}
      />
    </section>
  );
}

function RuleDraftView({
  drafts,
  onEnableDraft
}: {
  drafts: RuleDraft[];
  onEnableDraft: (draftId: number) => Promise<void>;
}) {
  return (
    <section className="surface-panel">
      <div className="panel-heading">
        <h2>
          <Lightbulb size={18} />
          规则草案
        </h2>
        <span>{drafts.length} 条</span>
      </div>
      <DataTable
        columns={[
          { key: "name", title: "草案名称", render: (draft) => draft.rule_name },
          { key: "type", title: "类型", render: (draft) => draft.rule_type },
          { key: "content", title: "内容", render: (draft) => <JsonCollapseBlock title="查看 proposed_content" value={draft.proposed_content_json || {}} /> },
          { key: "status", title: "状态", render: (draft) => <StatusBadge value={draft.status} /> },
          {
            key: "action",
            title: "操作",
            render: (draft) => (
              <button
                className="secondary-button"
                type="button"
                disabled={draft.status === "active"}
                onClick={() => void onEnableDraft(draft.id)}
              >
                手动启用
              </button>
            )
          }
        ]}
        rows={drafts}
        emptyText="暂无规则草案"
        getRowKey={(draft) => draft.id}
      />
    </section>
  );
}

function PromptConfigView({ prompts, onReload }: { prompts: PromptInfo[]; onReload: () => Promise<void> }) {
  const [selectedPromptKey, setSelectedPromptKey] = useState("");
  const [search, setSearch] = useState("");
  const [fileFilter, setFileFilter] = useState("");
  const [preview, setPreview] = useState<PromptPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const files = Array.from(new Set(prompts.map((prompt) => prompt.file))).sort();
  const filtered = prompts.filter((prompt) => `${prompt.key} ${prompt.name} ${prompt.file}`.toLowerCase().includes(search.toLowerCase()) && (!fileFilter || prompt.file === fileFilter));
  const selected = prompts.find((prompt) => prompt.key === selectedPromptKey) || filtered[0] || null;

  async function handleReload() {
    setError(null);
    try {
      await reloadPrompts();
      await onReload();
      setPreview(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    }
  }

  async function handlePreview(prompt: PromptInfo) {
    setError(null);
    try {
      const variables = Object.fromEntries(prompt.variables.map((name) => [name, samplePromptVariable(name)]));
      setPreview(await previewPrompt(prompt.key, variables));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    }
  }

  return (
    <section className="surface-panel prompt-manager-panel">
      <div className="panel-heading">
        <h2>
          <WandSparkles size={18} />
          Prompt 配置
        </h2>
        <button className="secondary-button" type="button" onClick={() => void handleReload()}>
          <RefreshCw size={16} />
          重新加载 Prompt
        </button>
      </div>
      {error ? <pre className="error-detail error-detail--collapsed">{error}</pre> : null}
      <div className="prompt-toolbar">
        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索 prompt_key / 名称" />
        <select value={fileFilter} onChange={(event) => setFileFilter(event.target.value)}>
          <option value="">全部文件</option>
          {files.map((file) => <option key={file} value={file}>{file}</option>)}
        </select>
      </div>
      <div className="prompt-manager-grid">
        <div className="prompt-list">
          {filtered.map((prompt) => (
            <button
              className={selected?.key === prompt.key ? "prompt-list-item prompt-list-item--active" : "prompt-list-item"}
              key={prompt.key}
              type="button"
              onClick={() => {
                setSelectedPromptKey(prompt.key);
                setPreview(null);
              }}
            >
              <strong>{prompt.key}</strong>
              <span>{prompt.file}</span>
              <StatusBadge value={prompt.enabled ? "active" : "disabled"} />
            </button>
          ))}
        </div>
        <div className="prompt-detail">
          {selected ? (
            <>
              <div className="panel-heading">
                <div>
                  <h3>{selected.name}</h3>
                  <span>{selected.key} / v{selected.version} / {selected.file}</span>
                </div>
                <button className="ghost-button" type="button" onClick={() => void handlePreview(selected)}>预览渲染</button>
              </div>
              <dl className="settings-list">
                <dt>enabled</dt>
                <dd>{selected.enabled ? "true" : "false"}</dd>
                <dt>变量</dt>
                <dd>{selected.variables.join(", ") || "-"}</dd>
              </dl>
              <JsonCollapseBlock title="system prompt" value={selected.system} />
              <JsonCollapseBlock title="user prompt" value={selected.user} />
              {preview ? <JsonCollapseBlock title="渲染预览" value={preview} /> : null}
            </>
          ) : <div className="empty-state">没有匹配的 Prompt</div>}
        </div>
      </div>
    </section>
  );
}

function AbilityStatsView({ stats }: { stats: AbilityStats | null }) {
  if (!stats) return <section className="surface-panel empty-state">暂无统计数据</section>;
  return (
    <div className="page-stack">
      <section className="settings-grid">
        <StatCard icon={<ScrollText size={18} />} title="规则命中次数" value={sumValues(stats.ruleHitCountsByType)} detail={`${Object.keys(stats.ruleHitCountsByType).length} 类规则`} />
        <StatCard icon={<FileWarning size={18} />} title="失败类型分布" value={sumValues(stats.failureTypeDistribution)} detail={`${Object.keys(stats.failureTypeDistribution).length} 类失败`} />
        <StatCard icon={<History size={18} />} title="人工介入次数" value={stats.humanInterventionCount} detail="人工介入记录总数" />
        <StatCard icon={<Lightbulb size={18} />} title="规则草案数量" value={stats.ruleDraftCount} detail="待审核与已启用草案" />
        <StatCard icon={<Settings2 size={18} />} title="视觉兜底触发次数" value={stats.visionFallbackCount} detail="最近 Runtime Stream 粗略聚合" />
        <StatCard icon={<BarChart3 size={18} />} title="LLM 决策次数" value={stats.llmDecisionCount} detail="LLM 日志与运行消息聚合" />
      </section>
      <section className="ability-stat-grid">
        <div className="surface-panel">
          <div className="panel-heading">
            <h2>失败类型分布</h2>
          </div>
          <KeyValueList values={stats.failureTypeDistribution} />
        </div>
        <div className="surface-panel">
          <div className="panel-heading">
            <h2>规则命中分布</h2>
          </div>
          <KeyValueList values={stats.ruleHitCountsByType} />
        </div>
      </section>
    </div>
  );
}

function StatCard({ icon, title, value, detail }: { icon: ReactNode; title: string; value: number; detail: string }) {
  return (
    <article className="surface-panel ability-stat-card">
      <div className="panel-heading">
        <h2>{icon}{title}</h2>
      </div>
      <strong>{value}</strong>
      <span>{detail}</span>
    </article>
  );
}

function KeyValueList({ values }: { values: Record<string, number> }) {
  const entries = Object.entries(values).sort((a, b) => b[1] - a[1]);
  if (entries.length === 0) return <div className="empty-state">暂无数据</div>;
  return (
    <div className="ability-key-value-list">
      {entries.map(([key, value]) => (
        <div key={key}>
          <span>{key}</span>
          <strong>{value}</strong>
        </div>
      ))}
    </div>
  );
}

function fallbackOverview(rules: AbilityRule[]): AbilityOperationOverview[] {
  const categories: Array<[string, string, string[]]> = [
    ["login", "登录", ["login"]],
    ["global_interruption", "弹窗 / 中断页", ["global_interruption", "dialog_handler"]],
    ["navigation", "导航", ["navigation"]],
    ["query", "查询", ["query"]],
    ["table_detection", "表格识别", ["table_detection"]],
    ["table_row_action", "表格行操作", ["table_row_action"]],
    ["form_fill", "表单填写", ["form_fill", "form_control"]],
    ["dropdown", "下拉框", ["dropdown"]],
    ["date_picker", "日期", ["date_picker"]],
    ["org_selector", "组织机构", ["org_selector"]],
    ["person_selector", "人员选择", ["person_selector"]],
    ["tree_selector", "树选择", ["tree_selector"]],
    ["dialog_selector", "弹窗选择", ["dialog_selector"]],
    ["file_upload", "文件上传", ["file_upload"]],
    ["approval_workflow", "审批流程", ["approval_workflow"]],
    ["assertion", "断言验证", ["assertion"]]
  ];
  return categories.map(([key, label, ruleTypes]) => {
    const matched = rules.filter((rule) => ruleTypes.includes(rule.rule_type));
    return { key, label, ruleTypes: [...ruleTypes], ruleCount: matched.length, activeCount: matched.filter((rule) => rule.status === "active").length, recentHitCount: 0, recentFailureCount: 0 };
  });
}

function stringifyJson(value: unknown): string {
  return value == null ? "" : JSON.stringify(value, null, 2);
}

function parseJsonDraft(value: string | undefined): Record<string, unknown> | null {
  if (!value || !value.trim()) return null;
  const parsed = JSON.parse(value) as unknown;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("JSON 配置必须是对象。");
  }
  return parsed as Record<string, unknown>;
}

function readRecovery(sample: FailureSample): Array<Record<string, string>> {
  const analysisRecovery = sample.ai_analysis_json?.suggestedRecovery;
  if (Array.isArray(analysisRecovery)) return analysisRecovery as Array<Record<string, string>>;
  const ruleRecovery = sample.suggested_rule_json?.suggestedRecovery;
  if (Array.isArray(ruleRecovery)) return ruleRecovery as Array<Record<string, string>>;
  return [];
}

function draftCreated(sample: FailureSample, drafts: RuleDraft[]): boolean {
  return drafts.some((draft) => draft.source_type === "failure_sample" && draft.source_id === sample.id);
}

function interventionCreated(sample: FailureSample, interventions: HumanIntervention[]): boolean {
  return interventions.some((item) => item.run_id === sample.run_id && item.step_id === sample.step_id);
}

function sumValues(values: Record<string, number>): number {
  return Object.values(values).reduce((sum, value) => sum + value, 0);
}

function samplePromptVariable(name: string): unknown {
  if (name.endsWith("_json") || name.includes("context") || name.includes("data") || name.includes("systems")) return {};
  if (name === "allowed_actions") return "open_url, navigate_path, business_goal, assert_text_exists";
  if (name === "instruction") return "登录系统，进入工作台/我的待办，确认页面存在我的待办。";
  if (name === "path_segments") return ["工作台", "我的待办"];
  if (name === "target") return "工作台/我的待办";
  return "";
}
