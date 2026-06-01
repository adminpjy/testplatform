# Prompt03：规则匹配引擎

## 目标

实现统一规则匹配引擎，执行器和预扫都通过同一套规则选择逻辑获得候选规则。

## 匹配输入

规则匹配输入包括：

1. project_id
2. system_id
3. case_id
4. action
5. business_intent
6. target
7. URL
8. page title
9. page fingerprint
10. DOM 摘要
11. accessibility 摘要
12. visible text
13. iframe/page context
14. risk level

## 匹配逻辑

规则选择顺序：

1. 作用域匹配。
2. 状态匹配：只使用 active/production_enabled 的规则。
3. 类型匹配。
4. 页面匹配。
5. 业务意图匹配。
6. target/别名匹配。
7. 优先级排序。
8. confidence 阈值过滤。

## 输出

每次匹配必须输出：

1. matched_rules
2. rejected_rules
3. reason
4. confidence
5. selected_rule
6. fallback_needed

## 观测性

运行记录中必须保存：

1. 命中的规则 ID。
2. 规则版本。
3. 为什么命中。
4. 为什么拒绝其他候选。
5. 是否触发 LLM 或视觉兜底。

## 验收标准

1. 同一个按钮文字不同的系统可以通过规则别名匹配。
2. 同一路径在不同项目可以有不同规则。
3. 执行日志能看清规则如何影响动作。

