# Prompt04：用例驱动预扫与规则草案

## 目标

基于初始用例做低风险预扫，生成页面知识和规则草案，让系统持续沉淀能力。

## 修改范围

1. 新增 `backend/app/services/prescan.py`
2. 新增 `backend/app/api/prescan.py`
3. 修改 `backend/app/api/__init__.py`
4. 补充测试 `backend/tests/test_prescan.py`

## API

1. `POST /api/projects/{project_id}/prescan`
   - 输入 caseIds、mode、dryRun。
   - 创建 `PrescanSession`。
   - 生成预扫计划、规则草案和用例增强建议。

2. `GET /api/prescan-sessions/{session_id}`
   - 查看预扫结果。

## 预扫输出

1. 规则草案：
   - 菜单路径规则。
   - 表格行打开规则。
   - 表单字段规则。
   - 审批意见与提交规则。
   - 成功断言规则。
2. 用例增强建议：
   - 补齐 DSL。
   - 补齐测试数据。
   - 补齐成功标准。
3. 页面知识：
   - 写入 `AbilityKnowledge`，状态为 active 或 candidate。

## 约束

1. 第一阶段不真实提交业务表单。
2. 对审批、删除、作废、发布类动作只生成计划和规则草案，不直接执行。
3. 生成规则草案需标记来源 `prescan_session`。

## 验收

1. 对包含菜单路径的用例能生成 navigation_rule 草案。
2. 对审批语义用例能生成 approval_rule 草案。
3. 能返回用户可读的预扫摘要。

