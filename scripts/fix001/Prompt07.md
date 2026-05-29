当前项目是“企业 MIS 智能功能测试平台”，不是 NISF，不做代码生成。

现在开始第六阶段：实现修复建议应用闭环。

目标：
LLM 错误分析给出建议后，用户可以选择应用建议。
系统应生成 DSL 新版本、规则草案、测试数据变更、账号建议、前置条件变更、成功判断变更等，并支持再次运行验证。

============================================================
一、FixApplication API
============================================================

新增 API：

POST /api/failure-analyses/{analysisId}/apply

请求：
{
  "suggestionIndex": 0,
  "action": "apply_to_dsl | create_rule_draft | modify_test_data | add_precondition | modify_success_criteria | create_human_intervention | mark_environment_issue | create_defect_candidate",
  "confirm": true
}

返回：
{
  "fixApplicationId": "",
  "status": "applied",
  "createdCaseVersionId": null,
  "createdRuleDraftId": null,
  "message": ""
}

GET /api/cases/{caseId}/fix-applications

GET /api/fix-applications/{id}

POST /api/fix-applications/{id}/verify-run

============================================================
二、应用 modify_dsl
============================================================

流程：
1. 读取当前 FunctionalTestCase 和当前 TestCaseVersion；
2. 读取 suggestion.dslPatch；
3. 应用 patch；
4. 生成新 DSL；
5. 校验 DSL；
6. 创建 TestCaseVersion；
7. FunctionalTestCase.current_version_id 指向新版本；
8. 创建 FixApplication；
9. 记录 before_snapshot_json 和 after_snapshot_json；
10. 状态 applied。

注意：
不要直接覆盖原 DSL。

============================================================
三、应用 add_rule
============================================================

流程：
1. 读取 suggestion.ruleDraft；
2. 创建 RuleDraft；
3. 状态 pending_review；
4. 创建 FixApplication；
5. 不直接启用规则。

============================================================
四、应用 update_rule
============================================================

流程：
1. 生成 RuleDraft，类型 update_rule；
2. 保存要修改的 ruleCode 和 patch；
3. 等待人工启用；
4. 不直接改 active 规则。

============================================================
五、应用 modify_test_data
============================================================

流程：
1. 将 suggestedTestData 合并到 FunctionalTestCase.test_data_json；
2. 创建 TestCaseVersion 或配置版本；
3. 创建 FixApplication；
4. 状态 applied。

建议：修改测试数据也生成新版本，便于回溯。

============================================================
六、应用 add_precondition
============================================================

流程：
1. 合并 preconditions 到 FunctionalTestCase.preconditions_json；
2. 创建新 TestCaseVersion；
3. 记录 FixApplication。

============================================================
七、应用 modify_success_criteria
============================================================

流程：
1. 合并 successCriteria；
2. 创建新 TestCaseVersion；
3. 记录 FixApplication。

============================================================
八、人工介入和缺陷
============================================================

human_intervention：
创建 HumanIntervention 草案或跳转人工介入流程。

environment_issue：
标记 FailureSample / FailureAnalysis 为环境问题。

defect_candidate：
生成缺陷草稿，不需要接正式缺陷系统，先保存 defectDraft JSON。

============================================================
九、验证运行
============================================================

FixApplication 应支持：

POST /api/fix-applications/{id}/verify-run

逻辑：
1. 找到关联 case_id；
2. 使用修复后的当前版本；
3. 创建新的 TestRun；
4. 执行；
5. 将 verify_run_id 写入 FixApplication；
6. 如果通过，FixApplication.status=verified；
7. 如果失败，status=failed。

============================================================
十、前端修复历史
============================================================

在用例详情“修复历史”Tab 中展示：

- 修复类型；
- 来源分析；
- 应用状态；
- 创建的新 DSL 版本；
- 规则草案；
- 验证运行；
- 是否通过；
- 时间；
- 操作：查看详情、重新验证。

============================================================
十一、验收标准
============================================================

请确保：

1. modify_dsl 建立新 TestCaseVersion。
2. add_rule 建立 RuleDraft。
3. modify_test_data 建立新版本或记录。
4. add_precondition 建立新版本。
5. modify_success_criteria 建立新版本。
6. FixApplication 入库。
7. 可以重新运行验证修复。
8. 用例详情能看到修复历史。
9. 历史 DSL 不被覆盖。
10. check.ps1 通过。

完成后提交：
git add .
git commit -m "feat: add repair suggestion application workflow"