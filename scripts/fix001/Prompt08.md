当前项目是“企业 MIS 智能功能测试平台”，不是 NISF，不做代码生成。

现在开始第七阶段：预留从文档提取测试用例的能力。

目标：
后期可以上传操作手册、测试文档、需求文档，由 AI 提取功能测试用例，并保存到项目下。

第一阶段先实现数据模型、页面和基础流程，不要求完整 OCR 或复杂解析。

============================================================
一、DocumentSource API
============================================================

实现：

GET /api/projects/{projectId}/documents
POST /api/projects/{projectId}/documents
GET /api/documents/{documentId}
DELETE /api/documents/{documentId}

上传后保存：
- file_name
- file_path
- doc_type
- status

第一阶段可以只支持 txt / md / docx / pdf 文件保存。
解析可先占位。

============================================================
二、ExtractedTestCaseDraft API
============================================================

实现：

POST /api/documents/{documentId}/extract-test-cases

第一版可以使用 LLM 或 mock fallback，根据文档文本生成测试用例草案。

GET /api/projects/{projectId}/extracted-case-drafts

POST /api/extracted-case-drafts/{draftId}/accept

POST /api/extracted-case-drafts/{draftId}/reject

accept 逻辑：
1. 根据 draft 创建 FunctionalTestCase；
2. 创建 TestCaseVersion v1；
3. source_type=document_extracted；
4. draft.status=converted。

============================================================
三、前端页面
============================================================

在项目详情增加 Tab：

文档与用例提取

功能：
1. 上传文档；
2. 查看文档列表；
3. 点击“提取测试用例”；
4. 查看测试用例草案；
5. 编辑草案；
6. 接受为正式用例；
7. 拒绝草案。

============================================================
四、验收标准
============================================================

请确保：

1. 可以上传文档。
2. 可以看到文档列表。
3. 可以生成测试用例草案。
4. 可以接受草案生成 FunctionalTestCase。
5. 生成的用例出现在项目用例列表。
6. check.ps1 通过。

完成后提交：
git add .
git commit -m "feat: add document-based test case extraction scaffolding"