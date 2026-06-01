# Prompt01：备份与分支

## 目标

在执行 fix002 前保存当前完整程序状态，并创建独立开发分支。

## 执行要求

1. 检查 `git status --short --branch`。
2. 如果工作区有未提交内容，不只创建 HEAD 分支，必须把当前工作区完整保存。
3. 创建备份分支，提交当前工作区：
   - 分支名格式：`backup/fix002-before-YYYYMMDD-HHMMSS`
   - 提交信息：`backup: before fix002 enterprise design implementation`
4. 从备份提交创建开发分支：
   - 分支名格式：`fix/fix002-enterprise-YYYYMMDD-HHMMSS`
5. 记录备份分支和开发分支名称。

## 验收

1. `git status --short --branch` 显示当前位于 fix002 开发分支。
2. 备份分支存在。
3. 当前程序状态可从备份分支恢复。

