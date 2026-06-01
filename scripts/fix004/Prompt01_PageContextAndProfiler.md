# Prompt01：页面上下文与页面画像

## 目标

建立统一 PageContext 和页面画像能力，解决执行器不知道当前在哪个页面、哪个 iframe、哪个新窗口的问题。

## PageContext 必须包含

1. page id
2. browser context id
3. url
4. title
5. visible text summary
6. active iframe
7. opened pages
8. dialogs
9. screenshot path
10. DOM snapshot path
11. accessibility snapshot path
12. page fingerprint
13. detected page type

## 页面类型

至少识别：

1. login_page
2. portal_home
3. menu_page
4. list_page
5. search_page
6. form_page
7. detail_page
8. approval_page
9. dialog_page
10. error_page
11. unknown_page

## 画像方法

使用多源证据：

1. URL。
2. title。
3. visible text。
4. DOM 结构。
5. 表格数量。
6. 表单控件数量。
7. 按钮文本。
8. iframe 数量。
9. 截图视觉兜底。
10. 规则匹配结果。

## 输出

每一步执行前后都刷新 PageContext，并写入过程日志。

## 验收标准

1. 点击菜单后新开页，系统能切到新页。
2. 进入 iframe 后能正确定位 iframe 内控件。
3. 错误提示能说明当前页面类型。

