# Prompt07：fix003 测试与验收

## 测试范围

补充测试覆盖：

1. 规则创建、审核、启用、停用、回滚。
2. 规则作用域优先级。
3. 规则匹配引擎。
4. 执行器读取规则。
5. dry-run 验证。
6. 高风险规则门禁。
7. 前端构建。

## 命令

执行：

```powershell
python -m pytest backend\tests executor\tests -q
npm --prefix frontend run build
```

## 验收

1. 全量测试通过。
2. 前端构建通过。
3. 至少提供 3 个真实规则样例：
   - 登录规则。
   - 菜单导航规则。
   - 审批规则。
4. 运行记录中能看到规则命中明细。

