import { BookOpen, FileWarning, FlaskConical, History, Lightbulb, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import { getAbilityRules, getTestRuns } from "../api/platform";
import { DataTable } from "../components/DataTable";
import { StatusBadge } from "../components/StatusBadge";
import type { AbilityRule, TestRun } from "../types/platform";

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
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [ruleList, runList] = await Promise.all([getAbilityRules(), getTestRuns()]);
      setRules(ruleList);
      setRuns(runList);
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
  const failedRuns = runs.filter((run) => run.status === "failed");

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
        <PlaceholderPanel icon={<BookOpen size={18} />} title="页面知识库" text="页面指纹、语义目标和成功定位路径会在后续运行复盘中沉淀。" />
      ) : null}
      {activeTab === "failures" ? <FailureMiniView failedRuns={failedRuns} /> : null}
      {activeTab === "interventions" ? (
        <PlaceholderPanel icon={<History size={18} />} title="人工介入记录" text="人工介入入口已在测试运行页预留，后续可接入持久化记录列表。" />
      ) : null}
      {activeTab === "drafts" ? (
        <PlaceholderPanel icon={<Lightbulb size={18} />} title="规则草案" text="失败分析和人工介入可形成规则草案，当前页面保留审核入口。" />
      ) : null}
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

function FailureMiniView({ failedRuns }: { failedRuns: TestRun[] }) {
  return (
    <section className="surface-panel">
      <div className="panel-heading">
        <h2>
          <FileWarning size={18} />
          失败样本
        </h2>
        <span>{failedRuns.length} 条</span>
      </div>
      <DataTable
        columns={[
          { key: "code", title: "运行编码", render: (run) => run.run_code },
          { key: "instruction", title: "测试目标", render: (run) => run.instruction || "-" },
          { key: "status", title: "状态", render: (run) => <StatusBadge value={run.status} /> }
        ]}
        rows={failedRuns}
        emptyText="暂无失败运行"
        getRowKey={(run) => run.id}
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
