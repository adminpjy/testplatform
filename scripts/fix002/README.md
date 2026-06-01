# fix002 执行说明

本目录保存本次企业级修复的完整设计方案和分步提示词。

执行顺序：

1. `Prompt01_BackupAndBranch.md`
2. `Prompt02_BackendModelsAndSchemas.md`
3. `Prompt03_ProjectWizardImport.md`
4. `Prompt04_PrescanRules.md`
5. `Prompt05_CampaignFeedback.md`
6. `Prompt06_FrontendWizard.md`
7. `Prompt07_TestsVerification.md`

当前实施原则：

1. 不做 Mock。
2. 不做无边界系统理解。
3. 以初始用例为中心，做可控预扫和规则沉淀。
4. 失败必须可读、可分析、可反馈。
5. 生产系统里自动升级只限规则、用例、提示词、页面知识；代码升级走人工审核。

