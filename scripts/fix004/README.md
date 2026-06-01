# fix004：页面自适应执行引擎提示词

## 阶段目标

在 fix003 规则中台基础上，升级执行器的页面自适应能力。  
重点解决企业系统中最常见的问题：登录、门户导航、隐藏查询框、列表循环、新页面、iframe、复杂表单、审批面板、弹窗确认。

## 执行顺序

1. `Prompt00_DataBackupAndResetPolicy.md`
2. `Prompt01_PageContextAndProfiler.md`
3. `Prompt02_TableAndQueryAdaptiveEngine.md`
4. `Prompt03_FormDataGenerationEngine.md`
5. `Prompt04_ApprovalWorkflowEngine.md`
6. `Prompt05_PageIframeDialogManager.md`
7. `Prompt06_ProcessEvidenceAndReadableErrors.md`
8. `Prompt07_TestsAndAcceptance.md`

## 数据策略

执行前备份数据库。该阶段不要求兼容历史运行数据或旧执行日志结构，可以围绕 PageContext、过程证据和页面画像重建更合理的数据结构。
