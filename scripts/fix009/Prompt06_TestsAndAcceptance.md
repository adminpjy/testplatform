# Prompt06：fix009 测试与验收

## 验收

1. 失败分类准确。
2. 缺陷候选生成可用。
3. 去重可用。
4. 外部推送适配器可配置。
5. 修复回归闭环可用。

```powershell
python -m pytest backend\tests executor\tests -q
npm --prefix frontend run build
```

