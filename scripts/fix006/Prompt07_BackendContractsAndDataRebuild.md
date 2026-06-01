# Prompt07：后端接口、数据重建与结构简化

## 目标

为 fix006 提供稳定后端契约。当前分支不要求兼容已有数据，可以清空并重建数据库结构。  
目标是得到更简单、更清晰、更适合智能维护和项目级报告的数据模型。

## 新增/增强接口

### 分页接口

1. `/api/abilities/rules/paged`
2. `/api/abilities/knowledge/paged`
3. `/api/rule-drafts/paged`
4. `/api/failure-samples/paged`
5. `/api/failure-analyses/paged`
6. `/api/human-interventions/paged`
7. `/api/fix-applications/paged`
8. `/api/test-runs/paged`
9. `/api/projects/{project_id}/cases/paged`
10. `/api/prompts/paged`

### 智能失败工作台

1. `/api/failure-workbench/items`
2. `/api/failure-workbench/{sample_id}`
3. `/api/failure-workbench/{sample_id}/analyze`
4. `/api/failure-workbench/{sample_id}/solutions`
5. `/api/failure-workbench/{sample_id}/create-rule-draft`
6. `/api/failure-workbench/{sample_id}/verify`
7. `/api/failure-workbench/{sample_id}/close`

### 配置助手

1. `/api/config-assistant/explain-rule`
2. `/api/config-assistant/generate-rule`
3. `/api/config-assistant/check-rule`
4. `/api/config-assistant/explain-prompt`
5. `/api/config-assistant/optimize-prompt`
6. `/api/config-assistant/test-prompt`

### 项目报告

1. `/api/projects/{project_id}/report-overview`
2. `/api/projects/{project_id}/report-modules`
3. `/api/projects/{project_id}/report-cases`
4. `/api/projects/{project_id}/report-cases/{case_id}`
5. `/api/projects/{project_id}/report-export`

## 数据重建策略

1. 执行前必须备份 `data/aitp.db`。
2. 备份后允许清空历史数据。
3. 允许删除旧字段和旧表。
4. 允许重命名旧接口。
5. 允许用新的结构化模型替代旧 JSON 配置。
6. 不需要写历史数据迁移脚本，除非有明确新版本初始化数据需要生成。
7. 需要提供初始化脚本，创建默认项目、默认规则模板、Prompt 模板和报告分类。

## 性能要求

1. 分页查询必须使用数据库分页。
2. 常用筛选字段加索引。
3. 大字段 JSON 不在列表中全量返回，详情页再加载。
4. 截图和日志只返回路径和摘要。
5. 新结构要减少跨表关系的隐式 JSON 引用，关键关系用显式字段或关联表表达。

## 验收标准

1. 数据库备份已完成。
2. 新分页接口返回统一结构。
3. 报告接口能按项目聚合。
4. 智能分析接口复用当前 LLM 设置。
5. 前端全部切换到新接口。
6. 新结构不为历史数据兼容增加复杂度。
