# Prompt02：资料接入与功能点提取

## 目标

把各种输入资料转成结构化功能点。

## 功能点结构

1. module
2. feature
3. operation
4. menu_path
5. roles
6. data_entities
7. business_rules
8. expected_results
9. risk_level

## LLM 辅助

1. 解析文档中的模块和功能。
2. 提取 CRUD、审批、查询、导入导出、流程流转。
3. 识别权限和角色。
4. 识别测试数据约束。

## 验收

1. 文档能转功能点。
2. 功能点能关联菜单路径和角色。

