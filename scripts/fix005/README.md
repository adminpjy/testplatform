# fix005：LLM 自愈闭环与持续成长提示词

## 阶段目标

让平台遇到未知失败时，能够自动收集完整证据、组织提示词、调用 LLM 分析、生成补充规则或用例修复建议、预执行验证，并在无法解决时一键反馈维护。

## 执行顺序

1. `Prompt00_DataBackupAndResetPolicy.md`
2. `Prompt01_FailureEvidencePackage.md`
3. `Prompt02_LlmDiagnosisPromptAndSchema.md`
4. `Prompt03_AutoRuleDraftGeneration.md`
5. `Prompt04_AutoPreExecutionAndSelfHealing.md`
6. `Prompt05_ManualInterventionPlan.md`
7. `Prompt06_MaintenanceFeedbackWorkflow.md`
8. `Prompt07_TestsAndAcceptance.md`

## 数据策略

执行前备份数据库。该阶段不要求兼容历史失败样本、人工介入、LLM 分析和修复记录，可以重建自愈闭环数据结构。
