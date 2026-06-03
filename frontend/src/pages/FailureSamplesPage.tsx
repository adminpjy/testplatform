import { ClipboardCopy, ExternalLink, FilePlus2, RefreshCw, Rocket, Save, ShieldCheck, UserRoundCheck, WandSparkles } from "lucide-react";
import { useEffect, useState } from "react";

import { apiUrl, fileUrl } from "../api/client";
import {
  createMaintenanceResponse,
  createRuleDraftFromSolution,
  deleteFailureSample,
  generateFailureSolutionFromSample,
  getFailureContext,
  getFailureSamplesPaged,
  getFailureSolutions,
  publishFailureSolution,
  updateFailureSolution,
  validateFailureSolution
} from "../api/platform";
import { JsonCollapseBlock } from "../components/JsonCollapseBlock";
import { StatusBadge } from "../components/StatusBadge";
import type { FailureContext, FailureSample, FailureSolution, MaintenanceResponse, PageResponse, RuleValidation } from "../types/platform";
import { labelFailureType } from "../utils/displayLabels";

function emptyPage(): PageResponse<FailureSample> {
  return { items: [], page: 1, pageSize: 10, total: 0, totalPages: 0, hasNext: false, hasPrev: false };
}

export function FailureSamplesPage() {
  const [samples, setSamples] = useState<PageResponse<FailureSample>>(emptyPage());
  const [expandedSampleId, setExpandedSampleId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void loadSamples(1);
  }, []);

  async function loadSamples(page = samples.page) {
    setLoading(true);
    setError(null);
    try {
      setSamples(await getFailureSamplesPaged(page));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(sampleId: number) {
    if (!window.confirm(`确认删除失败样本 #${sampleId}？`)) return;
    setError(null);
    try {
      await deleteFailureSample(sampleId);
      await loadSamples(samples.items.length === 1 && samples.page > 1 ? samples.page - 1 : samples.page);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    }
  }

  return (
    <div className="page-stack">
      <section className="surface-panel">
        <div className="panel-heading">
          <h1>失败样本</h1>
          <button className="secondary-button" type="button" onClick={() => void loadSamples()}>
            <RefreshCw size={16} />
            {loading ? "刷新中" : "刷新"}
          </button>
        </div>
        {error ? <pre className="error-detail error-detail--collapsed">{error}</pre> : null}
      </section>

      <div className="failure-sample-list">
        {samples.items.length === 0 ? <section className="surface-panel empty-state">暂无失败样本</section> : null}
        {samples.items.map((sample) => (
          <section className="surface-panel failure-sample" key={sample.id}>
            <div className="panel-heading">
              <h2>失败样本 #{sample.id}</h2>
              <StatusBadge value={sample.status} />
            </div>
            <div className="failure-sample__meta">
              {sample.project_id ? <span>项目 #{sample.project_id}</span> : null}
              {sample.case_id ? <span>用例 #{sample.case_id}</span> : null}
              <span>运行 #{sample.run_id}</span>
              <span>步骤 #{sample.step_id || "-"}</span>
              <span>{labelFailureType(sample.failure_type)}</span>
              <span>{new Date(sample.created_at).toLocaleString("zh-CN")}</span>
            </div>
            <pre className="error-detail error-detail--collapsed">
              {sample.failure_summary || "失败摘要待补充"}
            </pre>
            <div className="artifact-link-grid">
              {sample.screenshot_path ? <a href={fileUrl(sample.screenshot_path)} target="_blank" rel="noreferrer">截图</a> : null}
              {sample.dom_snapshot_path ? <a href={fileUrl(sample.dom_snapshot_path)} target="_blank" rel="noreferrer">页面结构快照</a> : null}
              {sample.accessibility_snapshot_path ? <a href={fileUrl(sample.accessibility_snapshot_path)} target="_blank" rel="noreferrer">可访问性快照</a> : null}
              {sample.locator_debug_path ? <a href={fileUrl(sample.locator_debug_path)} target="_blank" rel="noreferrer">定位调试文件</a> : null}
              {sample.runtime_stream_path ? <a href={fileUrl(sample.runtime_stream_path)} target="_blank" rel="noreferrer">运行消息</a> : null}
            </div>
            <div className="action-bar">
              {sample.report_path ? (
                <a className="secondary-link" href={apiUrl(`/api/reports/${sample.run_id}`)} target="_blank" rel="noreferrer">
                  <ExternalLink size={16} />
                  打开报告
                </a>
              ) : null}
              <a className="secondary-link" href="#test-run">
                <UserRoundCheck size={16} />
                人工介入
              </a>
              <button className="secondary-button" type="button" onClick={() => void handleDelete(sample.id)}>
                删除
              </button>
              <button className="primary-button" type="button" onClick={() => setExpandedSampleId(expandedSampleId === sample.id ? null : sample.id)}>
                <WandSparkles size={16} />
                {expandedSampleId === sample.id ? "收起处理" : "智能处理"}
              </button>
            </div>
            {expandedSampleId === sample.id ? <FailureWorkflowPanel sample={sample} onRefresh={() => void loadSamples(samples.page)} /> : null}
          </section>
        ))}
      </div>
      <div className="surface-panel failure-sample-pagination">
        <div className="pagination-bar">
          <span>第 {samples.page} / {Math.max(samples.totalPages, 1)} 页，共 {samples.total} 条</span>
          <div>
            <button className="secondary-button" type="button" disabled={!samples.hasPrev} onClick={() => void loadSamples(samples.page - 1)}>上一页</button>
            <button className="secondary-button" type="button" disabled={!samples.hasNext} onClick={() => void loadSamples(samples.page + 1)}>下一页</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function FailureWorkflowPanel({ sample, onRefresh }: { sample: FailureSample; onRefresh: () => void }) {
  const [context, setContext] = useState<FailureContext | null>(null);
  const [solutions, setSolutions] = useState<FailureSolution[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [draft, setDraft] = useState({ rootCause: "", solutionSummary: "", userReply: "", internalNotes: "" });
  const [validation, setValidation] = useState<RuleValidation | null>(null);
  const [response, setResponse] = useState<MaintenanceResponse | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const selectedSolution = solutions.find((item) => item.id === selectedId) || solutions[0] || null;

  useEffect(() => {
    void loadWorkflow();
  }, [sample.id]);

  useEffect(() => {
    if (!selectedSolution) {
      setDraft({ rootCause: "", solutionSummary: "", userReply: "", internalNotes: "" });
      return;
    }
    setDraft({
      rootCause: selectedSolution.root_cause || "",
      solutionSummary: selectedSolution.solution_summary || "",
      userReply: selectedSolution.user_reply || "",
      internalNotes: selectedSolution.internal_notes || ""
    });
  }, [selectedSolution?.id]);

  async function loadWorkflow() {
    setBusy(true);
    setError(null);
    try {
      const [contextPayload, solutionPayload] = await Promise.all([
        getFailureContext(sample.id),
        getFailureSolutions(sample.id)
      ]);
      setContext(contextPayload);
      setSolutions(solutionPayload);
      setSelectedId((current) => current || solutionPayload[0]?.id || null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    } finally {
      setBusy(false);
    }
  }

  async function runAction(action: () => Promise<void>, successMessage: string) {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await action();
      setMessage(successMessage);
      await loadWorkflow();
      onRefresh();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    } finally {
      setBusy(false);
    }
  }

  async function generateSolution(force = false) {
    await runAction(async () => {
      const solution = await generateFailureSolutionFromSample(sample.id, force);
      setSelectedId(solution.id);
    }, "方案已生成。");
  }

  async function saveSolution() {
    if (!selectedSolution) return;
    await runAction(async () => {
      const updated = await updateFailureSolution(selectedSolution.id, {
        rootCause: draft.rootCause,
        solutionSummary: draft.solutionSummary,
        userReply: draft.userReply,
        internalNotes: draft.internalNotes
      });
      setSelectedId(updated.id);
    }, "方案已保存。");
  }

  async function createDraft() {
    if (!selectedSolution) return;
    await runAction(async () => {
      await createRuleDraftFromSolution(selectedSolution.id);
    }, "规则草案已生成。");
  }

  async function validateRule() {
    if (!selectedSolution) return;
    await runAction(async () => {
      const result = await validateFailureSolution(selectedSolution.id, [sample.id]);
      setValidation(result);
    }, "证据预验证已完成。");
  }

  async function publishRule() {
    if (!selectedSolution) return;
    await runAction(async () => {
      await publishFailureSolution(selectedSolution.id);
    }, "规则已发布。");
  }

  async function generateResponse() {
    if (!selectedSolution) return;
    await runAction(async () => {
      const result = await createMaintenanceResponse(selectedSolution.id);
      setResponse(result);
    }, "维护回复已生成。");
  }

  async function copyReply() {
    const text = responseText(response || context?.maintenanceResponse) || draft.userReply || selectedSolution?.user_reply || "";
    if (!text) {
      setError("当前没有可复制的维护回复。");
      return;
    }
    await navigator.clipboard.writeText(text);
    setMessage("维护回复已复制。");
  }

  const opsContext = asRecord(asRecord(context?.context).opsContext);
  const currentValidation = validation || context?.latestValidation || null;
  const currentResponse = response || context?.maintenanceResponse || null;

  return (
    <div className="failure-workflow">
      <div className="failure-workflow__summary">
        <InfoItem label="项目" value={textValue(opsContext.projectName) || "-"} />
        <InfoItem label="用例" value={textValue(opsContext.caseName) || "-"} />
        <InfoItem label="执行人" value={textValue(opsContext.operator) || "-"} />
        <InfoItem label="执行时间" value={textValue(opsContext.executedAt) || "-"} />
        <InfoItem label="运行记录" value={textValue(opsContext.runCode) || `#${sample.run_id}`} />
      </div>

      <div className="action-bar">
        <button className="secondary-button" type="button" disabled={busy} onClick={() => void loadWorkflow()}>
          <RefreshCw size={16} />
          读取上下文
        </button>
        <button className="primary-button" type="button" disabled={busy} onClick={() => void generateSolution(false)}>
          <WandSparkles size={16} />
          生成方案
        </button>
        <button className="secondary-button" type="button" disabled={busy} onClick={() => void generateSolution(true)}>
          重新分析
        </button>
        {solutions.length > 1 ? (
          <select value={selectedId || ""} onChange={(event) => setSelectedId(Number(event.target.value))}>
            {solutions.map((solution) => (
              <option value={solution.id} key={solution.id}>{solution.solution_code} / {solution.status}</option>
            ))}
          </select>
        ) : null}
      </div>

      {error ? <pre className="error-detail error-detail--collapsed">{error}</pre> : null}
      {message ? <div className="success-banner">{message}</div> : null}

      {selectedSolution ? (
        <div className="failure-workflow__grid">
          <label>
            <span>问题原因</span>
            <textarea rows={4} value={draft.rootCause} onChange={(event) => setDraft((current) => ({ ...current, rootCause: event.target.value }))} />
          </label>
          <label>
            <span>处理方案</span>
            <textarea rows={4} value={draft.solutionSummary} onChange={(event) => setDraft((current) => ({ ...current, solutionSummary: event.target.value }))} />
          </label>
          <label>
            <span>对外回复</span>
            <textarea rows={7} value={draft.userReply} onChange={(event) => setDraft((current) => ({ ...current, userReply: event.target.value }))} />
          </label>
          <label>
            <span>内部备注</span>
            <textarea rows={7} value={draft.internalNotes} onChange={(event) => setDraft((current) => ({ ...current, internalNotes: event.target.value }))} />
          </label>
        </div>
      ) : (
        <div className="empty-state empty-state--compact">当前样本还没有方案，点击“生成方案”。</div>
      )}

      {selectedSolution ? (
        <div className="failure-workflow__steps">
          <button className="secondary-button" type="button" disabled={busy} onClick={() => void saveSolution()}>
            <Save size={16} />
            保存调整
          </button>
          <button className="secondary-button" type="button" disabled={busy} onClick={() => void createDraft()}>
            <FilePlus2 size={16} />
            生成规则草案
          </button>
          <button className="secondary-button" type="button" disabled={busy} onClick={() => void validateRule()}>
            <ShieldCheck size={16} />
            预验证
          </button>
          <button className="secondary-button" type="button" disabled={busy || validationStatus(currentValidation) !== "passed"} onClick={() => void publishRule()}>
            <Rocket size={16} />
            发布规则
          </button>
          <button className="secondary-button" type="button" disabled={busy} onClick={() => void generateResponse()}>
            <UserRoundCheck size={16} />
            生成回复
          </button>
          <button className="secondary-button" type="button" disabled={busy} onClick={() => void copyReply()}>
            <ClipboardCopy size={16} />
            复制回复
          </button>
        </div>
      ) : null}

      <div className="failure-workflow__details">
        {selectedSolution ? (
          <>
            <StatusLine label="方案状态" value={selectedSolution.status} />
            <StatusLine label="规则草案" value={selectedSolution.rule_draft_id ? `#${selectedSolution.rule_draft_id}` : "未生成"} />
            <StatusLine label="预验证" value={currentValidation ? `${validationStatus(currentValidation)}（通过 ${validationCount(currentValidation, "passed")} / 失败 ${validationCount(currentValidation, "failed")}）` : "未验证"} />
            <JsonCollapseBlock title="查看同类问题模式" value={selectedSolution.generalized_pattern_json || {}} />
            <JsonCollapseBlock title="查看规则草案内容" value={selectedSolution.suggested_rule_json || {}} />
          </>
        ) : null}
        {currentValidation ? <JsonCollapseBlock title="查看预验证结果" value={validationResult(currentValidation)} /> : null}
        {currentResponse ? <JsonCollapseBlock title="查看维护回复记录" value={currentResponse as unknown as Record<string, unknown>} /> : null}
        {context ? <JsonCollapseBlock title="查看完整上下文包" value={context.context} /> : null}
      </div>
    </div>
  );
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function StatusLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="failure-workflow__status-line">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function textValue(value: unknown): string {
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}

function validationStatus(value: unknown): string {
  const record = asRecord(value);
  return textValue(record.status) || "unknown";
}

function validationCount(value: unknown, type: "passed" | "failed"): number {
  const record = asRecord(value);
  const key = type === "passed" ? "passed_count" : "failed_count";
  const camelKey = type === "passed" ? "passedCount" : "failedCount";
  const raw = record[key] ?? record[camelKey];
  return typeof raw === "number" ? raw : Number(raw || 0);
}

function validationResult(value: unknown): Record<string, unknown> {
  const record = asRecord(value);
  return asRecord(record.result_json || record.result || {});
}

function responseText(value: unknown): string {
  const record = asRecord(value);
  return textValue(record.user_reply || record.userReply);
}
