# Prompt05：规则 dry-run 与验证

## 目标

规则启用前必须可验证，避免错误规则污染生产执行。

## dry-run 类型

1. 静态验证：
   - JSON Schema 校验。
   - 必填字段校验。
   - 风险等级校验。
   - 作用域校验。

2. 证据验证：
   - 用失败样本 DOM、截图、accessibility tree 验证规则是否能定位目标。

3. 回放验证：
   - 基于运行记录重新执行到失败点。
   - 不执行高风险最终提交。

4. 小范围验证：
   - 只对指定用例启用规则。
   - 验证通过后再提升作用域。

## API

实现：

1. `POST /api/rules/{rule_id}/dry-run`
2. `POST /api/rules/{rule_id}/verify-with-sample`
3. `POST /api/rules/{rule_id}/verify-with-case`
4. `POST /api/rules/{rule_id}/promote-scope`

## 验收标准

1. 规则启用前能看到 dry-run 结果。
2. dry-run 失败时能看到原因。
3. 高风险规则不能跳过验证。
4. 验证结果进入规则历史。

