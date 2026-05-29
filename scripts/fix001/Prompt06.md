当前项目是“企业 MIS 智能功能测试平台”，不是 NISF，不做代码生成。

现在开始第五阶段：实现 LLM 错误分析和修复建议生成。

目标：
测试失败后，用户可以点击“AI 分析错误”，系统读取完整证据包，通过 LLM 分析失败原因，并给出可操作的修改建议。

============================================================
一、新增 FailureAnalysisService
============================================================

新增服务：

backend/app/services/failure_analysis_service.py

核心方法：

analyze_failure(failure_sample_id) -> FailureAnalysis

输入证据：
1. project 配置；
2. FunctionalTestCase；
3. TestCaseVersion；
4. TestRun；
5. dsl_snapshot；
6. test_data_snapshot；
7. failed step；
8. screenshot；
9. DOM Snapshot；
10. Accessibility Snapshot；
11. Runtime Stream；
12. locator-debug；
13. execution-trace；
14. Playwright Trace 路径；
15. 已命中的规则；
16. 历史运行结果；
17. 账号角色和权限配置。

============================================================
二、LLM 输出结构
============================================================

LLM 必须输出 JSON：

{
  "failureCategory": "",
  "rootCause": "",
  "confidence": 0.0,
  "evidence": [],
  "impact": "",
  "suggestions": [],
  "recommendedActions": [],
  "riskLevel": "low | medium | high",
  "requiresHumanReview": true
}

suggestions 数组中支持以下类型：

1. modify_dsl
2. add_rule
3. update_rule
4. modify_test_data
5. modify_account
6. add_precondition
7. modify_success_criteria
8. human_intervention
9. environment_issue
10. defect_candidate

============================================================
三、建议类型结构
============================================================

modify_dsl：

{
  "type": "modify_dsl",
  "title": "",
  "description": "",
  "dslPatch": {},
  "affectedSteps": [],
  "risk": "low",
  "reason": ""
}

add_rule：

{
  "type": "add_rule",
  "ruleType": "",
  "ruleName": "",
  "ruleDraft": {},
  "reason": "",
  "requiresReview": true
}

update_rule：

{
  "type": "update_rule",
  "ruleCode": "",
  "patch": {},
  "reason": ""
}

modify_test_data：

{
  "type": "modify_test_data",
  "missingFields": [],
  "suggestedTestData": {},
  "reason": ""
}

modify_account：

{
  "type": "modify_account",
  "issue": "",
  "suggestion": "",
  "requiredRole": "",
  "reason": ""
}

add_precondition：

{
  "type": "add_precondition",
  "preconditions": [],
  "reason": ""
}

modify_success_criteria：

{
  "type": "modify_success_criteria",
  "successCriteria": [],
  "reason": ""
}

human_intervention：

{
  "type": "human_intervention",
  "instructionTemplate": "",
  "reason": ""
}

environment_issue：

{
  "type": "environment_issue",
  "issue": "",
  "suggestion": ""
}

defect_candidate：

{
  "type": "defect_candidate",
  "defectTitle": "",
  "defectDescription": "",
  "evidence": []
}

============================================================
四、Prompt 配置
============================================================

将错误分析 Prompt 放入：

config/prompts/failure-analysis.yaml

prompt_key：
failure_analysis

Prompt 要求：
1. 你是企业 MIS 智能功能测试失败分析专家；
2. 必须基于证据判断，不能凭空猜测；
3. 必须优先区分：
   - 登录失败；
   - 认证挑战；
   - 权限不足；
   - 菜单路径问题；
   - 表格识别问题；
   - 表格行操作问题；
   - 表单填写问题；
   - 下拉/日期/组织/人员选择问题；
   - 断言设计问题；
   - 测试数据问题；
   - 被测系统真实缺陷；
   - 环境问题。
4. 必须输出结构化 JSON；
5. 不要输出 Markdown。

============================================================
五、API
============================================================

新增：

POST /api/failure-samples/{failureSampleId}/analyze

返回 FailureAnalysis。

GET /api/failure-analyses/{analysisId}

GET /api/cases/{caseId}/failure-analyses

============================================================
六、前端展示
============================================================

在用例详情的“失败分析”Tab 中：

1. 展示失败样本列表；
2. 点击“AI 分析错误”；
3. 展示分析状态；
4. 展示 rootCause、confidence、evidence；
5. 展示 suggestions；
6. 每条建议旁边显示可操作按钮：
   - 应用到 DSL
   - 生成规则草案
   - 修改测试数据
   - 更新前置条件
   - 修改成功判断
   - 发起人工介入
   - 标记为环境问题
   - 标记为缺陷
   - 忽略建议

============================================================
七、验收标准
============================================================

请确保：

1. 失败样本可以触发 LLM 分析。
2. FailureAnalysis 入库。
3. 分析结果关联 project_id、case_id、run_id、failure_sample_id。
4. LLM 输出结构化 suggestions。
5. 前端能查看分析结果。
6. 前端能看到不同类型建议。
7. 不泄露密码。
8. check.ps1 通过。

完成后提交：
git add .
git commit -m "feat: add LLM failure analysis and repair suggestions"