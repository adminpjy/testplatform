# Prompt01：测试资产模型与资产仓库

## 目标

建立统一测试资产中心，管理用例、规则、页面知识、Prompt、测试数据模板和报告模板。

## 资产类型

1. `test_case`
2. `case_suite`
3. `rule`
4. `page_knowledge`
5. `prompt`
6. `test_data_template`
7. `report_template`
8. `project_template`

## 统一字段

每类资产都要支持：

1. asset_code
2. asset_name
3. asset_type
4. project_id
5. module
6. tags
7. status
8. owner
9. current_version_id
10. latest_published_version_id
11. created_from
12. risk_level
13. description

## 资产状态

1. draft
2. pending_review
3. approved
4. published
5. deprecated
6. archived

## API

1. 创建资产。
2. 查询资产。
3. 查看资产详情。
4. 复制资产。
5. 归档资产。
6. 资产关联关系查询。

## 验收

1. 用例、规则、Prompt 都能进入统一资产中心。
2. 资产有类型、状态、版本、标签。
3. 可以按项目、模块、标签检索资产。

