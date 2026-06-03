import type { RuntimeMessage } from "../types/runtime";
import type { TestStepRun } from "../types/platform";
import { labelAction, labelFailureType, labelStatus } from "./displayLabels";

export type RuntimeFilter = "all" | "action" | "page" | "llm" | "vision" | "error";

export interface RuntimeDetailView {
  lines: string[];
}

const phaseTitles: Record<string, string> = {
  understanding: "正在理解测试用例",
  planning: "正在生成测试步骤",
  browser: "正在准备浏览器环境",
  sandbox_starting: "正在拉起执行环境",
  sandbox_ready: "执行环境已就绪",
  open_system: "正在打开被测系统",
  open_url: "正在打开页面",
  login: "正在登录系统",
  login_result: "正在验证登录结果",
  auth_guard: "正在检查登录状态",
  input: "正在填写输入框",
  click: "正在点击页面元素",
  navigate_menu: "正在导航菜单",
  navigation_path: "正在执行菜单路径导航",
  verify: "正在验证执行结果",
  observe: "正在读取页面结构",
  page_ready: "正在等待页面加载完成",
  page_reading: "正在读取页面结构",
  page_semantic: "正在分析页面语义",
  locate: "正在分析候选元素",
  candidate_ranker: "正在分析候选元素",
  ambiguity_resolver: "正在处理候选元素冲突",
  llm_action_resolver: "正在调用大模型辅助判断",
  llm_resolver: "正在调用大模型辅助判断",
  llm_request: "正在调用大模型",
  llm_chunk: "正在接收大模型流式输出",
  llm_response: "大模型回复已接收",
  json_repair: "正在校验结构化输出",
  analysis_result: "正在生成分析结论",
  dsl_generated: "正在生成测试步骤",
  vision_resolver: "正在启用视觉兜底识别",
  vision: "正在启用视觉兜底识别",
  business_goal_agent: "正在执行业务目标",
  intent: "正在识别业务意图",
  global_interruption: "正在检查弹窗或中断提示",
  screenshot: "正在保存页面截图",
  reporting: "正在生成测试报告",
  completed: "执行成功",
  failed: "执行失败",
  step: "正在执行测试步骤",
  action: "正在执行页面操作"
};

const actionTitles: Record<string, string> = {
  open_url: "正在打开页面",
  input: "正在填写输入框",
  click: "正在点击页面元素",
  navigate_menu: "正在导航菜单",
  wait_for_text: "正在等待页面内容",
  assert_text_exists: "正在验证页面内容",
  assert_text_not_exists: "正在验证页面内容不存在",
  assert_url_contains: "正在验证页面地址",
  select: "正在选择下拉选项",
  upload_file: "正在上传文件",
  wait: "正在等待页面稳定",
  confirm_dialog: "正在处理确认弹窗",
  query_table: "正在查询列表数据",
  click_table_row_action: "正在点击表格行操作",
  business_goal: "正在执行业务目标",
  auto_fill_form: "正在自动填写表单"
};

const methodLabels: Record<string, string> = {
  playwright: "Playwright",
  runner: "执行器",
  page_observer: "页面观察",
  element_locator: "元素定位",
  action_verifier: "动作验证",
  report_writer: "报告生成",
  goal_executor: "业务目标",
  llm_element_resolver: "大模型辅助判断",
  vision_resolver: "视觉兜底",
  human_intervention: "人工介入",
  system_login_check: "登录检查",
  login_result_verifier: "登录结果校验",
  auth_state_detector: "登录状态检测",
  protected_step_guard: "受保护步骤守卫",
  global_interruption_handler: "中断处理",
  llm_provider: "大模型",
  natural_language_parser: "测试目标解析",
  json_utils: "结构化数据校验",
  sandbox_provider: "执行环境",
  page_waiter: "页面加载等待",
  menu_path_navigator: "菜单路径导航"
};

export function readableRuntimeTitle(message: RuntimeMessage): string {
  const action = metadataString(message, "action");
  if (action && actionTitles[action]) {
    return actionTitles[action];
  }
  if (message.phase && phaseTitles[message.phase]) {
    return phaseTitles[message.phase];
  }
  if (message.type === "error") return "执行失败";
  if (message.type === "success") return "执行成功";
  return message.content || "运行消息";
}

export function readableRuntimeMessage(message: RuntimeMessage): string {
  const target = metadataString(message, "target");
  const title = readableRuntimeTitle(message);
  if (message.content && !isTechnicalToken(message.content)) {
    if (target && !message.content.includes(target)) {
      return `${message.content}：${target}`;
    }
    return message.content;
  }
  if (message.phase === "locate") {
    return "正在分析页面上的按钮、输入框、菜单和表格，判断哪个元素最符合当前测试目标。";
  }
  if (message.phase === "page_ready") {
    return message.type === "success"
      ? "页面主要内容已经可见，继续执行下一步。"
      : "正在等待页面主体内容、表单、菜单或列表加载完成。";
  }
  if (message.phase === "navigation_path") {
    return message.content || "正在按菜单层级查找并进入目标页面。";
  }
  if (message.phase === "login_result" || message.phase === "auth_guard") {
    return message.content || "正在确认是否已经成功进入目标系统。";
  }
  if (message.phase === "llm_resolver") {
    return "页面存在多个相似操作，正在结合上下文进行判断。";
  }
  if (message.phase === "sandbox_starting") {
    return message.content || "正在准备隔离的浏览器执行环境。";
  }
  if (message.phase === "sandbox_ready") {
    return message.content || "执行环境已经启动完成，可以开始打开被测系统。";
  }
  if (message.phase === "llm_response") {
    return message.content || "大模型回复已接收完成，正在进入结构化处理。";
  }
  if (message.phase === "vision") {
    return "常规页面结构定位置信度不足，正在准备使用截图识别作为兜底。";
  }
  if (target) {
    return `${title}：${target}`;
  }
  return title;
}

export function readableStepAction(step: TestStepRun): string {
  const action = step.action || "";
  return actionTitles[action] || phaseTitles[action] || labelAction(action) || "测试步骤";
}

export function methodLabel(method: string | null): string {
  if (!method) return "系统";
  return methodLabels[method] || "系统";
}

export function runtimeFilterOf(message: RuntimeMessage): RuntimeFilter {
  if (message.type === "error") return "error";
  const text = `${message.phase || ""} ${message.method || ""} ${message.content || ""}`.toLowerCase();
  if (text.includes("vision")) return "vision";
  if (text.includes("llm")) return "llm";
  if (text.includes("semantic") || text.includes("observe") || text.includes("locate") || text.includes("candidate") || text.includes("navigation_path") || text.includes("menu_path")) {
    return "page";
  }
  if (text.includes("page_ready") || text.includes("page_waiter")) return "page";
  return "action";
}

export function runtimeDetailView(message: RuntimeMessage): RuntimeDetailView | null {
  const metadata = message.metadata || {};
  const lines: string[] = [];
  const stepNumber = metadataValue(metadata, "step_number");
  const target = metadataValue(metadata, "target");
  const action = metadataValue(metadata, "action");
  const url = metadataValue(metadata, "url");
  const steps = metadataValue(metadata, "steps");
  const status = metadataValue(metadata, "status");
  const strategy = metadataValue(metadata, "strategy");
  const confidence = metadataValue(metadata, "confidence");
  const fallbackReason = metadataValue(metadata, "fallback_reason");
  const requested = metadataValue(metadata, "requested");
  const summary = metadataValue(metadata, "summary");
  const report = metadataValue(metadata, "report");
  const provider = metadataValue(metadata, "provider");
  const model = metadataValue(metadata, "model");
  const endpoint = metadataValue(metadata, "endpoint");
  const stage = metadataValue(metadata, "stage");
  const stream = metadataValue(metadata, "stream");
  const chunkCount = metadataValue(metadata, "chunkCount");
  const rawLength = metadataValue(metadata, "rawLength");
  const modeLabel = metadataValue(metadata, "mode_label");
  const sandboxStatus = metadataValue(metadata, "sandbox_status");
  const localBrowser = metadataValue(metadata, "local_browser");
  const waitedMs = metadataValue(metadata, "waited_ms");
  const textLength = metadataValue(metadata, "text_length");
  const controlCount = metadataValue(metadata, "control_count");
  const loadingVisible = metadataValue(metadata, "loading_visible");
  const pathSegments = Array.isArray(metadata.pathSegments) ? metadata.pathSegments.map(String) : [];
  const parent = metadataValue(metadata, "parent");
  const leaf = metadataValue(metadata, "leaf");
  const failureType = metadataValue(metadata, "failureType");
  const authState = metadataValue(metadata, "authState");
  const remainingRetries = metadataValue(metadata, "remainingRetries");
  const visionFallback = metadataValue(metadata, "visionFallback");

  if (stepNumber) lines.push(`步骤编号：S${String(stepNumber).padStart(3, "0")}`);
  if (action) lines.push(`执行动作：${actionTitles[String(action)] || labelAction(String(action))}`);
  if (target) lines.push(`操作目标：${target}`);
  if (pathSegments.length > 0) lines.push(`菜单路径：${pathSegments.join(" → ")}`);
  if (parent) lines.push(`一级菜单：${parent}`);
  if (leaf) lines.push(`目标菜单：${leaf}`);
  if (url) lines.push(`访问地址：${url}`);
  if (provider || model) lines.push(`大模型：${[provider, model].filter(Boolean).join(" / ")}`);
  if (endpoint) lines.push(`模型接口：${endpoint}`);
  if (stage) lines.push(`处理阶段：${stage === "plan" ? "测试步骤生成" : "目标分析"}`);
  if (stream !== null && message.method === "llm_provider") lines.push(`流式输出：${stream === "true" ? "开启" : "关闭"}`);
  if (chunkCount) lines.push(`流式片段：${chunkCount} 段`);
  if (rawLength) lines.push(`回复长度：${rawLength} 字符`);
  if (modeLabel) lines.push(`执行环境：${modeLabel}`);
  if (sandboxStatus) lines.push(`环境状态：${sandboxStatus === "ready" ? "已就绪" : "启动中"}`);
  if (localBrowser !== null && message.method === "sandbox_provider") {
    lines.push(`本地浏览器承载：${localBrowser === "true" ? "是" : "否"}`);
  }
  if (waitedMs) lines.push(`页面等待耗时：${waitedMs} 毫秒`);
  if (textLength) lines.push(`页面文本长度：${textLength}`);
  if (controlCount) lines.push(`可操作元素数量：${controlCount}`);
  if (loadingVisible !== null && message.method === "page_waiter") {
    lines.push(`加载遮罩：${loadingVisible === "true" ? "仍可见" : "未发现"}`);
  }
  if (steps) lines.push(`预计步骤数：${steps}`);
  if (status) lines.push(`处理状态：${labelStatus(status)}`);
  if (strategy) lines.push(`定位来源：${locatorStrategyLabel(String(strategy))}`);
  if (confidence) lines.push(`定位置信度：${formatConfidence(confidence)}`);
  if (fallbackReason) lines.push(`兜底原因：${fallbackReason}`);
  if (failureType) lines.push(`失败类型：${labelFailureType(failureType)}`);
  if (authState) lines.push(`登录状态：${labelStatus(authState)}`);
  if (remainingRetries) lines.push(`剩余重试次数：${remainingRetries}`);
  if (visionFallback) lines.push(`视觉兜底：${visionFallback === "true" ? "已启用" : "未启用"}`);
  if (requested !== null && message.phase === "vision") {
    lines.push(`视觉兜底配置：${requested === "true" ? "已开启" : "未开启"}`);
  }
  if (summary) lines.push(`摘要文件：${summary}`);
  if (report) lines.push(`报告文件：${report}`);

  if (lines.length === 0) {
    return null;
  }
  return { lines };
}

export function metadataString(message: RuntimeMessage, key: string): string | null {
  const value = message.metadata[key];
  return typeof value === "string" || typeof value === "number" ? String(value) : null;
}

function metadataValue(metadata: Record<string, unknown>, key: string): string | null {
  const value = metadata[key];
  if (value === undefined || value === null || value === "") return null;
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "string" || typeof value === "number") return String(value);
  return null;
}

function locatorStrategyLabel(value: string): string {
  if (value.startsWith("page_semantic")) return "页面语义定位";
  if (value.startsWith("low_confidence_semantic")) return "低置信度页面语义定位";
  if (value === "playwright_button_exact") return "按钮精确匹配";
  if (value === "playwright_label_exact") return "表单标签精确匹配";
  if (value === "playwright_text_exact") return "文本精确匹配";
  if (value === "explicit_selector") return "显式选择器";
  if (value === "knowledge_base") return "知识库规则";
  if (value === "llm_resolver") return "大模型辅助判断";
  if (value === "vision_fallback") return "视觉兜底";
  if (value === "url") return "页面地址";
  return "自定义定位策略";
}

function formatConfidence(value: string): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return value;
  return `${Math.round(numeric * 100)}%`;
}

function isTechnicalToken(value: string): boolean {
  return /^[a-z0-9_:-]+$/i.test(value.trim());
}
