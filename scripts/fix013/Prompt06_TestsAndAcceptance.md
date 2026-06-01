# Prompt06：fix013 测试与验收

```powershell
python -m pytest backend\tests executor\tests -q
npm --prefix frontend run build
```

## 验收

1. 插件注册、启用、停用可用。
2. UI 适配器可被执行器调用。
3. LLM 和浏览器适配器可切换。
4. 报告和缺陷适配器可配置。

