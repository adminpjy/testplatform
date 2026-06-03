import { BarChart3, BookOpen, FileWarning, History, Lightbulb, Plus, RefreshCw, Save, ScrollText, Settings2, Trash2, WandSparkles } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import {
  deleteAbilityKnowledge,
  deleteAbilityRule,
  deleteFailureSample,
  deleteHumanIntervention,
  deletePrompt,
  deleteRuleDraft,
  enableRuleDraft,
  getAbilityKnowledge,
  getAbilityRules,
  getAbilityStats,
  getFailureSamples,
  generateFailureSolutionFromSample,
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
import {
  labelBoolean,
  labelConfigValue,
  labelFailureType,
  labelKnowledgeType,
  labelPromptVariable,
  labelRisk,
  labelRuleConfigKey,
  labelRuleSource,
  labelRuleType,
  labelRuleTypes,
  parseConfigDisplayValue,
  ruleTypeLabels
} from "../utils/displayLabels";

type AbilityTab = "overview" | "rules" | "knowledge" | "failures" | "interventions" | "drafts" | "prompts" | "stats";
const PAGE_SIZE = 10;

const tabs: Array<{ id: AbilityTab; label: string }> = [
  { id: "overview", label: "操作能力总览" },
  { id: "rules", label: "规则库" },
  { id: "knowledge", label: "页面知识库" },
  { id: "failures", label: "失败样本" },
  { id: "interventions", label: "人工介入记录" },
  { id: "drafts", label: "规则草案" },
  { id: "prompts", label: "提示词配置" },
  { id: "stats", label: "能力统计" }
];

const jsonFieldDefs = [
  { field: "match_config_json", label: "匹配条件" },
  { field: "action_config_json", label: "执行动作" },
  { field: "success_criteria_json", label: "成功标准" },
  { field: "fallback_strategies_json", label: "兜底策略" },
  { field: "failure_patterns_json", label: "失败特征" },
  { field: "recovery_strategies_json", label: "恢复策略" }
] as const;

type RuleJsonField = (typeof jsonFieldDefs)[number]["field"];
type RuleConfigRow = { id: string; key: string; value: string };
type RuleBasicDraft = {
  rule_name: string;
  rule_type: string;
  intent: string;
  status: string;
  priority: string;
  risk_level: string;
  confidence_threshold: string;
  production_enabled: boolean;
  auto_handle: boolean;
  requires_human_confirmation: boolean;
};

const ruleConfigKeyOptionsByField: Record<RuleJsonField, string[]> = {
  match_config_json: ["trigger_phrases", "positive_actions", "negative_actions", "target_keywords", "blockedAuthStates", "negativeTextHints", "minimumConfidence"],
  action_config_json: ["business_target", "requires_human", "uses_vision", "max_retry", "fillUsername", "fillPassword", "clickSubmit", "redactPassword", "detectMainMenu", "detectHomePage", "detectUserArea", "navigation_mode", "pathSeparator", "successSignals", "failureSignals", "detectPagination", "detectHeaders", "detectRows", "captureEvidence", "rankCandidates", "preferNearestLabel", "verifyEditable", "openDialog", "queryTarget", "selectTableRow", "confirm", "verifyBackfill"],
  success_criteria_json: ["criteria", "successSignals", "pageChangeEvidence", "alreadyOnTargetCheck"],
  fallback_strategies_json: ["strategies"],
  failure_patterns_json: ["failureSignals", "negativeTextHints"],
  recovery_strategies_json: ["strategies"]
};

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
  const [pages, setPages] = useState<Record<AbilityTab, number>>({
    overview: 1,
    rules: 1,
    knowledge: 1,
    failures: 1,
    interventions: 1,
    drafts: 1,
    prompts: 1,
    stats: 1
  });
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

  async function handleDelete(action: () => Promise<void>) {
    setError(null);
    try {
      await action();
      await loadData();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    }
  }

  async function handleGenerateFailureSolution(sampleId: number) {
    setError(null);
    try {
      await generateFailureSolutionFromSample(sampleId);
      await loadData();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    }
  }

  async function handleConfirmedDelete(message: string, action: () => Promise<void>) {
    if (!window.confirm(message)) return;
    await handleDelete(action);
  }

  function setPage(tab: AbilityTab, page: number) {
    setPages((current) => ({ ...current, [tab]: Math.max(1, page) }));
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
      {activeTab === "rules" ? <RulesView rules={rules} page={pages.rules} selectedRule={selectedRule} onPage={(page) => setPage("rules", page)} onSelectRule={setSelectedRule} onUpdateRule={handleUpdateRule} onDeleteRule={(rule) => handleConfirmedDelete(`确认删除规则“${rule.rule_name}”？删除后会归档停用，不会物理删除。`, () => deleteAbilityRule(rule.id))} /> : null}
      {activeTab === "knowledge" ? <KnowledgeView knowledge={knowledge} page={pages.knowledge} onPage={(page) => setPage("knowledge", page)} onDeleteKnowledge={(id) => handleDelete(() => deleteAbilityKnowledge(id))} /> : null}
      {activeTab === "failures" ? <FailureSamplesView samples={failureSamples} page={pages.failures} drafts={ruleDrafts} interventions={interventions} onPage={(page) => setPage("failures", page)} onGenerateSolution={handleGenerateFailureSolution} onDeleteSample={(id) => handleDelete(() => deleteFailureSample(id))} /> : null}
      {activeTab === "interventions" ? <InterventionView interventions={interventions} page={pages.interventions} onPage={(page) => setPage("interventions", page)} onDeleteIntervention={(id) => handleDelete(() => deleteHumanIntervention(id))} /> : null}
      {activeTab === "drafts" ? <RuleDraftView drafts={ruleDrafts} page={pages.drafts} onPage={(page) => setPage("drafts", page)} onEnableDraft={handleEnableDraft} onDeleteDraft={(id) => handleDelete(() => deleteRuleDraft(id))} /> : null}
      {activeTab === "prompts" ? <PromptConfigView prompts={prompts} page={pages.prompts} onPage={(page) => setPage("prompts", page)} onReload={loadData} /> : null}
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
            <span>{labelRuleTypes(item.ruleTypes)}</span>
          </div>
          <dl>
            <div>
              <dt>规则</dt>
              <dd>{item.ruleCount}</dd>
            </div>
            <div>
              <dt>启用</dt>
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
  page,
  selectedRule,
  onPage,
  onSelectRule,
  onUpdateRule,
  onDeleteRule
}: {
  rules: AbilityRule[];
  page: number;
  selectedRule: AbilityRule | null;
  onPage: (page: number) => void;
  onSelectRule: (rule: AbilityRule) => void;
  onUpdateRule: (ruleId: number, payload: Partial<AbilityRule>) => Promise<void>;
  onDeleteRule: (rule: AbilityRule) => Promise<void>;
}) {
  const ruleTypes = useMemo(() => Array.from(new Set(rules.map((rule) => rule.rule_type))).sort(), [rules]);
  const [ruleTypeFilter, setRuleTypeFilter] = useState("");
  const filteredRules = rules.filter((rule) => !ruleTypeFilter || rule.rule_type === ruleTypeFilter);
  const pagedRules = pageItems(filteredRules, page);
  return (
    <div className="ability-rules-layout">
      <section className="surface-panel ability-rules-list">
        <div className="panel-heading ability-rules-toolbar">
          <h2>
            <ScrollText size={18} />
            规则库
          </h2>
          <select className="ability-rule-type-filter" value={ruleTypeFilter} onChange={(event) => setRuleTypeFilter(event.target.value)}>
            <option value="">全部规则类型</option>
            {ruleTypes.map((type) => (
              <option key={type} value={type}>
                {labelRuleType(type)}
              </option>
            ))}
          </select>
        </div>
        <DataTable
          columns={[
            { key: "code", title: "规则编码", render: (rule) => <button className="link-button" type="button" onClick={() => onSelectRule(rule)}>{rule.rule_code}</button> },
            { key: "name", title: "名称", render: (rule) => rule.rule_name },
            { key: "type", title: "类型", render: (rule) => labelRuleType(rule.rule_type) },
            { key: "intent", title: "意图", render: (rule) => rule.intent || "-" },
            { key: "risk", title: "风险", render: (rule) => labelRisk(rule.risk_level) },
            { key: "status", title: "状态", render: (rule) => <StatusBadge value={rule.status} /> },
            {
              key: "actions",
              title: "操作",
              render: (rule) => <button className="table-link-button" type="button" onClick={() => void onDeleteRule(rule)}>删除</button>
            }
          ]}
          rows={pagedRules}
          emptyText="暂无规则"
          getRowKey={(rule) => rule.id}
        />
        <LocalPager page={page} total={filteredRules.length} onPage={onPage} />
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
  const [basicDraft, setBasicDraft] = useState<RuleBasicDraft>(emptyRuleBasicDraft());
  const [configDrafts, setConfigDrafts] = useState<Record<RuleJsonField, RuleConfigRow[]>>(emptyRuleConfigDrafts);
  const [editorError, setEditorError] = useState<string | null>(null);

  useEffect(() => {
    if (!rule) {
      setBasicDraft(emptyRuleBasicDraft());
      setConfigDrafts(emptyRuleConfigDrafts());
      return;
    }
    setBasicDraft(ruleToBasicDraft(rule));
    setConfigDrafts(ruleToConfigDrafts(rule));
    setEditorError(null);
  }, [rule]);

  if (!rule) {
    return <section className="surface-panel empty-state">请选择一条规则查看详情</section>;
  }

  function updateBasic<K extends keyof RuleBasicDraft>(field: K, value: RuleBasicDraft[K]) {
    setBasicDraft((current) => ({ ...current, [field]: value }));
  }

  function addConfigRow(field: RuleJsonField) {
    setConfigDrafts((current) => ({
      ...current,
      [field]: [...(current[field] || []), { id: makeRuleConfigRowId(), key: "", value: "" }]
    }));
  }

  function updateConfigRow(field: RuleJsonField, rowId: string, patch: Partial<RuleConfigRow>) {
    setConfigDrafts((current) => ({
      ...current,
      [field]: (current[field] || []).map((row) => (row.id === rowId ? { ...row, ...patch } : row))
    }));
  }

  function removeConfigRow(field: RuleJsonField, rowId: string) {
    setConfigDrafts((current) => ({
      ...current,
      [field]: (current[field] || []).filter((row) => row.id !== rowId)
    }));
  }

  async function handleSave() {
    if (!rule) return;
    try {
      const priority = Number.parseInt(basicDraft.priority, 10);
      const confidenceThreshold = Number(basicDraft.confidence_threshold);
      if (!basicDraft.rule_name.trim()) throw new Error("规则名称不能为空。");
      if (!basicDraft.rule_type.trim()) throw new Error("规则类型不能为空。");
      if (!Number.isFinite(priority)) throw new Error("优先级必须是数字。");
      if (!Number.isFinite(confidenceThreshold) || confidenceThreshold < 0 || confidenceThreshold > 1) {
        throw new Error("置信度阈值必须在 0 到 1 之间。");
      }
      const payload: Partial<AbilityRule> = {
        rule_name: basicDraft.rule_name.trim(),
        rule_type: basicDraft.rule_type.trim(),
        intent: basicDraft.intent.trim() || null,
        status: basicDraft.status,
        priority,
        risk_level: basicDraft.risk_level.trim() || "medium",
        confidence_threshold: confidenceThreshold,
        production_enabled: basicDraft.production_enabled,
        auto_handle: basicDraft.auto_handle,
        requires_human_confirmation: basicDraft.requires_human_confirmation
      };
      for (const definition of jsonFieldDefs) {
        payload[definition.field] = rowsToRuleConfig(configDrafts[definition.field] || [], definition.label);
      }
      await onUpdateRule(rule.id, payload);
      setEditorError(null);
    } catch (error) {
      setEditorError(error instanceof Error ? error.message : String(error));
    }
  }

  return (
    <section className="surface-panel ability-rule-detail">
      <div className="panel-heading rule-detail-heading">
        <div>
          <h2>{rule.rule_code}</h2>
          <span>{rule.rule_name} / {labelRuleType(rule.rule_type)} / 版本 {rule.version || "1.0.0"}</span>
        </div>
        <button className="primary-button" type="button" onClick={() => void handleSave()}>
          <Save size={16} />
          保存规则
        </button>
      </div>
      {editorError ? <pre className="error-detail error-detail--collapsed">{editorError}</pre> : null}
      <div className="rule-editor-section">
        <div className="rule-editor-section__heading">
          <h3>基础信息</h3>
          <StatusBadge value={basicDraft.status} />
        </div>
        <div className="rule-basic-grid">
          <label>
            <span>规则编码</span>
            <input value={rule.rule_code} disabled />
          </label>
          <label>
            <span>规则名称</span>
            <input value={basicDraft.rule_name} onChange={(event) => updateBasic("rule_name", event.target.value)} />
          </label>
          <label>
            <span>规则类型</span>
            <select value={basicDraft.rule_type} onChange={(event) => updateBasic("rule_type", event.target.value)}>
              {ruleTypeOptions(basicDraft.rule_type).map((type) => (
                <option key={type} value={type}>{labelRuleType(type)}</option>
              ))}
            </select>
          </label>
          <label>
            <span>状态</span>
            <select value={basicDraft.status} onChange={(event) => updateBasic("status", event.target.value)}>
              <option value="active">启用</option>
              <option value="disabled">停用</option>
              <option value="draft">草稿</option>
              <option value="archived">归档</option>
            </select>
          </label>
          <label>
            <span>优先级</span>
            <input value={basicDraft.priority} inputMode="numeric" onChange={(event) => updateBasic("priority", event.target.value)} />
          </label>
          <label>
            <span>风险等级</span>
            <select value={basicDraft.risk_level} onChange={(event) => updateBasic("risk_level", event.target.value)}>
              <option value="low">低</option>
              <option value="medium">中</option>
              <option value="high">高</option>
            </select>
          </label>
          <label>
            <span>置信度阈值</span>
            <input value={basicDraft.confidence_threshold} inputMode="decimal" onChange={(event) => updateBasic("confidence_threshold", event.target.value)} />
          </label>
          <label>
            <span>来源</span>
            <input value={labelRuleSource(rule.source)} disabled />
          </label>
          <label className="rule-basic-grid__wide">
            <span>业务意图</span>
            <textarea rows={3} value={basicDraft.intent} onChange={(event) => updateBasic("intent", event.target.value)} />
          </label>
          <label className="rule-checkbox-field">
            <input type="checkbox" checked={basicDraft.production_enabled} onChange={(event) => updateBasic("production_enabled", event.target.checked)} />
            <span>生产启用</span>
          </label>
          <label className="rule-checkbox-field">
            <input type="checkbox" checked={basicDraft.auto_handle} onChange={(event) => updateBasic("auto_handle", event.target.checked)} />
            <span>自动处理</span>
          </label>
          <label className="rule-checkbox-field">
            <input type="checkbox" checked={basicDraft.requires_human_confirmation} onChange={(event) => updateBasic("requires_human_confirmation", event.target.checked)} />
            <span>需要人工确认</span>
          </label>
        </div>
      </div>
      <div className="rule-config-sections">
        {jsonFieldDefs.map((definition) => {
          const rows = configDrafts[definition.field] || [];
          return (
            <section className="rule-config-card" key={definition.field}>
              <div className="rule-config-card__header">
                <h3>{definition.label}</h3>
                <button className="secondary-button" type="button" onClick={() => addConfigRow(definition.field)}>
                  <Plus size={16} />
                  添加项
                </button>
              </div>
              {rows.length > 0 ? (
                <div className="rule-kv-list">
                  {rows.map((row) => (
                    <div className="rule-kv-row" key={row.id}>
                      <select value={row.key} onChange={(event) => updateConfigRow(definition.field, row.id, { key: event.target.value })}>
                        <option value="">请选择配置项</option>
                        {ruleConfigKeyOptions(definition.field, row.key).map((key) => (
                          <option key={key} value={key}>{labelRuleConfigKey(key)}</option>
                        ))}
                      </select>
                      <textarea rows={2} value={row.value} placeholder="配置值" onChange={(event) => updateConfigRow(definition.field, row.id, { value: event.target.value })} />
                      <button className="icon-button" type="button" title="删除配置项" aria-label="删除配置项" onClick={() => removeConfigRow(definition.field, row.id)}>
                        <Trash2 size={16} />
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-state empty-state--compact">暂无配置项</div>
              )}
              <JsonCollapseBlock title={`查看原始 ${definition.label}`} value={rule[definition.field] || {}} />
            </section>
          );
        })}
      </div>
    </section>
  );
}

function FailureSamplesView({
  samples,
  page,
  drafts,
  interventions,
  onPage,
  onGenerateSolution,
  onDeleteSample
}: {
  samples: FailureSample[];
  page: number;
  drafts: RuleDraft[];
  interventions: HumanIntervention[];
  onPage: (page: number) => void;
  onGenerateSolution: (sampleId: number) => Promise<void>;
  onDeleteSample: (sampleId: number) => Promise<void>;
}) {
  const pagedSamples = pageItems(samples, page);
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
          { key: "type", title: "失败类型", render: (sample) => labelFailureType(sample.failure_type) },
          { key: "step", title: "步骤", render: (sample) => sample.step_id ? `#${sample.step_id}` : "-" },
          { key: "shot", title: "截图", render: (sample) => sample.screenshot_path ? <img className="ability-thumb" src={fileUrl(sample.screenshot_path)} alt="失败截图" /> : "暂无截图" },
          { key: "recovery", title: "建议恢复方案", render: (sample) => <RecoverySummary sample={sample} /> },
          { key: "draft", title: "规则草案", render: (sample) => draftCreated(sample, drafts) ? "已生成" : "未生成" },
          { key: "intervene", title: "人工介入", render: (sample) => interventionCreated(sample, interventions) ? "已介入" : "未介入" },
          { key: "status", title: "状态", render: (sample) => <StatusBadge value={sample.status} /> },
          {
            key: "actions",
            title: "操作",
            render: (sample) => (
              <div className="table-actions">
                <button className="table-link-button" type="button" onClick={() => void onGenerateSolution(sample.id)}>生成方案</button>
                <a className="table-link-button" href="#failure-samples">打开工作台</a>
                <button className="table-link-button" type="button" onClick={() => void onDeleteSample(sample.id)}>删除</button>
              </div>
            )
          }
        ]}
        rows={pagedSamples}
        emptyText="暂无失败样本"
        getRowKey={(sample) => sample.id}
      />
      <LocalPager page={page} total={samples.length} onPage={onPage} />
    </section>
  );
}

function RecoverySummary({ sample }: { sample: FailureSample }) {
  const recovery = readRecovery(sample);
  if (recovery.length === 0) return <span>-</span>;
  return (
    <div className="ability-recovery-list">
      {recovery.slice(0, 3).map((item, index) => (
        <span key={`${item.code || item.label || index}`}>{item.label || labelConfigValue("strategies", item.code || String(item))}</span>
      ))}
      <JsonCollapseBlock title="查看恢复建议详情" value={recovery} />
    </div>
  );
}

function KnowledgeView({
  knowledge,
  page,
  onPage,
  onDeleteKnowledge
}: {
  knowledge: AbilityKnowledge[];
  page: number;
  onPage: (page: number) => void;
  onDeleteKnowledge: (knowledgeId: number) => Promise<void>;
}) {
  const pagedKnowledge = pageItems(knowledge, page);
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
          { key: "type", title: "类型", render: (item) => labelKnowledgeType(item.knowledge_type) },
          { key: "target", title: "语义目标", render: (item) => item.semantic_target || "-" },
          { key: "intent", title: "业务意图", render: (item) => item.business_intent || "-" },
          { key: "locator", title: "成功定位", render: (item) => <JsonCollapseBlock title="查看定位数据" value={item.success_locator_json || {}} /> },
          { key: "status", title: "状态", render: (item) => <StatusBadge value={item.status} /> },
          { key: "actions", title: "操作", render: (item) => <button className="table-link-button" type="button" onClick={() => void onDeleteKnowledge(item.id)}>删除</button> }
        ]}
        rows={pagedKnowledge}
        emptyText="暂无知识记录"
        getRowKey={(item) => item.id}
      />
      <LocalPager page={page} total={knowledge.length} onPage={onPage} />
    </section>
  );
}

function InterventionView({
  interventions,
  page,
  onPage,
  onDeleteIntervention
}: {
  interventions: HumanIntervention[];
  page: number;
  onPage: (page: number) => void;
  onDeleteIntervention: (interventionId: number) => Promise<void>;
}) {
  const pagedInterventions = pageItems(interventions, page);
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
          { key: "status", title: "状态", render: (item) => <StatusBadge value={item.status} /> },
          { key: "actions", title: "操作", render: (item) => <button className="table-link-button" type="button" onClick={() => void onDeleteIntervention(item.id)}>删除</button> }
        ]}
        rows={pagedInterventions}
        emptyText="暂无人工介入记录"
        getRowKey={(item) => item.id}
      />
      <LocalPager page={page} total={interventions.length} onPage={onPage} />
    </section>
  );
}

function RuleDraftView({
  drafts,
  page,
  onPage,
  onEnableDraft,
  onDeleteDraft
}: {
  drafts: RuleDraft[];
  page: number;
  onPage: (page: number) => void;
  onEnableDraft: (draftId: number) => Promise<void>;
  onDeleteDraft: (draftId: number) => Promise<void>;
}) {
  const pagedDrafts = pageItems(drafts, page);
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
          { key: "type", title: "类型", render: (draft) => labelRuleType(draft.rule_type) },
          { key: "content", title: "内容", render: (draft) => <JsonCollapseBlock title="查看草案内容" value={draft.proposed_content_json || {}} /> },
          { key: "status", title: "状态", render: (draft) => <StatusBadge value={draft.status} /> },
          {
            key: "action",
            title: "操作",
            render: (draft) => (
              <div className="table-actions">
                <button
                  className="secondary-button"
                  type="button"
                  disabled={draft.status === "active"}
                  onClick={() => void onEnableDraft(draft.id)}
                >
                  手动启用
                </button>
                <button className="table-link-button" type="button" onClick={() => void onDeleteDraft(draft.id)}>
                  删除
                </button>
              </div>
            )
          }
        ]}
        rows={pagedDrafts}
        emptyText="暂无规则草案"
        getRowKey={(draft) => draft.id}
      />
      <LocalPager page={page} total={drafts.length} onPage={onPage} />
    </section>
  );
}

function PromptConfigView({ prompts, page, onPage, onReload }: { prompts: PromptInfo[]; page: number; onPage: (page: number) => void; onReload: () => Promise<void> }) {
  const [selectedPromptKey, setSelectedPromptKey] = useState("");
  const [search, setSearch] = useState("");
  const [fileFilter, setFileFilter] = useState("");
  const [preview, setPreview] = useState<PromptPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const files = Array.from(new Set(prompts.map((prompt) => prompt.file))).sort();
  const filtered = prompts.filter((prompt) => `${prompt.key} ${prompt.name} ${prompt.file}`.toLowerCase().includes(search.toLowerCase()) && (!fileFilter || prompt.file === fileFilter));
  const selected = prompts.find((prompt) => prompt.key === selectedPromptKey) || filtered[0] || null;
  const pagedPrompts = pageItems(filtered, page);

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

  async function handleDeletePrompt(prompt: PromptInfo) {
    if (!window.confirm(`确认删除“${prompt.name}”？`)) return;
    setError(null);
    try {
      await deletePrompt(prompt.key);
      await onReload();
      setPreview(null);
      setSelectedPromptKey("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    }
  }

  return (
    <section className="surface-panel prompt-manager-panel">
      <div className="panel-heading">
        <h2>
          <WandSparkles size={18} />
          提示词配置
        </h2>
        <button className="secondary-button" type="button" onClick={() => void handleReload()}>
          <RefreshCw size={16} />
          重新加载提示词
        </button>
      </div>
      {error ? <pre className="error-detail error-detail--collapsed">{error}</pre> : null}
      <div className="prompt-toolbar">
        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索提示词编码或名称" />
        <select value={fileFilter} onChange={(event) => setFileFilter(event.target.value)}>
          <option value="">全部文件</option>
          {files.map((file) => <option key={file} value={file}>{file}</option>)}
        </select>
      </div>
      <div className="prompt-manager-grid">
        <div className="prompt-list">
          {pagedPrompts.map((prompt) => (
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
          <LocalPager page={page} total={filtered.length} onPage={onPage} />
        </div>
        <div className="prompt-detail">
          {selected ? (
            <>
              <div className="panel-heading">
                <div>
                  <h3>{selected.name}</h3>
                  <span>{selected.name} / 版本 {selected.version} / {selected.file}</span>
                </div>
                <div className="table-actions">
                  <button className="ghost-button" type="button" onClick={() => void handlePreview(selected)}>预览渲染</button>
                  <button className="table-link-button" type="button" onClick={() => void handleDeletePrompt(selected)}>删除</button>
                </div>
              </div>
              <dl className="settings-list">
                <dt>是否启用</dt>
                <dd>{labelBoolean(selected.enabled)}</dd>
                <dt>变量</dt>
                <dd>{selected.variables.map(labelPromptVariable).join("，") || "-"}</dd>
              </dl>
              <JsonCollapseBlock title="系统提示词" value={selected.system} />
              <JsonCollapseBlock title="用户提示词" value={selected.user} />
              {preview ? <JsonCollapseBlock title="渲染预览" value={preview} /> : null}
            </>
          ) : <div className="empty-state">没有匹配的提示词</div>}
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
        <StatCard icon={<Settings2 size={18} />} title="视觉兜底触发次数" value={stats.visionFallbackCount} detail="最近运行消息粗略聚合" />
        <StatCard icon={<BarChart3 size={18} />} title="大模型决策次数" value={stats.llmDecisionCount} detail="大模型日志与运行消息聚合" />
      </section>
      <section className="ability-stat-grid">
        <div className="surface-panel">
          <div className="panel-heading">
            <h2>失败类型分布</h2>
          </div>
          <KeyValueList values={stats.failureTypeDistribution} labeler={labelFailureType} />
        </div>
        <div className="surface-panel">
          <div className="panel-heading">
            <h2>规则命中分布</h2>
          </div>
          <KeyValueList values={stats.ruleHitCountsByType} labeler={labelRuleType} />
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

function KeyValueList({ values, labeler }: { values: Record<string, number>; labeler?: (value: string) => string }) {
  const entries = Object.entries(values).sort((a, b) => b[1] - a[1]);
  if (entries.length === 0) return <div className="empty-state">暂无数据</div>;
  return (
    <div className="ability-key-value-list">
      {entries.map(([key, value]) => (
        <div key={key}>
          <span>{labeler ? labeler(key) : key}</span>
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

function emptyRuleBasicDraft(): RuleBasicDraft {
  return {
    rule_name: "",
    rule_type: "",
    intent: "",
    status: "draft",
    priority: "100",
    risk_level: "medium",
    confidence_threshold: "0.8",
    production_enabled: false,
    auto_handle: false,
    requires_human_confirmation: false
  };
}

function ruleToBasicDraft(rule: AbilityRule): RuleBasicDraft {
  return {
    rule_name: rule.rule_name || "",
    rule_type: rule.rule_type || "",
    intent: rule.intent || "",
    status: rule.status || "draft",
    priority: String(rule.priority ?? 100),
    risk_level: rule.risk_level || "medium",
    confidence_threshold: String(rule.confidence_threshold ?? 0.8),
    production_enabled: Boolean(rule.production_enabled),
    auto_handle: Boolean(rule.auto_handle),
    requires_human_confirmation: Boolean(rule.requires_human_confirmation)
  };
}

function emptyRuleConfigDrafts(): Record<RuleJsonField, RuleConfigRow[]> {
  const drafts = {} as Record<RuleJsonField, RuleConfigRow[]>;
  for (const definition of jsonFieldDefs) {
    drafts[definition.field] = [];
  }
  return drafts;
}

function ruleToConfigDrafts(rule: AbilityRule): Record<RuleJsonField, RuleConfigRow[]> {
  const drafts = {} as Record<RuleJsonField, RuleConfigRow[]>;
  for (const definition of jsonFieldDefs) {
    drafts[definition.field] = objectToRuleConfigRows(rule[definition.field]);
  }
  return drafts;
}

function objectToRuleConfigRows(value: Record<string, unknown> | null): RuleConfigRow[] {
  if (!value || typeof value !== "object" || Array.isArray(value)) return [];
  return Object.entries(value).map(([key, item], index) => ({
    id: `${key || "row"}-${index}-${makeRuleConfigRowId()}`,
    key,
    value: labelConfigValue(key, item)
  }));
}

function rowsToRuleConfig(rows: RuleConfigRow[], label: string): Record<string, unknown> | null {
  const result: Record<string, unknown> = {};
  const seen = new Set<string>();
  for (const row of rows) {
    const key = row.key.trim();
    const value = row.value.trim();
    if (!key && !value) continue;
    if (!key) throw new Error(`${label}存在空配置项。`);
    if (seen.has(key)) throw new Error(`${label}存在重复配置项：${key}`);
    seen.add(key);
    result[key] = parseConfigDisplayValue(key, row.value);
  }
  return Object.keys(result).length > 0 ? result : null;
}

function makeRuleConfigRowId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function ruleTypeOptions(current: string): string[] {
  const options = Object.keys(ruleTypeLabels);
  return current && !options.includes(current) ? [current, ...options] : options;
}

function ruleConfigKeyOptions(field: RuleJsonField, current: string): string[] {
  const options = ruleConfigKeyOptionsByField[field] || [];
  return current && !options.includes(current) ? [current, ...options] : options;
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

function pageItems<T>(items: T[], page: number): T[] {
  const safePage = Math.max(1, page);
  return items.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);
}

function LocalPager({ page, total, onPage }: { page: number; total: number; onPage: (page: number) => void }) {
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  return (
    <div className="pagination-bar">
      <span>
        第 {Math.min(page, totalPages)} / {totalPages} 页，共 {total} 条
      </span>
      <div>
        <button className="secondary-button" type="button" disabled={page <= 1} onClick={() => onPage(page - 1)}>上一页</button>
        <button className="secondary-button" type="button" disabled={page >= totalPages} onClick={() => onPage(page + 1)}>下一页</button>
      </div>
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
