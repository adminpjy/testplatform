# Prompt01：插件架构

## 目标

建立统一插件机制。

## 插件类型

1. ui_adapter
2. login_adapter
3. browser_provider
4. llm_provider
5. document_parser
6. report_exporter
7. defect_connector
8. data_generator

## 插件字段

1. plugin_code
2. plugin_name
3. plugin_type
4. version
5. config_schema
6. status
7. priority
8. health_check

## 验收

1. 插件可注册、启用、停用。
2. 插件配置有 Schema。

