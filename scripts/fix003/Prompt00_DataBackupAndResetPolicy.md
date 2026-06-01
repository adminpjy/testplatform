# Prompt00：数据库备份与清空重建策略

## 背景补充

当前分支是重要演进分支，但不要求兼容历史运行数据、历史规则、历史页面知识或旧数据库结构。  
本阶段目标是把平台能力做正确、做简洁、做易维护，效果优先。

## 执行前必须做

1. 备份当前数据库：

```powershell
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupDir = "backups/database/$timestamp"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
Copy-Item data/aitp.db $backupDir -Force
if (Test-Path data/aitp.db-wal) { Copy-Item data/aitp.db-wal $backupDir -Force }
if (Test-Path data/aitp.db-shm) { Copy-Item data/aitp.db-shm $backupDir -Force }
```

2. 记录备份目录。
3. 确认备份文件存在。

## 允许的变更

1. 可以清空历史数据。
2. 可以重建数据库表结构。
3. 可以删除不合理的旧字段。
4. 可以重命名旧接口。
5. 可以重构规则、知识、Prompt、报告的数据模型。
6. 可以把旧的 JSON 重配置改成更清晰的结构化模型。

## 不允许的变更

1. 不允许在未备份数据库前执行破坏性变更。
2. 不允许保留明显错误的旧设计只是为了兼容历史数据。
3. 不允许为了兼容旧接口牺牲新版本的易用性和正确性。

## 验收

1. 数据库备份完成。
2. 新结构更简单、更清晰。
3. 新功能效果优先。

