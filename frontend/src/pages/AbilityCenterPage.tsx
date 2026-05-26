import { BookOpen, FileWarning, FlaskConical, History, Lightbulb, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import { enableRuleDraft, getAbilityKnowledge, getAbilityRules, getFailureSamples, getHumanInterventions, getRuleDrafts } from "../api/platform";
import { DataTable } from "../components/DataTable";
import { StatusBadge } from "../components/StatusBadge";
import type { AbilityKnowledge, AbilityRule, FailureSample, HumanIntervention, RuleDraft } from "../types/platform";

type AbilityTab = "rules" | "knowledge" | "failures" | "interventions" | "drafts";

const tabs: Array<{ id: AbilityTab; label: string }> = [
  { id: "rules", label: "基础规则库" },
  { id: "knowledge", label: "页面知识库" },
  { id: "failures", label: "失败样本" },
  { id: "interventions", label: "人工介入记录" },
  { id: "drafts", label: "规则草案" }
];

export function AbilityCenterPage() {
  const [activeTab, setActiveTab] = useState<AbilityTab>("rules");
  const [rules, setRules] = useState<AbilityRule[]>([]);
  const [knowledge, setKnowledge] = useState<AbilityKnowledge[]>([]);
  const [failureSamples, setFailureSamples] = useState<FailureSample[]>([]);
  const [interventions, setInterventions] = useState<HumanIntervention[]>([]);
  const [ruleDrafts, setRuleDrafts] = useState<RuleDraft[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [ruleList, knowledgeList, sampleList, interventionList, draftList] = await Promise.all([
        getAbilityRules(),
        getAbilityKnowledge(),
        getFailureSamples(),
        getHumanInterventions(),
        getRuleDrafts()
      ]);
      setRules(ruleList);
      setKnowledge(knowledgeList);
      setFailureSamples(sampleList);
      setInterventions(interventionList);
      setRuleDrafts(draftList);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    } finally {
      setLoading(false);
    }
  }

  const groupedRules = useMemo(() => {
    return rules.reduce<Record<string, AbilityRule[]>>((groups, rule) => {
      groups[rule.rule_type] = groups[rule.rule_type] || [];
      groups[rule.rule_type].push(rule);
      return groups;
    }, {});
  }, [rules]);

  async function handleEnableDraft(draftId: number) {
    setError(null);
    try {
      await enableRuleDraft(draftId);
      await loadData();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    }
  }

  return (
    <div className="page-stack">
      <section className="surface-panel">
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

      {activeTab === "rules" ? <RulesView groupedRules={groupedRules} /> : null}
      {activeTab === "knowledge" ? (
        <KnowledgeView knowledge={knowledge} />
      ) : null}
      {activeTab === "failures" ? <FailureMiniView samples={failureSamples} /> : null}
      {activeTab === "interventions" ? <InterventionView interventions={interventions} /> : null}
      {activeTab === "drafts" ? <RuleDraftView drafts={ruleDrafts} onEnableDraft={handleEnableDraft} /> : null}
    </div>
  );
}

function RulesView({ groupedRules }: { groupedRules: Record<string, AbilityRule[]> }) {
  const entries = Object.entries(groupedRules).sort(([left], [right]) => left.localeCompare(right));
  return (
    <div className="ability-rule-grid">
      {entries.map(([ruleType, rules]) => (
        <section className="surface-panel" key={ruleType}>
          <div className="panel-heading">
            <h2>{ruleType}</h2>
            <span>{rules.length} 条</span>
          </div>
          <DataTable
            columns={[
              { key: "code", title: "规则编码", render: (rule) => <strong>{rule.rule_code}</strong> },
              { key: "name", title: "名称", render: (rule) => rule.rule_name },
              { key: "risk", title: "风险", render: (rule) => rule.risk_level },
              { key: "status", title: "状态", render: (rule) => <StatusBadge value={rule.status} /> }
            ]}
            rows={rules}
            emptyText="暂无规则"
            getRowKey={(rule) => rule.id}
          />
        </section>
      ))}
    </div>
  );
}

function FailureMiniView({ samples }: { samples: FailureSample[] }) {
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
          { key: "id", title: "样本", render: (sample) => `#${sample.id}` },
          { key: "summary", title: "失败摘要", render: (sample) => sample.failure_summary || "-" },
          { key: "type", title: "类型", render: (sample) => sample.failure_type || "-" },
          { key: "status", title: "状态", render: (sample) => <StatusBadge value={sample.status} /> }
        ]}
        rows={samples}
        emptyText="暂无失败样本"
        getRowKey={(sample) => sample.id}
      />
    </section>
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
          { key: "instruction", title: "用户指令", render: (item) => item.user_instruction || "-" },
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

function PlaceholderPanel({ icon, title, text }: { icon: ReactNode; title: string; text: string }) {
  return (
    <section className="surface-panel placeholder-panel">
      <div className="panel-heading">
        <h2>
          {icon}
          {title}
        </h2>
        <FlaskConical size={18} />
      </div>
      <p>{text}</p>
    </section>
  );
}
