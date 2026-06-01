# Prompt01：备份、分支与实施范围确认

## 目标

执行 fix006 前，必须保存当前程序状态，并创建独立开发分支。

## 要求

1. 检查当前分支和工作区：

```powershell
git status --short --branch
```

2. 当前如果有未提交内容，先创建备份分支并提交完整工作区：

```text
backup/fix006-before-YYYYMMDD-HHMMSS
```

提交信息：

```text
backup: before fix006 intelligent maintenance experience
```

3. 创建开发分支：

```text
fix/fix006-intelligent-maintenance-YYYYMMDD-HHMMSS
```

## fix006 实施范围

本阶段只做产品化和智能维护升级：

1. 分页、筛选、排序。
2. 失败样本智能工作台。
3. 人工介入记录智能优化。
4. 规则库、页面知识库、Prompt 配置低代码化。
5. 项目级报告总览和下钻。
6. 数据结构可清空重建，历史数据不做兼容迁移。

## 不做

1. 不重写执行器核心逻辑。
2. 不做无边界系统理解。
3. 不自动启用高风险规则。
4. 不用 Mock 代替真实数据。
5. 不做历史运行数据兼容层。

## 验收

1. 备份分支存在。
2. 开发分支存在。
3. 工作范围清晰。
4. 数据库备份存在，后续允许清库重建。
