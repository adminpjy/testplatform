# Prompt02：LLM 诊断提示词与输出 Schema

## 目标

建立稳定、可审计的 LLM 失败诊断提示词，让 LLM 输出结构化结果，避免自由文本不可执行。

## 输入

输入为标准 evidence package。

## LLM 输出 Schema

必须输出 JSON：

```json
{
  "failureCategory": "locator_failed | login_failed | rule_missing | data_missing | permission_issue | environment_issue | system_defect | assertion_failed | unknown",
  "rootCause": "用户可理解的根因",
  "confidence": 0.0,
  "userMessage": "给测试人员看的说明",
  "evidence": [],
  "riskLevel": "low | medium | high",
  "canAutoHeal": false,
  "requiresHumanReview": true,
  "suggestions": [
    {
      "type": "add_rule | modify_dsl | modify_test_data | add_assertion | human_intervention | create_defect",
      "title": "",
      "reason": "",
      "ruleDraft": {},
      "dslPatch": {},
      "testDataPatch": {},
      "interventionPlan": {},
      "verificationPlan": {}
    }
  ],
  "recommendedActions": []
}
```

## 提示词要求

1. 不要暴露敏感信息。
2. 不要编造页面证据。
3. 不确定时降低 confidence。
4. 高风险动作必须要求人工审核。
5. 输出必须能被程序解析。

## 验收标准

1. LLM 失败时有本地 fallback。
2. LLM 输出非法 JSON 时能修复或 fallback。
3. 前端能展示用户可理解说明和建议。

