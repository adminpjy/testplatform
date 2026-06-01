# Prompt06：前端项目初始化向导

## 目标

降低使用复杂度，把项目配置、资料上传、用例导入、预扫、批次执行串成一个向导。

## 修改范围

1. `frontend/src/types/platform.ts`
2. `frontend/src/api/platform.ts`
3. `frontend/src/routes/navigation.ts`
4. `frontend/src/App.tsx`
5. 新增 `frontend/src/pages/ProjectWizardPage.tsx`
6. 修改 `frontend/src/styles/app.css`

## 页面要求

1. 顶部导航新增“项目向导”。
2. 向导步骤：
   - 基本配置。
   - 测试账号。
   - 上传两个资料文件。
   - 生成并预览初始用例。
   - 导入用例。
   - 预扫增强。
   - 创建批次执行。
3. 页面必须聚焦操作，不做营销式布局。
4. 状态提示要用户能理解：
   - 哪一步成功。
   - 哪一步需要补充。
   - 哪一步失败以及可以怎么反馈。
5. 不显示密码明文。

## 验收

1. TypeScript 编译通过。
2. 可以通过向导完成项目和用例导入。
3. 可以从向导发起预扫和批次执行。

