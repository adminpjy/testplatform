import type { RuntimeMessage } from "../types/runtime";
import type { TestStepRun } from "../types/platform";

export type RuntimeFilter = "all" | "action" | "page" | "llm" | "vision" | "error";

const phaseTitles: Record<string, string> = {
  understanding: "正在理解测试用例",
  planning: "正在生成测试步骤",
  browser: "正在准备浏览器环境",
  open_system: "正在打开被测系统",
  open_url: "正在打开页面",
  login: "正在登录系统",
  input: "正在填写输入框",
  click: "正在点击页面元素",
  navigate_menu: "正在导航菜单",
  verify: "正在验证执行结果",
  observe: "正在读取页面结构",
  page_reading: "正在读取页面结构",
  page_semantic: "正在分析页面语义",
  locate: "正在分析候选元素",
  candidate_ranker: "正在分析候选元素",
  ambiguity_resolver: "正在处理候选元素冲突",
  llm_action_resolver: "正在调用大模型辅助判断",
  llm_resolver: "正在调用大模型辅助判断",
  llm_request: "正在调用大模型",
  llm_chunk: "正在接收大模型流式输出",
  json_repair: "正在校验结构化 JSON",
  analysis_result: "正在生成分析结论",
  dsl_generated: "正在生成 DSL 步骤",
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
  system_login_check: "登录检查"
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
  if (message.phase === "llm_resolver") {
    return "页面存在多个相似操作，正在结合上下文进行判断。";
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
  return actionTitles[action] || phaseTitles[action] || action || "测试步骤";
}

export function methodLabel(method: string | null): string {
  if (!method) return "系统";
  return methodLabels[method] || method;
}

export function runtimeFilterOf(message: RuntimeMessage): RuntimeFilter {
  if (message.type === "error") return "error";
  const text = `${message.phase || ""} ${message.method || ""} ${message.content || ""}`.toLowerCase();
  if (text.includes("vision")) return "vision";
  if (text.includes("llm")) return "llm";
  if (text.includes("semantic") || text.includes("observe") || text.includes("locate") || text.includes("candidate")) {
    return "page";
  }
  return "action";
}

export function metadataString(message: RuntimeMessage, key: string): string | null {
  const value = message.metadata[key];
  return typeof value === "string" || typeof value === "number" ? String(value) : null;
}

function isTechnicalToken(value: string): boolean {
  return /^[a-z0-9_:-]+$/i.test(value.trim());
}
