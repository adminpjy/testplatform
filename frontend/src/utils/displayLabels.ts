export const statusLabels: Record<string, string> = {
  active: "启用",
  disabled: "停用",
  draft: "草稿",
  archived: "归档",
  created: "已创建",
  planned: "已生成计划",
  analyzing: "分析中",
  running: "运行中",
  passed: "通过",
  failed: "失败",
  pending: "等待中",
  pending_review: "待审核",
  needs_human: "需要人工介入",
  converted: "已转为用例",
  completed: "已完成",
  connected: "已连接",
  enabled: "已启用",
  submitted: "已提交",
  succeeded: "成功",
  blocked: "已阻止",
  aborted: "已中止",
  analyzed: "已分析",
  new: "新建",
  rejected: "已拒绝",
  published: "已发布",
  stopped: "已停止",
  not_started: "未启动",
  ready: "已就绪",
  missing: "缺失",
  success: "成功",
  error: "错误",
  warning: "警告",
  unknown: "未知"
};

export const riskLabels: Record<string, string> = {
  low: "低",
  medium: "中",
  high: "高",
  critical: "严重",
  urgent: "紧急"
};

export const ruleTypeLabels: Record<string, string> = {
  login: "登录",
  authentication: "认证",
  global_interruption: "全局弹窗/中断页",
  dialog_handler: "弹窗处理",
  navigation: "导航路径",
  query: "查询",
  table_detection: "表格识别",
  table_row_action: "表格行操作",
  form_fill: "表单填写",
  form_control: "表单控件",
  dropdown: "下拉选择",
  date_picker: "日期选择",
  org_selector: "组织机构选择",
  person_selector: "人员选择",
  tree_selector: "树节点选择",
  dialog_selector: "弹窗选择",
  file_upload: "文件上传",
  approval_workflow: "审批流程",
  assertion: "断言验证",
  risk_policy: "风险控制",
  vision_fallback: "视觉兜底",
  recovery_policy: "恢复策略"
};

export const actionLabels: Record<string, string> = {
  open_url: "打开地址",
  navigate_path: "按路径导航",
  business_goal: "业务目标",
  click: "点击",
  input: "填写",
  fill: "填写",
  select: "选择",
  choose_radio: "选择单选项",
  close_dialog: "关闭弹窗",
  confirm_dialog: "确认弹窗",
  wait: "等待",
  retry_step: "重试步骤",
  assert_text_exists: "校验文本存在",
  assert_url_contains: "校验地址包含",
  wait_for_text: "等待文本出现",
  query_table: "查询表格",
  query_table_count: "统计表格数量",
  open_table_row: "打开表格行",
  open_row_link_or_detail: "打开行链接或详情",
  click_table_row_action: "点击行内操作",
  auto_fill_form: "自动填写表单",
  fill_form: "填写表单",
  approval_pass: "审批通过",
  view_flow: "查看流程",
  select_dropdown: "选择下拉项",
  select_org: "选择组织机构"
};

export const failureTypeLabels: Record<string, string> = {
  login_failed: "登录失败",
  auth_state_not_logged_in: "未登录",
  authentication_failed: "认证失败",
  protected_step_blocked_by_login_failure: "登录失败后阻止业务步骤",
  protected_step_blocked_by_auth_challenge: "认证挑战阻止业务步骤",
  login_form_fields_not_found: "登录表单识别不完整",
  login_captcha_required: "需要验证码",
  authentication_challenge_required: "需要认证挑战",
  approval_submit_failed: "审批提交失败",
  locator_failed: "元素定位失败",
  vision_fallback_not_configured: "视觉兜底未配置",
  navigation_goal_not_reached: "导航目标未到达",
  table_target_row_not_found: "未找到目标表格行",
  table_no_action_found: "未找到表格行操作",
  click_no_effect: "点击后页面无变化",
  timeout: "等待超时",
  assertion_failed: "断言失败",
  dsl_generation_failed: "测试步骤生成失败"
};

export const environmentLabels: Record<string, string> = {
  dev: "开发环境",
  test: "测试环境",
  uat: "用户验收环境",
  preprod: "预生产环境",
  prod: "生产环境"
};

export const authTypeLabels: Record<string, string> = {
  username_password: "账号密码登录",
  sso: "单点登录",
  token: "令牌认证",
  other: "其他认证方式"
};

export const ruleSourceLabels: Record<string, string> = {
  builtin: "系统内置",
  llm_generated: "大模型生成",
  human: "人工维护",
  imported: "导入",
  failure_sample: "失败样本沉淀"
};

export const knowledgeTypeLabels: Record<string, string> = {
  page: "页面知识",
  locator: "元素定位知识",
  navigation: "导航知识",
  assertion: "断言知识",
  form: "表单知识"
};

export const sourceTypeLabels: Record<string, string> = {
  failure_sample: "失败样本",
  human_intervention: "人工介入",
  llm_analysis: "大模型分析",
  manual: "人工新增"
};

export const scenarioTypeLabels: Record<string, string> = {
  positive: "正向场景",
  negative: "反向场景",
  boundary: "边界场景",
  permission: "权限场景",
  exception: "异常场景"
};

export const ruleConfigKeyLabels: Record<string, string> = {
  trigger_phrases: "触发短语",
  positive_actions: "适用动作",
  negative_actions: "排除动作",
  target_keywords: "目标关键词",
  criteria: "成功判断",
  strategies: "处理策略",
  business_target: "业务目标",
  requires_human: "需要人工确认",
  uses_vision: "使用视觉识别",
  max_retry: "最大重试次数",
  navigation_mode: "导航方式",
  pathSeparator: "路径分隔符",
  successSignals: "成功信号",
  failureSignals: "失败信号",
  alreadyOnTargetCheck: "已在目标页检查",
  pageChangeEvidence: "页面变化证据",
  clickLeafOnly: "只点击末级菜单",
  expandParentMenu: "展开父级菜单",
  tryMenuSearch: "尝试菜单搜索",
  detectPagination: "识别分页器",
  paginationSignals: "分页器特征",
  detectHeaders: "识别表头",
  detectRows: "识别行数据",
  captureEvidence: "保存证据",
  detectEmptyState: "识别空结果",
  doNotTreatAsLocatorFailure: "空结果不视为定位失败",
  actionTexts: "行内操作文本",
  locateRowFirst: "先定位目标行",
  clickActionInRow: "点击行内操作",
  verifyEffect: "验证操作效果",
  refetchRowsEachIteration: "每次循环重新读取行",
  handleDialogAfterRowClick: "行点击后处理弹窗",
  recordProcessedRows: "记录已处理行",
  rankCandidates: "候选项排序",
  penalizeNegativeTexts: "降低排除文本优先级",
  requireMinimumConfidence: "要求最低置信度",
  preferNearestLabel: "优先使用最近标签",
  verifyEditable: "验证可编辑",
  fillUsername: "填写用户名",
  fillPassword: "填写密码",
  clickSubmit: "点击登录",
  redactPassword: "隐藏密码",
  detectMainMenu: "识别主菜单",
  detectHomePage: "识别首页",
  detectUserArea: "识别用户区",
  clickLowRiskContinue: "点击低风险继续",
  continueButtons: "继续按钮文本",
  autoContinueWhenSafeButtonExists: "安全按钮存在时自动继续",
  forceChangePolicy: "强制改密策略",
  policy: "处理策略",
  autoRetry: "自动重试",
  stopOnFailure: "失败后停止",
  reason: "原因",
  blockedAuthStates: "阻止业务步骤的认证状态",
  stopProtectedSteps: "停止受保护业务步骤",
  doNotCallBusinessHandlers: "不调用业务处理器",
  requiresHumanOnCaptcha: "验证码需要人工处理",
  askForValue: "请求输入值",
  doNotPickRandomOption: "不随机选择",
  openSelector: "打开选择器",
  searchIfValueProvided: "有值时搜索",
  expandTree: "展开树",
  selectNode: "选择节点",
  confirmIfNeeded: "需要时确认",
  selectCurrentUserOrgFirst: "优先选择当前用户组织",
  selectPerson: "选择人员",
  verifySelected: "验证已选择",
  askForPerson: "请求选择人员",
  doNotUseRandomPerson: "不随机选人",
  openTree: "打开树",
  searchNode: "搜索节点",
  expandParents: "展开父节点",
  waitForChildren: "等待子节点",
  retrySearch: "重试搜索",
  openDialog: "打开弹窗",
  queryTarget: "查询目标",
  selectTableRow: "选择表格行",
  confirm: "确认",
  verifyBackfill: "验证回填",
  selectRows: "选择多行",
  setInputFiles: "设置上传文件",
  verifyAttachmentList: "验证附件列表",
  clickUploadButton: "点击上传按钮",
  setInputFilesWhenInputAppears: "上传控件出现后设置文件",
  verifyUploadResult: "验证上传结果",
  defaultStart: "默认开始日期",
  defaultEnd: "默认结束日期",
  verifyRange: "验证日期范围",
  must_not_select: "禁止选择规则",
  mustNotTriggerApprovalPass: "不得触发审批通过",
  negativeTextHints: "排除文本提示",
  minimumConfidence: "最低置信度"
};

const strategyLabels: Record<string, string> = {
  request_human_intervention: "请求人工介入",
  human_intervention: "人工介入",
  request_clarification: "请求补充说明",
  request_missing_required_fields: "请求补充必填字段",
  request_test_data: "请求补充测试数据",
  request_file_path: "请求提供文件路径",
  request_person_value: "请求指定人员",
  request_target_values: "请求指定目标值",
  check_login_url: "检查登录地址",
  handle_global_interruption: "处理全局中断",
  retry_submit_once: "重试提交一次",
  wait_for_page_ready: "等待页面稳定",
  handle_login_interruption: "处理登录中断",
  check_test_account: "检查测试账号",
  reset_failed_login_count: "重置失败登录次数",
  human_complete_captcha: "人工完成验证码",
  rerun_login_check: "重新执行登录检查",
  reobserve_page: "重新观察页面",
  expand_parent_menu: "展开父级菜单",
  try_menu_search: "尝试菜单搜索",
  try_iframe_menu: "尝试 iframe 菜单",
  already_on_target_page: "已在目标页面",
  vision_fallback_optional: "可使用视觉兜底",
  retry_by_nearby_label: "按邻近标签重试",
  open_next_tab: "打开下一个页签",
  retry_open_dropdown: "重试打开下拉框",
  scroll_options: "滚动选项",
  search_option_text: "搜索选项文本",
  llm_choose_option: "大模型选择选项",
  vision_fallback: "视觉兜底",
  open_picker: "打开日期控件",
  choose_next_enabled_date: "选择下一个可用日期",
  direct_input_range: "直接输入日期范围",
  picker_select_range: "日期控件选择范围",
  needs_clarification: "需要补充说明",
  expand_more_nodes: "展开更多节点",
  search_node_text: "搜索节点文本",
  retry_expand: "重试展开",
  retry_query: "重试查询",
  select_first_matching_row: "选择第一条匹配行",
  wait_for_table: "等待表格加载",
  try_virtual_grid: "尝试虚拟表格",
  record_empty_result: "记录空结果",
  continue_when_allowed: "允许时继续",
  try_row_link: "尝试行链接",
  try_more_action_menu: "尝试更多操作菜单",
  llm_disambiguation: "大模型消歧",
  ambiguity_resolver: "消歧处理",
  skip_failed_row_when_allowed: "允许时跳过失败行",
  retry_current_row: "重试当前行",
  return_to_list_page: "返回列表页",
  page_semantic: "页面语义定位"
};

export function labelStatus(value: string | null | undefined): string {
  return labelFromMap(statusLabels, value, "未知状态");
}

export function labelRisk(value: string | null | undefined): string {
  return labelFromMap(riskLabels, value, "未知风险");
}

export function labelRuleType(value: string | null | undefined): string {
  return labelFromMap(ruleTypeLabels, value, "其他规则");
}

export function labelRuleTypes(values: string[] | null | undefined): string {
  if (!values || values.length === 0) return "-";
  return values.map(labelRuleType).join(" / ");
}

export function labelAction(value: string | null | undefined): string {
  return labelFromMap(actionLabels, value, "其他动作");
}

export function labelFailureType(value: string | null | undefined): string {
  return labelFromMap(failureTypeLabels, value, "其他失败");
}

export function labelEnvironment(value: string | null | undefined): string {
  return labelFromMap(environmentLabels, value, "其他环境");
}

export function labelAuthType(value: string | null | undefined): string {
  return labelFromMap(authTypeLabels, value, "其他认证方式");
}

export function labelRuleSource(value: string | null | undefined): string {
  return labelFromMap(ruleSourceLabels, value, "其他来源");
}

export function labelKnowledgeType(value: string | null | undefined): string {
  return labelFromMap(knowledgeTypeLabels, value, "其他知识");
}

export function labelSourceType(value: string | null | undefined): string {
  return labelFromMap(sourceTypeLabels, value, "其他来源");
}

export function labelScenarioType(value: string | null | undefined): string {
  return labelFromMap(scenarioTypeLabels, value, "其他场景");
}

export function labelRuleConfigKey(value: string | null | undefined): string {
  return labelFromMap(ruleConfigKeyLabels, value, "自定义配置项");
}

export function labelPromptVariable(value: string): string {
  const labels: Record<string, string> = {
    allowed_actions: "允许动作",
    instruction: "测试目标",
    path_segments: "路径分段",
    target: "目标",
    context_json: "上下文",
    page_context: "页面上下文",
    data_json: "数据",
    systems: "系统列表"
  };
  return labels[value] || labelRuleConfigKey(value);
}

export function labelBoolean(value: boolean | null | undefined): string {
  return value ? "是" : "否";
}

export function labelConfigValue(key: string, value: unknown): string {
  if (value == null) return "";
  if (Array.isArray(value)) {
    return value.map((item) => labelArrayItem(key, item)).join("\n");
  }
  if (typeof value === "boolean") return labelBoolean(value);
  if (typeof value === "string") return labelArrayItem(key, value);
  if (typeof value === "number") return String(value);
  return JSON.stringify(value, null, 2);
}

export function parseConfigDisplayValue(key: string, value: string): unknown {
  const trimmed = value.trim();
  if (!trimmed) return "";
  const lines = value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  if (isListConfigKey(key)) {
    return lines.map((line) => parseListItem(key, line));
  }
  if (trimmed === "是") return true;
  if (trimmed === "否") return false;
  if (/^(\{|\[|true$|false$|null$|-?\d)/.test(trimmed)) {
    try {
      return JSON.parse(trimmed) as unknown;
    } catch {
      return value;
    }
  }
  return parseListItem(key, value);
}

function labelArrayItem(key: string, value: unknown): string {
  const text = String(value);
  if (isActionConfigKey(key)) return labelAction(text);
  if (isStrategyConfigKey(key)) return strategyLabels[text] || labelAction(text);
  return text;
}

function parseListItem(key: string, value: string): string {
  if (isActionConfigKey(key)) return reverseLookup(actionLabels, value) || value;
  if (isStrategyConfigKey(key)) return reverseLookup(strategyLabels, value) || value;
  return value;
}

function isActionConfigKey(key: string): boolean {
  return key.includes("action") || ["positive_actions", "negative_actions", "allowed_actions"].includes(key);
}

function isStrategyConfigKey(key: string): boolean {
  return key.includes("strategy") || key === "strategies" || key.includes("fallback") || key.includes("recovery");
}

function isListConfigKey(key: string): boolean {
  return isActionConfigKey(key) || isStrategyConfigKey(key) || ["trigger_phrases", "target_keywords", "criteria", "successSignals", "failureSignals", "continueButtons", "blockedAuthStates", "paginationSignals", "actionTexts", "negativeTextHints"].includes(key);
}

function labelFromMap(map: Record<string, string>, value: string | null | undefined, fallback: string): string {
  if (!value) return fallback;
  return map[value] || fallback;
}

function reverseLookup(map: Record<string, string>, label: string): string | null {
  const found = Object.entries(map).find(([, display]) => display === label);
  return found?.[0] || null;
}
