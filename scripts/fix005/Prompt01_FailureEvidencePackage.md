# Prompt01：失败证据包标准化

## 目标

失败后自动生成完整证据包，供 LLM、维护人员、报告系统复用。

## 证据包必须包含

1. 项目信息。
2. 系统信息。
3. 用例信息。
4. 自然语言测试目标。
5. DSL 快照。
6. 测试数据快照。
7. 设置快照。
8. 账号脱敏快照。
9. 执行步骤列表。
10. 每步结果。
11. 每步过程截图。
12. DOM snapshot。
13. accessibility snapshot。
14. locator debug。
15. runtime stream。
16. execution trace。
17. Playwright 错误。
18. Python 异常栈。
19. LLM 调用摘要。
20. 规则命中与拒绝明细。
21. 当前页面类型和 PageContext。

## 脱敏要求

必须脱敏：

1. password。
2. token。
3. api_key。
4. secret。
5. cookie。
6. authorization。
7. 身份证号、手机号等敏感数据按配置脱敏。

## 验收标准

1. 任意失败都能生成 evidence package。
2. 证据包不泄露敏感信息。
3. LLM 分析和一键反馈使用同一证据包。

