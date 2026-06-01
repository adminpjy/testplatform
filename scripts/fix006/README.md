# fix006：智能维护体验与项目级报告平台

## 阶段目标

fix006 面向“企业级可用、非专业人员可维护”的产品化升级。  
当前系统已经有规则库、页面知识库、失败样本、人工介入、Prompt 配置、测试报告等模块，但这些模块更像研发调试工具：列表无分页、配置过于 JSON 化、失败样本偏展示、报告偏单次运行，不利于大规模项目使用。

fix006 的目标是把这些能力升级为：

1. 所有资产列表具备分页、筛选、搜索、排序。
2. 失败样本、人工介入记录升级为智能修复工作台。
3. 规则库、页面知识库、Prompt 配置从 JSON 编辑升级为表单化、向导化、LLM 辅助配置。
4. 测试报告支持按项目总览，并可下钻到模块、用例、运行、步骤、证据。
5. 非专业维护人员能够通过“问题、建议、确认、执行、验证”的流程完成维护升级。

## 执行顺序

1. `Design.md`
2. `Prompt00_DataBackupAndResetPolicy.md`
3. `Prompt01_BackupAndScope.md`
4. `Prompt02_PaginationFoundation.md`
5. `Prompt03_IntelligentFailureWorkbench.md`
6. `Prompt04_GuidedRuleKnowledgePromptConfig.md`
7. `Prompt05_ProjectReportOverviewAndDrilldown.md`
8. `Prompt06_MaintenanceAssistantAndLLMFlows.md`
9. `Prompt07_BackendContractsAndDataRebuild.md`
10. `Prompt08_FrontendExperienceRefactor.md`
11. `Prompt09_TestsAndAcceptance.md`

## 原则

1. 不用 Mock 代替真实系统能力。
2. 不把维护压力转嫁给用户手写 JSON。
3. LLM 辅助必须结构化、可审计、可回滚。
4. 高风险规则、审批、删除、作废、发布类动作必须人工确认。
5. 所有智能建议必须有证据、置信度、影响范围和验证结果。
6. 执行前备份数据库；本分支不要求兼容历史数据和旧结构，可以清空重建。
