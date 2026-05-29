当前项目是“企业 MIS 智能功能测试平台”，不是 NISF，不做代码生成。

现在开始第四阶段：实现从功能测试用例发起测试运行，并保存执行快照。

目标：
测试运行必须关联项目、功能测试用例、用例版本、测试账号，并保存 DSL 快照、测试数据快照和设置快照。

============================================================
一、从用例创建 TestRun
============================================================

新增或调整 API：

POST /api/cases/{caseId}/runs

请求：
{
  "caseVersionId": null,
  "accountId": null,
  "testDataOverride": {},
  "settingsOverride": {},
  "runName": ""
}

逻辑：
1. 读取 FunctionalTestCase；
2. 读取 current_version 或指定 version；
3. 确定账号：
   - 如果请求指定 accountId，使用请求账号；
   - 否则如果用例 account_id 存在，使用用例账号；
   - 否则使用项目 default_account_id；
4. 读取项目 base_url / login_url / home_url；
5. 合并测试数据：
   - 用例 test_data_json；
   - 版本 test_data_json；
   - 本次运行 override；
6. 合并 settings；
7. 创建 TestRun；
8. 保存：
   - case_id
   - case_version_id
   - account_id
   - instruction_snapshot
   - dsl_snapshot
   - test_data_snapshot
   - settings_snapshot
   - account_snapshot
   - base_url_snapshot
   - login_url_snapshot
   - home_url_snapshot

然后启动执行。

============================================================
二、临时运行另存为用例
============================================================

保留临时测试目标模式。

新增 API：

POST /api/test-runs/save-as-case

请求：
{
  "runId": "",
  "projectId": "",
  "caseName": "",
  "description": ""
}

逻辑：
1. 读取 run 的 instruction_snapshot、dsl_snapshot、test_data_snapshot、settings_snapshot；
2. 创建 FunctionalTestCase；
3. 创建 TestCaseVersion v1；
4. 关联 source_type=failure_replay 或 manual；
5. 返回 caseId。

============================================================
三、重新运行
============================================================

支持：

POST /api/test-runs/{runId}/rerun
POST /api/cases/{caseId}/rerun-latest
POST /api/cases/{caseId}/versions/{versionId}/run

要求：
1. rerun 原运行时，默认使用原 dsl_snapshot；
2. rerun latest 时，使用用例当前版本；
3. 版本运行时，使用指定版本；
4. 页面上清晰展示是哪种运行方式。

============================================================
四、更新统计
============================================================

TestRun 完成后，更新 FunctionalTestCase：

- last_run_id
- last_run_status
- last_run_at
- run_count
- pass_count
- fail_count

============================================================
五、执行记录关联展示
============================================================

确保：

GET /api/cases/{caseId}/runs

返回：
- run_code
- status
- started_at
- duration_ms
- case_version_id
- account_snapshot.username
- error_summary
- report_url
- trace_url

============================================================
六、Artifact 关联
============================================================

所有 Artifact 仍然按 run_id 保存。
但通过 run 可以追溯到 case_id 和 project_id。

报告中显示：
- 项目名称；
- 用例名称；
- 用例版本；
- 使用账号；
- 使用 DSL 快照。

============================================================
七、验收标准
============================================================

请确保：

1. 可以从用例详情点击“执行”。
2. 执行时自动使用项目 URL。
3. 执行时自动使用项目默认账号或用例覆盖账号。
4. TestRun 关联 case_id。
5. TestRun 关联 case_version_id。
6. TestRun 保存 dsl_snapshot。
7. 修改用例后，历史运行仍可查看旧 DSL。
8. 可以重新运行历史 run。
9. 可以运行最新版本。
10. 可以将临时运行另存为用例。
11. check.ps1 通过。

完成后提交：
git add .
git commit -m "feat: run functional test cases with execution snapshots"