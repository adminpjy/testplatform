当前项目是“企业 MIS 智能功能测试平台”，不是 NISF，不是 AI 无人项目组，不做代码生成，不做 generated-app，不做 SRS，不做软件工厂。

现在需要重构测试资产管理层级。

最终层级确定为：

项目（被测系统配置）
  ├── 测试账号
  └── 功能测试用例
        ├── DSL
        ├── DSL 版本
        ├── 测试运行记录
        ├── 失败样本
        ├── LLM 错误分析
        └── 修复应用记录

重要设计：
1. 项目就是被测系统测试项目，项目中维护 base_url、login_url、home_url、默认账号、默认执行设置。
2. 测试账号挂在项目下。
3. 功能测试用例挂在项目下。
4. 功能测试用例保存自然语言目标、DSL、测试数据、前置条件、成功判断。
5. 功能测试用例可新增、编辑、删除、复制、停用。
6. 生成的 DSL 必须可以保存至测试用例。
7. DSL 支持编辑、校验、格式化、版本化。
8. 每次测试运行必须关联 project_id、case_id、case_version_id、account_id。
9. 测试运行保存 DSL 快照、测试数据快照、账号快照、执行设置快照。
10. 失败后可以通过 LLM 分析错误并给出修复建议。
11. 修复建议可以应用为：
    - 修改 DSL；
    - 新增规则草案；
    - 修改规则草案；
    - 修改测试数据；
    - 修改测试账号建议；
    - 新增前置条件；
    - 修改成功判断；
    - 发起人工介入；
    - 标记为环境问题；
    - 标记为系统缺陷。
12. 应用 DSL 修改时，不直接覆盖原 DSL，而是创建新的 TestCaseVersion。
13. 修复后可重新运行并验证。

当前步骤不要修改代码。

请先完整分析当前项目结构，重点检查：

后端：
- TestProject / TestSystem / TestAccount / TestCase / TestRun / TestStepRun / FailureSample / AbilityRule / RuleDraft 现有模型；
- projects API；
- systems API；
- test-runs API；
- abilities API；
- failure-samples API；
- LLM Provider；
- prompt 管理；
- DSL 生成和 DslPostProcessor；
- Playwright Executor；
- FailureAnalyzer；
- Runtime Stream；
- Artifact 保存逻辑。

前端：
- 项目管理页面；
- 被测系统管理页面；
- 测试运行页面；
- 能力中心；
- 失败样本页面；
- 报告页面；
- DSL 预览/编辑组件是否存在。

请输出：
1. 当前项目中“项目 / 被测系统 / 测试用例 / 测试运行”的实际关系；
2. 当前是否存在 FunctionalTestCase 或类似表；
3. 当前 DSL 保存在哪里；
4. 当前 TestRun 是否关联测试用例；
5. 当前 FailureSample 是否关联测试用例；
6. 当前是否有 TestCaseVersion；
7. 当前是否有 FailureAnalysis；
8. 当前是否有 FixApplication；
9. 当前前端哪里可以管理测试用例；
10. 需要新增或调整哪些模型；
11. 需要新增或调整哪些 API；
12. 需要新增或调整哪些前端页面；
13. 迁移已有数据的建议；
14. 分阶段实施计划；
15. 每阶段验收标准。

注意：
- 不要修改代码；
- 不要删除任何表；
- 不要删除已有数据；
- 不要改测试执行主链路；
- 只输出分析和计划。