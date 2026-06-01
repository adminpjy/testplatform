# Prompt00：数据库备份与清空重建策略

## 背景补充

fix006 是智能维护体验与项目级报告平台升级。  
当前分支不要求兼容历史数据和旧数据库结构。可以清空历史运行数据、规则数据、页面知识、Prompt 配置、报告数据，前提是先备份当前数据库。

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

2. 在执行日志中记录备份目录。
3. 确认备份成功后，允许执行清库、重建表、重构字段。

## 允许

1. 删除不合理旧表。
2. 重建规则、页面知识、Prompt、失败工作台、报告相关表。
3. 调整接口路径和返回结构。
4. 用更简洁的数据结构替代旧 JSON 结构。
5. 不保留旧接口兼容层。

## 目标

1. 新版本体验优先。
2. 非专业人员可维护优先。
3. 项目级报告准确优先。
4. 智能失败处理闭环优先。

