# Prompt00：备份与数据重建策略

## 目标

fix007 执行前必须备份数据库。本分支不要求兼容历史测试资产数据。

## 执行

```powershell
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupDir = "backups/database/$timestamp"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
Copy-Item data/aitp.db $backupDir -Force
if (Test-Path data/aitp.db-wal) { Copy-Item data/aitp.db-wal $backupDir -Force }
if (Test-Path data/aitp.db-shm) { Copy-Item data/aitp.db-shm $backupDir -Force }
```

## 允许

1. 清空历史用例、规则、知识、Prompt 版本数据。
2. 重建资产模型。
3. 删除不合理旧表和旧字段。
4. 调整接口路径。

## 原则

测试资产可治理、可复用、可回滚优先。

