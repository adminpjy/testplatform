import {
  Boxes,
  BrainCircuit,
  Bug,
  CheckCircle2,
  ClipboardList,
  FileCog,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  UsersRound,
  Wrench
} from "lucide-react";
import type { ComponentType, ReactNode } from "react";
import { useEffect, useState } from "react";

import {
  checkPlugin,
  createAsset,
  createDefectFromFailure,
  createLearningItem,
  createPlatformUser,
  deleteAsset,
  deleteDefect,
  deleteFailureWorkbenchItem,
  deleteLearningItem,
  deletePlatformUser,
  deletePlugin,
  generateCases,
  generateFailureSolution,
  getAssets,
  getDefects,
  getFailureWorkbench,
  getLearningItems,
  getPlatformUsers,
  getPlugins,
  getQualityOverview,
  publishAsset,
  registerPlugin,
  transitionLearningItem,
  updateAsset,
  updateDefect,
  updateFailureWorkbenchItem,
  updateLearningItem,
  updatePlatformUser,
  updatePlugin
} from "../api/maturity";
import { fileUrl } from "../api/client";
import { DataTable } from "../components/DataTable";
import { JsonCollapseBlock } from "../components/JsonCollapseBlock";
import { StatusBadge } from "../components/StatusBadge";
import type {
  AssetItem,
  DefectItem,
  FailureWorkbenchItem,
  GeneratedCase,
  LearningItem,
  PageResponse,
  PlatformUserItem,
  PluginItem,
  QualityOverview
} from "../types/maturity";
import { labelFailureType, labelRisk, labelScenarioType, labelStatus } from "../utils/displayLabels";

type EnterpriseTab = "overview" | "assets" | "generation" | "failures" | "defects" | "learning" | "security" | "plugins";

const tabs: Array<{ id: EnterpriseTab; label: string; icon: ComponentType<{ size?: number; strokeWidth?: number }> }> = [
  { id: "overview", label: "质量总览", icon: ClipboardList },
  { id: "assets", label: "资产中心", icon: Boxes },
  { id: "generation", label: "用例生成", icon: Sparkles },
  { id: "failures", label: "失败工作台", icon: Wrench },
  { id: "defects", label: "缺陷候选", icon: Bug },
  { id: "learning", label: "学习治理", icon: BrainCircuit },
  { id: "security", label: "安全权限", icon: ShieldCheck },
  { id: "plugins", label: "插件适配", icon: FileCog }
];

function emptyPage<T>(): PageResponse<T> {
  return { items: [], page: 1, pageSize: 10, total: 0, totalPages: 0, hasNext: false, hasPrev: false };
}

export function EnterpriseCenterPage() {
  const [activeTab, setActiveTab] = useState<EnterpriseTab>("overview");
  const [quality, setQuality] = useState<QualityOverview | null>(null);
  const [assets, setAssets] = useState<PageResponse<AssetItem>>(emptyPage());
  const [defects, setDefects] = useState<PageResponse<DefectItem>>(emptyPage());
  const [failures, setFailures] = useState<PageResponse<FailureWorkbenchItem>>(emptyPage());
  const [learning, setLearning] = useState<PageResponse<LearningItem>>(emptyPage());
  const [plugins, setPlugins] = useState<PageResponse<PluginItem>>(emptyPage());
  const [users, setUsers] = useState<PageResponse<PlatformUserItem>>(emptyPage());
  const [generatedCases, setGeneratedCases] = useState<GeneratedCase[]>([]);
  const [generationCoverage, setGenerationCoverage] = useState<Record<string, unknown> | null>(null);
  const [sourceText, setSourceText] = useState("工作台/我的待办：逐一点开待办，填写审批意见并提交。\n公文管理：按实例号查询，查看详情并校验状态。");
  const [solution, setSolution] = useState<Record<string, unknown> | null>(null);
  const [assetName, setAssetName] = useState("门户导航规则模板");
  const [pluginName, setPluginName] = useState("Ant Design UI 适配器");
  const [userName, setUserName] = useState("tester");
  const [learningTitle, setLearningTitle] = useState("审批表单自动填写规则");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void loadAll();
  }, []);

  async function loadAll() {
    setLoading(true);
    setError(null);
    try {
      const [qualityPayload, assetsPayload, defectsPayload, failuresPayload, learningPayload, pluginsPayload, usersPayload] = await Promise.all([
        getQualityOverview(),
        getAssets(assets.page),
        getDefects(defects.page),
        getFailureWorkbench(failures.page),
        getLearningItems(learning.page),
        getPlugins(plugins.page),
        getPlatformUsers(users.page)
      ]);
      setQuality(qualityPayload);
      setAssets(assetsPayload);
      setDefects(defectsPayload);
      setFailures(failuresPayload);
      setLearning(learningPayload);
      setPlugins(pluginsPayload);
      setUsers(usersPayload);
    } catch (requestError) {
      setError(readError(requestError));
    } finally {
      setLoading(false);
    }
  }

  async function loadAssetsPage(page: number) {
    setAssets(await getAssets(page));
  }

  async function loadDefectsPage(page: number) {
    setDefects(await getDefects(page));
  }

  async function loadFailuresPage(page: number) {
    setFailures(await getFailureWorkbench(page));
  }

  async function loadLearningPage(page: number) {
    setLearning(await getLearningItems(page));
  }

  async function loadPluginsPage(page: number) {
    setPlugins(await getPlugins(page));
  }

  async function loadUsersPage(page: number) {
    setUsers(await getPlatformUsers(page));
  }

  async function handleGenerateCases() {
    setError(null);
    try {
      const result = await generateCases(sourceText);
      setGeneratedCases(result.items);
      setGenerationCoverage(result.coverage);
    } catch (requestError) {
      setError(readError(requestError));
    }
  }

  async function handleCreateAsset() {
    setError(null);
    try {
      await createAsset({
        assetName,
        assetType: "rule_template",
        module: "平台通用",
        riskLevel: "medium",
        description: "由企业能力中心创建的可复用资产。",
        content: { fields: ["match", "action", "verification"], source: "enterprise_center" }
      });
      await loadAssetsPage(1);
    } catch (requestError) {
      setError(readError(requestError));
    }
  }

  async function handleCreateLearningItem() {
    setError(null);
    try {
      await createLearningItem({
        itemType: "rule_candidate",
        title: learningTitle,
        riskLevel: "medium",
        proposal: { source: "enterprise_center", validation: "dry_run_required" }
      });
      await loadLearningPage(1);
    } catch (requestError) {
      setError(readError(requestError));
    }
  }

  async function handleRegisterPlugin() {
    setError(null);
    try {
      await registerPlugin({
        pluginName,
        pluginType: "ui_adapter",
        configSchema: { properties: { framework: { type: "string" } } },
        config: { framework: "enterprise-web" }
      });
      await loadPluginsPage(1);
    } catch (requestError) {
      setError(readError(requestError));
    }
  }

  async function handleCreateUser() {
    setError(null);
    try {
      await createPlatformUser({ username: userName, displayName: userName, role: "tester" });
      await loadUsersPage(1);
    } catch (requestError) {
      setError(readError(requestError));
    }
  }

  async function runAction(action: () => Promise<void>) {
    setError(null);
    try {
      await action();
      await loadAll();
    } catch (requestError) {
      setError(readError(requestError));
    }
  }

  function confirmDelete(label: string): boolean {
    return window.confirm(`确认删除“${label}”？`);
  }

  return (
    <div className="page-stack enterprise-page">
      <section className="surface-panel enterprise-header">
        <div className="panel-heading">
          <div>
            <h1>企业级能力中心</h1>
            <span>把规则、资产、用例、失败复盘、缺陷、学习治理、安全和插件统一到一个运维入口。</span>
          </div>
          <button className="secondary-button" type="button" onClick={() => void loadAll()}>
            <RefreshCw size={16} />
            {loading ? "刷新中" : "刷新"}
          </button>
        </div>
        <div className="tab-strip">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                className={activeTab === tab.id ? "tab-button tab-button--active" : "tab-button"}
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
              >
                <Icon size={15} />
                {tab.label}
              </button>
            );
          })}
        </div>
        {error ? <pre className="error-detail error-detail--collapsed">{error}</pre> : null}
      </section>

      {activeTab === "overview" ? <OverviewTab quality={quality} /> : null}
      {activeTab === "assets" ? (
        <AssetsTab
          assets={assets}
          assetName={assetName}
          setAssetName={setAssetName}
          onCreate={handleCreateAsset}
          onPage={loadAssetsPage}
          onPublish={async (id) => { await publishAsset(id); await loadAssetsPage(assets.page); }}
          onEdit={(item) => runAction(async () => {
            const value = promptValue("资产名称", item.assetName);
            if (value === null) return;
            await updateAsset(item.id, { assetName: value });
          })}
          onDelete={(item) => runAction(async () => {
            if (!confirmDelete(item.assetName)) return;
            await deleteAsset(item.id);
          })}
        />
      ) : null}
      {activeTab === "generation" ? (
        <GenerationTab sourceText={sourceText} setSourceText={setSourceText} generatedCases={generatedCases} coverage={generationCoverage} onGenerate={handleGenerateCases} />
      ) : null}
      {activeTab === "failures" ? (
        <FailureWorkbenchTab
          failures={failures}
          solution={solution}
          onPage={loadFailuresPage}
          onGenerateSolution={async (id) => setSolution(await generateFailureSolution(id))}
          onCreateDefect={async (id) => { await createDefectFromFailure(id); await loadDefectsPage(1); }}
          onEdit={(item) => runAction(async () => {
            const value = promptValue("失败样本状态", item.status);
            if (value === null) return;
            await updateFailureWorkbenchItem(item.id, { status: value });
          })}
          onDelete={(item) => runAction(async () => {
            if (!confirmDelete(`失败样本 #${item.id}`)) return;
            await deleteFailureWorkbenchItem(item.id);
          })}
        />
      ) : null}
      {activeTab === "defects" ? <DefectsTab defects={defects} onPage={loadDefectsPage} onEdit={(item) => runAction(async () => {
        const value = promptValue("缺陷标题", item.title);
        if (value === null) return;
        await updateDefect(item.id, { title: value });
      })} onDelete={(item) => runAction(async () => {
        if (!confirmDelete(item.title)) return;
        await deleteDefect(item.id);
      })} /> : null}
      {activeTab === "learning" ? (
        <LearningTab
          learning={learning}
          title={learningTitle}
          setTitle={setLearningTitle}
          onCreate={handleCreateLearningItem}
          onPage={loadLearningPage}
          onTransition={async (id, status) => { await transitionLearningItem(id, status); await loadLearningPage(learning.page); }}
          onEdit={(item) => runAction(async () => {
            const value = promptValue("学习项标题", item.title);
            if (value === null) return;
            await updateLearningItem(item.id, { title: value });
          })}
          onDelete={(item) => runAction(async () => {
            if (!confirmDelete(item.title)) return;
            await deleteLearningItem(item.id);
          })}
        />
      ) : null}
      {activeTab === "security" ? (
        <SecurityTab users={users} userName={userName} setUserName={setUserName} onCreate={handleCreateUser} onPage={loadUsersPage} onEdit={(item) => runAction(async () => {
          const value = promptValue("显示名称", item.displayName || item.username);
          if (value === null) return;
          await updatePlatformUser(item.id, { displayName: value });
        })} onDelete={(item) => runAction(async () => {
          if (!confirmDelete(item.username)) return;
          await deletePlatformUser(item.id);
        })} />
      ) : null}
      {activeTab === "plugins" ? (
        <PluginsTab
          plugins={plugins}
          pluginName={pluginName}
          setPluginName={setPluginName}
          onRegister={handleRegisterPlugin}
          onPage={loadPluginsPage}
          onHealthCheck={async (id) => { await checkPlugin(id); await loadPluginsPage(plugins.page); }}
          onEdit={(item) => runAction(async () => {
            const value = promptValue("插件名称", item.pluginName);
            if (value === null) return;
            await updatePlugin(item.id, { pluginName: value });
          })}
          onDelete={(item) => runAction(async () => {
            if (!confirmDelete(item.pluginName)) return;
            await deletePlugin(item.id);
          })}
        />
      ) : null}
    </div>
  );
}

function OverviewTab({ quality }: { quality: QualityOverview | null }) {
  const totals = quality?.totals || {};
  return (
    <div className="page-stack">
      <section className="enterprise-metric-grid">
        <Metric title="用例数" value={totals.cases ?? 0} detail="当前项目资产覆盖" />
        <Metric title="执行数" value={totals.runs ?? 0} detail={`通过 ${totals.passed ?? 0} / 失败 ${totals.failed ?? 0}`} />
        <Metric title="通过率" value={`${totals.passRate ?? 0}%`} detail="按测试运行聚合" />
        <Metric title="缺陷候选" value={totals.defects ?? 0} detail="可下钻确认和分派" />
      </section>
      <section className="enterprise-grid-two">
        <Panel title="模块覆盖" icon={<ClipboardList size={18} />}>
          <KeyValueRows items={(quality?.modules || []).map((item) => ({ label: String(item.module || "未分组"), value: Number(item.caseCount || 0) }))} />
        </Panel>
        <Panel title="风险建议" icon={<CheckCircle2 size={18} />}>
          {(quality?.recommendations || []).map((item, index) => (
            <p className="enterprise-recommendation" key={`${item}-${index}`}>{item}</p>
          ))}
        </Panel>
      </section>
    </div>
  );
}

function AssetsTab({
  assets,
  assetName,
  setAssetName,
  onCreate,
  onPage,
  onPublish,
  onEdit,
  onDelete
}: {
  assets: PageResponse<AssetItem>;
  assetName: string;
  setAssetName: (value: string) => void;
  onCreate: () => Promise<void>;
  onPage: (page: number) => Promise<void>;
  onPublish: (id: number) => Promise<void>;
  onEdit: (item: AssetItem) => Promise<void>;
  onDelete: (item: AssetItem) => Promise<void>;
}) {
  return (
    <section className="surface-panel enterprise-panel">
      <div className="enterprise-toolbar">
        <input value={assetName} onChange={(event) => setAssetName(event.target.value)} />
        <button className="primary-button" type="button" onClick={() => void onCreate()}>新增资产</button>
      </div>
      <DataTable
        columns={[
          { key: "code", title: "编码", render: (item) => item.assetCode },
          { key: "name", title: "名称", render: (item) => item.assetName },
          { key: "type", title: "类型", render: (item) => labelAssetType(item.assetType) },
          { key: "module", title: "模块", render: (item) => item.module || "-" },
          { key: "risk", title: "风险", render: (item) => labelRisk(item.riskLevel) },
          { key: "status", title: "状态", render: (item) => <StatusBadge value={item.status} /> },
          {
            key: "action",
            title: "操作",
            render: (item) => (
              <div className="table-actions">
                <button className="table-link-button" type="button" onClick={() => void onEdit(item)}>修改</button>
                <button className="table-link-button" type="button" onClick={() => void onPublish(item.id)}>发布</button>
                <button className="table-link-button" type="button" onClick={() => void onDelete(item)}>删除</button>
              </div>
            )
          }
        ]}
        rows={assets.items}
        emptyText="暂无资产"
        getRowKey={(item) => item.id}
      />
      <Pager page={assets} onPage={onPage} />
    </section>
  );
}

function GenerationTab({
  sourceText,
  setSourceText,
  generatedCases,
  coverage,
  onGenerate
}: {
  sourceText: string;
  setSourceText: (value: string) => void;
  generatedCases: GeneratedCase[];
  coverage: Record<string, unknown> | null;
  onGenerate: () => Promise<void>;
}) {
  return (
    <section className="surface-panel enterprise-panel">
      <div className="enterprise-generation-grid">
        <label className="stacked-field">
          <span>需求、菜单路径或功能清单</span>
          <textarea value={sourceText} onChange={(event) => setSourceText(event.target.value)} />
        </label>
        <div className="enterprise-side-card">
          <button className="primary-button" type="button" onClick={() => void onGenerate()}>
            <Sparkles size={16} />
            生成测试用例
          </button>
          {coverage ? <JsonCollapseBlock title="覆盖率分析" value={coverage} /> : null}
        </div>
      </div>
      <DataTable
        columns={[
          { key: "name", title: "用例", render: (item) => item.caseName },
          { key: "module", title: "模块", render: (item) => item.module || "-" },
          { key: "scenario", title: "场景", render: (item) => labelScenarioType(item.scenarioType) },
          { key: "goal", title: "目标", render: (item) => <span className="text-cell">{item.naturalLanguageGoal}</span> },
          { key: "risk", title: "风险", render: (item) => labelRisk(item.riskLevel) },
          { key: "score", title: "自动化分", render: (item) => item.automationScore }
        ]}
        rows={generatedCases}
        emptyText="尚未生成用例"
        getRowKey={(item) => `${item.caseName}-${item.scenarioType}`}
      />
    </section>
  );
}

function FailureWorkbenchTab({
  failures,
  solution,
  onPage,
  onGenerateSolution,
  onCreateDefect,
  onEdit,
  onDelete
}: {
  failures: PageResponse<FailureWorkbenchItem>;
  solution: Record<string, unknown> | null;
  onPage: (page: number) => Promise<void>;
  onGenerateSolution: (id: number) => Promise<void>;
  onCreateDefect: (id: number) => Promise<void>;
  onEdit: (item: FailureWorkbenchItem) => Promise<void>;
  onDelete: (item: FailureWorkbenchItem) => Promise<void>;
}) {
  return (
    <section className="surface-panel enterprise-panel">
      <DataTable
        columns={[
          { key: "id", title: "样本", render: (item) => `#${item.id}` },
          { key: "type", title: "失败类型", render: (item) => labelFailureType(item.failureType) },
          { key: "summary", title: "摘要", render: (item) => <span className="text-cell">{item.failureSummary || "-"}</span> },
          { key: "risk", title: "风险", render: (item) => labelRisk(item.riskLevel) },
          { key: "status", title: "状态", render: (item) => <StatusBadge value={item.status} /> },
          { key: "shot", title: "截图", render: (item) => item.screenshotPath ? <img className="ability-thumb" src={fileUrl(item.screenshotPath)} alt="失败截图" /> : "-" },
          {
            key: "action",
            title: "动作",
            render: (item) => (
              <div className="table-actions">
                <button className="table-link-button" type="button" onClick={() => void onEdit(item)}>修改</button>
                <button className="table-link-button" type="button" onClick={() => void onGenerateSolution(item.id)}>生成方案</button>
                <button className="table-link-button" type="button" onClick={() => void onCreateDefect(item.id)}>转缺陷</button>
                <button className="table-link-button" type="button" onClick={() => void onDelete(item)}>删除</button>
              </div>
            )
          }
        ]}
        rows={failures.items}
        emptyText="暂无失败样本"
        getRowKey={(item) => item.id}
      />
      <Pager page={failures} onPage={onPage} />
      {solution ? <JsonCollapseBlock title="最新解决方案" value={solution} /> : null}
    </section>
  );
}

function DefectsTab({
  defects,
  onPage,
  onEdit,
  onDelete
}: {
  defects: PageResponse<DefectItem>;
  onPage: (page: number) => Promise<void>;
  onEdit: (item: DefectItem) => Promise<void>;
  onDelete: (item: DefectItem) => Promise<void>;
}) {
  return (
    <section className="surface-panel enterprise-panel">
      <DataTable
        columns={[
          { key: "code", title: "缺陷编码", render: (item) => item.defectCode },
          { key: "title", title: "标题", render: (item) => <span className="text-cell">{item.title}</span> },
          { key: "type", title: "类型", render: (item) => labelDefectType(item.defectType) },
          { key: "severity", title: "严重级别", render: (item) => labelRisk(item.severity) },
          { key: "priority", title: "优先级", render: (item) => labelRisk(item.priority) },
          { key: "status", title: "状态", render: (item) => <StatusBadge value={item.status} /> },
          {
            key: "actions",
            title: "操作",
            render: (item) => (
              <div className="table-actions">
                <button className="table-link-button" type="button" onClick={() => void onEdit(item)}>修改</button>
                <button className="table-link-button" type="button" onClick={() => void onDelete(item)}>删除</button>
              </div>
            )
          }
        ]}
        rows={defects.items}
        emptyText="暂无缺陷候选"
        getRowKey={(item) => item.id}
      />
      <Pager page={defects} onPage={onPage} />
    </section>
  );
}

function LearningTab({
  learning,
  title,
  setTitle,
  onCreate,
  onPage,
  onTransition,
  onEdit,
  onDelete
}: {
  learning: PageResponse<LearningItem>;
  title: string;
  setTitle: (value: string) => void;
  onCreate: () => Promise<void>;
  onPage: (page: number) => Promise<void>;
  onTransition: (id: number, status: string) => Promise<void>;
  onEdit: (item: LearningItem) => Promise<void>;
  onDelete: (item: LearningItem) => Promise<void>;
}) {
  return (
    <section className="surface-panel enterprise-panel">
      <div className="enterprise-toolbar">
        <input value={title} onChange={(event) => setTitle(event.target.value)} />
        <button className="primary-button" type="button" onClick={() => void onCreate()}>新增学习项</button>
      </div>
      <DataTable
        columns={[
          { key: "code", title: "编码", render: (item) => item.learningCode },
          { key: "title", title: "标题", render: (item) => item.title },
          { key: "type", title: "类型", render: (item) => labelLearningType(item.itemType) },
          { key: "risk", title: "风险", render: (item) => labelRisk(item.riskLevel) },
          { key: "status", title: "状态", render: (item) => <StatusBadge value={item.status} /> },
          {
            key: "action",
            title: "操作",
            render: (item) => (
              <div className="table-actions">
                <button className="table-link-button" type="button" onClick={() => void onEdit(item)}>修改</button>
                <button className="table-link-button" type="button" onClick={() => void onTransition(item.id, "verified")}>验证通过</button>
                <button className="table-link-button" type="button" onClick={() => void onTransition(item.id, "active")}>启用</button>
                <button className="table-link-button" type="button" onClick={() => void onDelete(item)}>删除</button>
              </div>
            )
          }
        ]}
        rows={learning.items}
        emptyText="暂无学习项"
        getRowKey={(item) => item.id}
      />
      <Pager page={learning} onPage={onPage} />
    </section>
  );
}

function SecurityTab({
  users,
  userName,
  setUserName,
  onCreate,
  onPage,
  onEdit,
  onDelete
}: {
  users: PageResponse<PlatformUserItem>;
  userName: string;
  setUserName: (value: string) => void;
  onCreate: () => Promise<void>;
  onPage: (page: number) => Promise<void>;
  onEdit: (item: PlatformUserItem) => Promise<void>;
  onDelete: (item: PlatformUserItem) => Promise<void>;
}) {
  return (
    <section className="surface-panel enterprise-panel">
      <div className="enterprise-toolbar">
        <input value={userName} onChange={(event) => setUserName(event.target.value)} />
        <button className="primary-button" type="button" onClick={() => void onCreate()}>新增用户</button>
      </div>
      <DataTable
        columns={[
          { key: "user", title: "账号", render: (item) => item.username },
          { key: "name", title: "姓名", render: (item) => item.displayName || "-" },
          { key: "role", title: "角色", render: (item) => labelUserRole(item.role) },
          { key: "status", title: "状态", render: (item) => <StatusBadge value={item.status} /> },
          {
            key: "actions",
            title: "操作",
            render: (item) => (
              <div className="table-actions">
                <button className="table-link-button" type="button" onClick={() => void onEdit(item)}>修改</button>
                <button className="table-link-button" type="button" onClick={() => void onDelete(item)}>删除</button>
              </div>
            )
          }
        ]}
        rows={users.items}
        emptyText="暂无用户"
        getRowKey={(item) => item.id}
      />
      <Pager page={users} onPage={onPage} />
    </section>
  );
}

function PluginsTab({
  plugins,
  pluginName,
  setPluginName,
  onRegister,
  onPage,
  onHealthCheck,
  onEdit,
  onDelete
}: {
  plugins: PageResponse<PluginItem>;
  pluginName: string;
  setPluginName: (value: string) => void;
  onRegister: () => Promise<void>;
  onPage: (page: number) => Promise<void>;
  onHealthCheck: (id: number) => Promise<void>;
  onEdit: (item: PluginItem) => Promise<void>;
  onDelete: (item: PluginItem) => Promise<void>;
}) {
  return (
    <section className="surface-panel enterprise-panel">
      <div className="enterprise-toolbar">
        <input value={pluginName} onChange={(event) => setPluginName(event.target.value)} />
        <button className="primary-button" type="button" onClick={() => void onRegister()}>注册插件</button>
      </div>
      <DataTable
        columns={[
          { key: "code", title: "编码", render: (item) => item.pluginCode },
          { key: "name", title: "名称", render: (item) => item.pluginName },
          { key: "type", title: "类型", render: (item) => labelPluginType(item.pluginType) },
          { key: "version", title: "版本", render: (item) => item.version },
          { key: "status", title: "状态", render: (item) => <StatusBadge value={item.status} /> },
          { key: "health", title: "健康", render: (item) => labelStatus(String(item.health.status || "unknown")) },
          {
            key: "action",
            title: "操作",
            render: (item) => (
              <div className="table-actions">
                <button className="table-link-button" type="button" onClick={() => void onEdit(item)}>修改</button>
                <button className="table-link-button" type="button" onClick={() => void onHealthCheck(item.id)}>健康检查</button>
                <button className="table-link-button" type="button" onClick={() => void onDelete(item)}>删除</button>
              </div>
            )
          }
        ]}
        rows={plugins.items}
        emptyText="暂无插件"
        getRowKey={(item) => item.id}
      />
      <Pager page={plugins} onPage={onPage} />
    </section>
  );
}

function Panel({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <section className="surface-panel enterprise-panel">
      <div className="panel-heading">
        <h2>{icon}{title}</h2>
      </div>
      {children}
    </section>
  );
}

function Metric({ title, value, detail }: { title: string; value: string | number; detail: string }) {
  return (
    <article className="surface-panel enterprise-metric-card">
      <span>{title}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function KeyValueRows({ items }: { items: Array<{ label: string; value: number }> }) {
  if (items.length === 0) return <div className="empty-state">暂无数据</div>;
  return (
    <div className="ability-key-value-list">
      {items.map((item) => (
        <div key={item.label}>
          <span>{item.label}</span>
          <strong>{item.value}</strong>
        </div>
      ))}
    </div>
  );
}

function Pager<T>({ page, onPage }: { page: PageResponse<T>; onPage: (page: number) => Promise<void> }) {
  return (
    <div className="pagination-bar">
      <span>
        第 {page.page} / {Math.max(page.totalPages, 1)} 页，共 {page.total} 条
      </span>
      <div>
        <button className="secondary-button" type="button" disabled={!page.hasPrev} onClick={() => void onPage(page.page - 1)}>上一页</button>
        <button className="secondary-button" type="button" disabled={!page.hasNext} onClick={() => void onPage(page.page + 1)}>下一页</button>
      </div>
    </div>
  );
}

function readError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function labelAssetType(value: string): string {
  const labels: Record<string, string> = {
    rule_template: "规则模板",
    prompt_template: "提示词模板",
    test_case: "测试用例",
    knowledge: "知识资产",
    ui_adapter: "界面适配器"
  };
  return labels[value] || "其他资产";
}

function labelDefectType(value: string): string {
  const labels: Record<string, string> = {
    product_bug: "产品缺陷",
    automation_bug: "自动化问题",
    environment_issue: "环境问题",
    data_issue: "数据问题",
    rule_gap: "规则缺口"
  };
  return labels[value] || "其他缺陷";
}

function labelLearningType(value: string): string {
  const labels: Record<string, string> = {
    rule_candidate: "规则候选",
    prompt_candidate: "提示词候选",
    locator_knowledge: "定位知识",
    recovery_policy: "恢复策略",
    ui_adapter: "界面适配器"
  };
  return labels[value] || "其他学习项";
}

function labelUserRole(value: string): string {
  const labels: Record<string, string> = {
    tester: "测试人员",
    maintainer: "维护人员",
    admin: "管理员",
    viewer: "只读用户"
  };
  return labels[value] || "其他角色";
}

function labelPluginType(value: string): string {
  const labels: Record<string, string> = {
    ui_adapter: "界面适配器",
    data_provider: "数据提供器",
    report_exporter: "报告导出器",
    llm_provider: "大模型服务",
    rule_pack: "规则包"
  };
  return labels[value] || "其他插件";
}

function promptValue(label: string, currentValue: string): string | null {
  const value = window.prompt(`请输入${label}`, currentValue);
  if (value === null) return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}
