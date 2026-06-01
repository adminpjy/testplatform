# Prompt06：fix007 测试与验收

## 测试

```powershell
python -m pytest backend\tests executor\tests -q
npm --prefix frontend run build
```

## 验收

1. 资产中心可管理用例、规则、Prompt。
2. 版本、diff、回滚可用。
3. 模板复用可用。
4. 批量审核和发布可用。
5. 高风险批量发布被拦截。

