# Prompt07：fix005 测试与验收

## 测试范围

覆盖：

1. 失败证据包生成。
2. 敏感信息脱敏。
3. LLM 诊断 JSON 解析。
4. LLM 失败 fallback。
5. 规则草案生成。
6. dry-run。
7. 预执行。
8. 人工介入方案。
9. 一键反馈。

## 命令

```powershell
python -m pytest backend\tests executor\tests -q
npm --prefix frontend run build
```

## 验收

1. 所有测试通过。
2. 失败页面能展示用户可读诊断。
3. 能一键生成规则草案。
4. 能一键预执行验证。
5. 不能自动解决的问题能一键反馈。

