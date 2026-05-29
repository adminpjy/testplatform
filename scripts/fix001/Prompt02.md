当前项目是“企业 MIS 智能功能测试平台”，不是 NISF，不做代码生成。

现在开始第一阶段：重构测试资产数据模型，建立正式层级：

项目（被测系统配置）
  ├── 测试账号
  └── 功能测试用例

目标：
1. 项目作为被测系统测试项目，保存 URL、登录信息、默认账号和默认执行设置。
2. 测试账号挂在项目下。
3. 功能测试用例挂在项目下。
4. DSL 保存到功能测试用例中。
5. DSL 修改要支持版本。
6. 测试运行必须关联项目、用例、用例版本和账号。
7. 失败样本、失败分析、修复应用都要能关联到用例。

请做增量修改，不要破坏现有测试运行和历史数据。

============================================================
一、调整 TestProject
============================================================

请确保 TestProject 支持以下字段：

- id
- project_code
- project_name
- description

被测系统配置：
- system_name
- base_url
- login_url
- home_url
- auth_type
  username_password / sso / token / other

默认账号：
- default_account_id nullable

默认执行设置：
- default_timeout_ms
- enable_trace_default
- enable_screenshot_default
- enable_dom_snapshot_default
- enable_accessibility_snapshot_default
- enable_vision_fallback_default

状态：
- status
  active / disabled / deleted

时间：
- created_at
- updated_at
- deleted_at nullable

说明：
项目在前端表现为“项目（被测系统）”。
可以保留 TestSystem 表作为底层兼容，但第一阶段前端主概念应改为 Project。
不要强制用户每次再选择独立 TestSystem。

============================================================
二、调整 TestAccount
============================================================

TestAccount 挂在项目下。

字段：
- id
- project_id
- account_name
- username
- password_encrypted 或 secret_ref
- role_name
- description
- allow_read
- allow_write
- allow_approval
- allow_delete
- is_default
- status
  active / disabled / deleted
- created_at
- updated_at
- deleted_at nullable

要求：
1. 一个项目可以有多个测试账号。
2. 一个项目只能有一个默认账号。
3. 密码不得明文输出到日志、Runtime Stream、报告、LLM prompt。
4. 删除账号优先软删除。
5. 功能测试用例默认继承项目默认账号，也可覆盖账号。

============================================================
三、新增 FunctionalTestCase
============================================================

新增模型 FunctionalTestCase。

字段：

基础信息：
- id
- project_id
- case_code
- case_name
- description

来源：
- source_type
  manual / ai_generated / document_extracted / imported / failure_replay
- source_document_id nullable
- source_run_id nullable

测试目标：
- natural_language_goal
- menu_path
- business_intent

账号配置：
- inherit_project_account boolean default true
- account_id nullable

测试配置：
- test_data_json
- preconditions_json
- success_criteria_json
- settings_json
- risk_level

DSL：
- dsl_json
- current_version_id nullable

状态：
- status
  draft / ready / disabled / archived / deleted

运行摘要：
- last_run_id nullable
- last_run_status nullable
- last_run_at nullable
- run_count default 0
- pass_count default 0
- fail_count default 0

时间：
- created_at
- updated_at
- deleted_at nullable

唯一约束：
- 同一 project_id 下 case_code 唯一。
- 同一 project_id 下 active/draft/ready 状态的 case_name 建议不重复。

============================================================
四、新增 TestCaseVersion
============================================================

新增模型 TestCaseVersion。

字段：
- id
- case_id
- version_no
- version_label
- natural_language_goal
- dsl_json
- test_data_json
- preconditions_json
- success_criteria_json
- settings_json
- change_type
  initial_generated / manual_edit / llm_regenerated / failure_analysis_suggestion / rule_based_fix / document_extracted
- change_summary
- source_analysis_id nullable
- source_run_id nullable
- created_at

要求：
1. 新增用例时自动创建 v1。
2. 每次修改 DSL 时创建新版本。
3. 不要直接覆盖历史版本。
4. FunctionalTestCase.current_version_id 指向当前生效版本。
5. TestRun 保存 case_version_id 和 DSL 快照。

============================================================
五、调整 TestRun
============================================================

请确保 TestRun 支持：

- id
- run_code
- project_id
- case_id nullable
- case_version_id nullable
- account_id nullable

运行快照：
- instruction_snapshot
- dsl_snapshot
- test_data_snapshot
- settings_snapshot
- account_snapshot
- base_url_snapshot
- login_url_snapshot
- home_url_snapshot

状态：
- status
  created / analyzing / planned / running / passed / failed / stopped / needs_human
- current_phase
- error_summary
- started_at
- ended_at
- duration_ms
- summary_json
- created_at
- updated_at

要求：
1. 从功能测试用例执行时，必须写 case_id、case_version_id。
2. 临时执行时 case_id 可为空，但可以支持“另存为测试用例”。
3. 执行时保存 DSL 快照，不受后续用例修改影响。

============================================================
六、调整 FailureSample
============================================================

FailureSample 增加：

- project_id
- case_id nullable
- case_version_id nullable
- run_id
- step_id
- failure_type
- failure_summary
- evidence_json
- ai_analysis_json
- suggested_rule_json
- status
- created_at
- updated_at

要求：
1. 从用例执行失败时必须关联 case_id。
2. 可以在用例详情中查看所有失败样本。

============================================================
七、新增 FailureAnalysis
============================================================

新增模型 FailureAnalysis。

字段：
- id
- project_id
- case_id nullable
- case_version_id nullable
- run_id
- failure_sample_id

分析状态：
- analysis_status
  pending / analyzing / completed / failed

分析结果：
- failure_category
- root_cause
- confidence
- evidence_json
- suggestions_json
- recommended_actions_json
- risk_level
- requires_human_review

LLM 信息：
- llm_prompt_key
- llm_prompt_version
- llm_model
- llm_provider
- elapsed_ms
- error_summary

时间：
- created_at
- updated_at

============================================================
八、新增 FixApplication
============================================================

新增模型 FixApplication。

字段：
- id
- project_id
- case_id nullable
- run_id nullable
- failure_analysis_id nullable

修复类型：
- fix_type
  modify_dsl
  add_rule
  update_rule
  modify_test_data
  modify_account
  add_precondition
  modify_success_criteria
  human_intervention
  environment_issue
  defect_candidate

状态：
- status
  pending / applied / rejected / verified / failed

快照：
- before_snapshot_json
- after_snapshot_json

结果：
- created_case_version_id nullable
- created_rule_draft_id nullable
- verify_run_id nullable
- reason
- created_at
- applied_at
- verified_at

要求：
1. 应用 DSL 修改时创建新的 TestCaseVersion。
2. 新增规则时创建 RuleDraft，不直接启用。
3. 应用修复后可重新运行并关联 verify_run_id。

============================================================
九、预留文档提取模型
============================================================

为后续“从文档中提取并生成测试用例”预留模型。

DocumentSource：
- id
- project_id
- file_name
- file_path
- doc_type
- status
- created_at
- updated_at

ExtractedTestCaseDraft：
- id
- project_id
- document_id
- case_name
- natural_language_goal
- menu_path
- test_data_json
- suggested_account_role
- confidence
- status
  draft / accepted / rejected / converted
- created_case_id nullable
- created_at
- updated_at

第一阶段可以只建表和基础 API，不做真实文档解析。

============================================================
十、兼容和迁移
============================================================

请处理已有数据：

1. 现有 TestProject “默认测试项目”应显示在项目列表中，不隐藏。
2. 不再自动创建隐藏默认项目。
3. 如果已有 TestRun 没有 case_id，允许为空，显示为“临时运行”。
4. 如果已有 TestSystem，可迁移或绑定到 TestProject，但不要强制删除。
5. 已有被测系统配置可以合并到项目配置或保留兼容字段。
6. 已有测试运行和失败样本不能丢失。

============================================================
十一、验收标准
============================================================

请确保：

1. TestProject 支持被测系统配置字段。
2. TestAccount 挂在 project_id 下。
3. FunctionalTestCase 表存在。
4. TestCaseVersion 表存在。
5. TestRun 可以关联 case_id 和 case_version_id。
6. FailureSample 可以关联 case_id。
7. FailureAnalysis 表存在。
8. FixApplication 表存在。
9. DocumentSource 和 ExtractedTestCaseDraft 预留存在。
10. 后端启动自动建表或迁移成功。
11. 旧 TestRun 不受影响。
12. check.ps1 通过。

完成后提交：
git add .
git commit -m "feat: add project-case-run data model with DSL versioning"