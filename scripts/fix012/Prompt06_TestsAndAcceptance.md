# Prompt06：fix012 测试与验收

```powershell
python -m pytest backend\tests executor\tests -q
npm --prefix frontend run build
```

## 验收

1. 登录和 RBAC 可用。
2. 项目权限隔离可用。
3. 密钥托管和脱敏可用。
4. 高风险门禁可用。
5. 审计可用。

