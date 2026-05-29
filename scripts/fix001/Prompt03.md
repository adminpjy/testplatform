当前项目是“企业 MIS 智能功能测试平台”，不是 NISF，不做代码生成。

现在开始第二阶段：实现项目、测试账号、功能测试用例 CRUD API。

目标：
用户可以维护项目（被测系统配置）、项目下测试账号、项目下功能测试用例，并保存 DSL。

不要重构测试执行主链路。

============================================================
一、项目 API
============================================================

实现或调整：

GET /api/projects
POST /api/projects
GET /api/projects/{projectId}
PUT /api/projects/{projectId}
DELETE /api/projects/{projectId}

项目字段包括：
- project_name
- description
- system_name
- base_url
- login_url
- home_url
- auth_type
- default_timeout_ms
- enable_trace_default
- enable_screenshot_default
- enable_dom_snapshot_default
- enable_accessibility_snapshot_default
- enable_vision_fallback_default
- status

要求：
1. 新增项目时生成 project_code。
2. base_url 不再受 ALLOWED_BASE_URL_PREFIXES 限制。
3. 只做基本 URL 格式校验：http/https。
4. 删除项目优先软删除。
5. 删除项目不删除历史 TestRun。
6. 项目列表返回用例数量、账号数量、最近运行状态。

============================================================
二、项目账号 API
============================================================

实现：

GET /api/projects/{projectId}/accounts
POST /api/projects/{projectId}/accounts
GET /api/accounts/{accountId}
PUT /api/accounts/{accountId}
DELETE /api/accounts/{accountId}
POST /api/accounts/{accountId}/set-default

要求：
1. 账号挂在 project_id 下。
2. 一个项目只能一个默认账号。
3. 返回账号列表时不返回明文密码。
4. 可以设置默认账号。
5. 删除账号为软删除。
6. 如果账号被功能测试用例引用，删除时提示或软删除。
7. 项目详情返回 default_account。

============================================================
三、功能测试用例 API
============================================================

实现：

GET /api/projects/{projectId}/cases
POST /api/projects/{projectId}/cases
GET /api/cases/{caseId}
PUT /api/cases/{caseId}
DELETE /api/cases/{caseId}
POST /api/cases/{caseId}/disable
POST /api/cases/{caseId}/enable
POST /api/cases/{caseId}/copy

FunctionalTestCase 字段：
- case_name
- description
- source_type
- natural_language_goal
- menu_path
- business_intent
- inherit_project_account
- account_id
- test_data_json
- preconditions_json
- success_criteria_json
- settings_json
- dsl_json
- status

要求：
1. 新增用例时创建 TestCaseVersion v1。
2. 修改基础信息不一定创建版本。
3. 修改 DSL / test_data / preconditions / success_criteria / settings 时创建新版本。
4. 删除用例为软删除。
5. 停用用例后不能执行。
6. 复制用例时复制当前版本 DSL 和配置，生成新 case_code。

============================================================
四、DSL 版本 API
============================================================

实现：

GET /api/cases/{caseId}/versions
GET /api/cases/{caseId}/versions/{versionId}
POST /api/cases/{caseId}/versions
POST /api/cases/{caseId}/versions/{versionId}/activate

POST /api/cases/{caseId}/dsl/validate
POST /api/cases/{caseId}/dsl/format
PUT /api/cases/{caseId}/dsl

要求：
1. 可以查看所有 DSL 版本。
2. 可以激活历史版本。
3. validate 返回 DSL 校验错误。
4. format 返回格式化后的 DSL。
5. 更新 DSL 时创建新版本。
6. 不直接覆盖历史版本。

============================================================
五、从自然语言生成 DSL 并保存到用例
============================================================

实现：

POST /api/cases/{caseId}/analyze
POST /api/cases/{caseId}/generate-dsl
POST /api/cases/{caseId}/save-generated-dsl

流程：
1. analyze：分析自然语言目标是否信息足够；
2. generate-dsl：生成 DSL 但不立即覆盖；
3. save-generated-dsl：保存为新的 TestCaseVersion 并更新 current_version_id。

要求：
1. 生成 DSL 后可预览。
2. 用户确认后才保存。
3. 保存时创建版本，source=llm_generated。
4. 支持测试数据 JSON 合并。
5. 支持菜单路径 navigate_path。
6. 支持登录后步骤 preconditions.authState=logged_in。

============================================================
六、运行记录 API
============================================================

实现：

GET /api/cases/{caseId}/runs
GET /api/cases/{caseId}/failure-samples
GET /api/cases/{caseId}/failure-analyses
GET /api/cases/{caseId}/fix-applications

用于用例详情页查看历史运行、失败分析和修复记录。

============================================================
七、验收标准
============================================================

请确保：

1. 可以新增项目。
2. 可以编辑项目 URL 和默认设置。
3. 可以新增项目测试账号。
4. 可以设置默认测试账号。
5. 可以新增功能测试用例。
6. 可以保存 DSL 到测试用例。
7. 修改 DSL 会生成新版本。
8. 可以查看 DSL 历史版本。
9. 可以删除 / 停用用例。
10. 可以复制用例。
11. 可以查看某用例的运行记录。
12. check.ps1 通过。

完成后提交：
git add .
git commit -m "feat: add project account and functional test case APIs"