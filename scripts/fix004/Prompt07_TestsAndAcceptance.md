# Prompt07：fix004 测试与验收

## 测试场景

至少覆盖：

1. 登录页。
2. 门户菜单。
3. 隐藏查询框。
4. 表格查询。
5. 表格逐行处理。
6. 新页面打开详情。
7. iframe 控件。
8. 审批意见填写提交。
9. 确认弹窗。
10. 用户可读错误。

## 命令

```powershell
python -m pytest backend\tests executor\tests -q
npm --prefix frontend run build
```

## 验收

1. 所有测试通过。
2. 过程截图完整。
3. 失败提示用户可理解。
4. 不因某一个系统特殊页面继续扩大硬编码。

