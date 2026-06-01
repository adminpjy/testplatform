# Prompt06：fix010 测试与验收

```powershell
python -m pytest backend\tests executor\tests -q
npm --prefix frontend run build
```

## 验收

1. 企业、项目、模块看板可用。
2. 失败、缺陷、规则、LLM 指标可用。
3. 风险摘要可生成。

