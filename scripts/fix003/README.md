# fix003：规则中台与执行器规则化提示词

## 阶段目标

把 fix002 中“预扫生成规则草案”的能力升级为真正可用的企业级规则中台。  
核心目标是：以后遇到不同系统、不同页面、不同按钮文字、不同列表/表单/审批设计时，优先通过规则配置解决，而不是每次改代码。

## 执行顺序

1. `Prompt00_DataBackupAndResetPolicy.md`
2. `Prompt01_RuleCenterArchitecture.md`
3. `Prompt02_RuleLifecycleAndReview.md`
4. `Prompt03_RuleMatchingEngine.md`
5. `Prompt04_ExecutorRuleIntegration.md`
6. `Prompt05_RuleDryRunAndVerification.md`
7. `Prompt06_FrontendRuleCenter.md`
8. `Prompt07_TestsAndAcceptance.md`

## 边界

1. 不接入无边界“理解整个系统”。
2. 不自动修改生产代码。
3. 规则启用必须可审计、可回滚。
4. 高风险动作规则必须人工确认后才能生产启用。
5. 不要求兼容历史数据库结构；执行前备份数据库后，可以清空重建，效果优先。
