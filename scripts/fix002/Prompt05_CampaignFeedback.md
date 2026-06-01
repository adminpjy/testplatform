# Prompt05：批次执行、报告摘要与一键反馈

## 目标

支持项目级批量测试，并在失败时一键反馈完整证据包。

## 修改范围

1. 新增 `backend/app/services/campaigns.py`
2. 新增 `backend/app/api/campaigns.py`
3. 新增 `backend/app/services/maintenance_feedback.py`
4. 新增 `backend/app/api/maintenance_feedback.py`
5. 修改 `backend/app/api/__init__.py`
6. 补充测试：
   - `backend/tests/test_campaigns.py`
   - `backend/tests/test_maintenance_feedback.py`

## API

1. `POST /api/projects/{project_id}/campaigns`
   - 创建测试批次。
   - 输入 caseIds、name、runSettings。

2. `POST /api/campaigns/{campaign_id}/start`
   - 批量创建用例运行记录。
   - 第一阶段可以顺序创建后台运行，不阻塞接口等待全部结束。

3. `GET /api/campaigns/{campaign_id}`
   - 返回批次和用例状态。

4. `GET /api/campaigns/{campaign_id}/report-summary`
   - 返回项目级报告摘要。

5. `POST /api/maintenance-feedback`
   - 输入 runId 或 failureSampleId。
   - 生成维护反馈工单。
   - 自动打包运行路径和证据。

## 反馈包必须包含

1. project/case/run/step 基本信息。
2. instruction、DSL、testData、settings、accountSnapshot。
3. step results。
4. artifacts：截图、过程截图、DOM、可访问性树、runtime stream、execution trace、locator debug、report。
5. failure samples 和已有 LLM analysis。
6. 用户可读摘要。

## 验收

1. 可以创建测试批次并启动多个用例运行。
2. 批次摘要能统计 total、queued、running、passed、failed、blocked。
3. 可以对失败运行生成反馈工单，反馈包不泄露密码。

