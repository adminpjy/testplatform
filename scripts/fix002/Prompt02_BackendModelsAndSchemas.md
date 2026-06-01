# Prompt02：后端数据模型与 Schema

## 目标

建立企业级测试活动、项目初始化、预扫、反馈工单的数据基础。

## 修改范围

1. `backend/app/models/entities.py`
2. `backend/app/models/__init__.py`
3. `backend/app/db/init_db.py`
4. 新增 `backend/app/schemas/enterprise.py`

## 实现要求

1. 新增模型：
   - `ProjectBootstrapPackage`
   - `PrescanSession`
   - `TestCampaign`
   - `TestCampaignCase`
   - `MaintenanceFeedback`
2. 不破坏已有表结构；新增表由 `Base.metadata.create_all` 创建。
3. 如需兼容已有库，只在 `ensure_compatible_columns` 添加必要新增列，不删除、不重命名旧列。
4. Schema 要覆盖：
   - 初始化向导请求/响应。
   - 初始用例草案。
   - 预扫请求/响应。
   - 批次创建/读取/报告摘要。
   - 一键反馈创建/读取。
5. 所有敏感字段不得原样返回，密码、API key、token、secret 必须脱敏。

## 验收

1. 后端导入不报错。
2. 新模型在内存 SQLite 上可以 `create_all`。
3. Schema 可被 FastAPI response model 使用。

