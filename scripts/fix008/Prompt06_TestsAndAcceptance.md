# Prompt06：fix008 测试与验收

## 验收

1. 文档生成功能点。
2. 功能点生成多类型用例。
3. 覆盖缺口分析可用。
4. 前端向导可用。

```powershell
python -m pytest backend\tests executor\tests -q
npm --prefix frontend run build
```

