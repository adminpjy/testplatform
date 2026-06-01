# Prompt07：测试与验证

## 目标

验证 fix002 的后端和前端基础功能可用，且不破坏现有执行器能力。

## 执行

1. 运行后端和执行器测试：
   - `python -m pytest backend\tests executor\tests -q`
2. 如前端具备构建脚本，运行：
   - `npm --prefix frontend run build`
3. 检查 git 状态：
   - `git status --short --branch`

## 验收

1. 所有已有测试通过。
2. 新增测试覆盖：
   - 双文件导入。
   - 草案导入用例。
   - 预扫规则草案。
   - 批次创建和摘要。
   - 一键反馈证据包脱敏。
3. 前端构建通过或明确说明无法构建原因。

