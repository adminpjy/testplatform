# Prompt03：项目向导与双文件导入

## 目标

把项目初始化变成一个低门槛向导：配置项目、上传两个必备文件、生成初始用例、导入现有系统。

## 修改范围

1. 新增 `backend/app/services/project_wizard.py`
2. 新增 `backend/app/api/project_wizard.py`
3. 修改 `backend/app/api/__init__.py`
4. 补充测试 `backend/tests/test_project_wizard.py`

## API

1. `POST /api/project-wizard/bootstrap`
   - 创建或更新项目。
   - 保存两个输入文件。
   - 生成 `ProjectBootstrapPackage`。
   - 返回初始用例草案。

2. `POST /api/project-wizard/bootstrap/{package_id}/import-cases`
   - 将草案批量导入 `test_cases`。
   - 支持只导入选中的草案。

## 用例生成策略

1. 优先读取前置程序输出格式：
   - JSON 数组。
   - JSON 对象中的 `cases` / `testCases`。
2. 如果不是 JSON，则按文本规则提取：
   - 包含“测试、验证、进入、查询、新增、修改、删除、审批、菜单、/”的行作为候选。
   - 自动识别菜单路径。
3. 输出统一草案：
   - `caseName`
   - `naturalLanguageGoal`
   - `menuPath`
   - `businessIntent`
   - `testData`
   - `riskLevel`
   - `confidence`
4. 导入时生成可执行的最小 DSL：
   - 登录系统。
   - 菜单路径导航。
   - 业务目标或结果断言。

## 验收

1. 可以通过两个文本文件生成草案。
2. 可以批量导入草案为正式用例。
3. 导入的用例包含版本记录和最小 DSL。

