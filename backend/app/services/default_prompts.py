DEFAULT_PROMPTS = {
    "test_instruction_analysis": {
        "key": "test_instruction_analysis",
        "name": "测试任务信息完整性检查",
        "version": "fallback-1.0.0",
        "enabled": True,
        "model_profile": "default",
        "temperature": 0.2,
        "max_tokens": 8192,
        "output_format": "json",
        "description": "Fallback prompt for natural-language test analysis.",
        "variables": ["input_json"],
        "system": (
            "你是企业 MIS 系统功能测试专家。只能返回 JSON。"
            "不要输出密码、token、authorization 或密钥。"
        ),
        "user": (
            "TASK: analyze\n"
            "If instruction conflicts with testData, the explicit value in instruction has higher priority. "
            "testData is supplemental only.\n"
            "Return JSON matching this schema exactly:\n"
            "{\"readyToExecute\":false,\"confidence\":0.0,\"understoodGoal\":\"\","
            "\"missingFields\":[],\"clarifyingQuestions\":[],\"assumptions\":[],"
            "\"riskLevel\":\"low\",\"normalizedInstruction\":\"\"}\n"
            "INPUT_JSON:\n{{ input_json }}"
        ),
        "file": "default_prompts.py",
    },
    "test_dsl_generation": {
        "key": "test_dsl_generation",
        "name": "自然语言生成测试 DSL",
        "version": "fallback-1.0.0",
        "enabled": True,
        "model_profile": "default",
        "temperature": 0.1,
        "max_tokens": 8192,
        "output_format": "json",
        "description": "Fallback prompt for DSL generation.",
        "variables": ["allowed_actions", "input_json"],
        "system": "你是企业 MIS 测试 DSL 规划器。只能返回 JSON。",
        "user": (
            "TASK: plan\n"
            "Use only these actions: {{ allowed_actions }}.\n"
            "If instruction conflicts with testData, use the explicit value in instruction. testData is supplemental only.\n"
            "菜单路径必须生成 action=navigate_path，并补充 pathSegments 与 navigationType=menu_path。\n"
            "当目标要求逐一/逐条/全部处理待办列表时，必须生成 action=process_table_rows；如果每条待办还要填写意见并提交审批，"
            "把填写意见和提交审批放入 loopPolicy.rowSteps，不要生成“第一行任意列”这类一次性顶层点击步骤。\n"
            "Return JSON matching this schema exactly:\n"
            "{\"caseName\":\"\",\"baseUrl\":\"\",\"credentials\":{},\"testData\":{},\"settings\":{},\"steps\":[]}\n"
            "INPUT_JSON:\n{{ input_json }}"
        ),
        "file": "default_prompts.py",
    },
    "llm_element_resolve": {
        "key": "llm_element_resolve",
        "name": "元素候选定位",
        "version": "fallback-1.0.0",
        "enabled": True,
        "model_profile": "default",
        "temperature": 0.0,
        "max_tokens": 512,
        "output_format": "json",
        "description": "Fallback prompt for element candidate selection.",
        "variables": ["payload_json"],
        "system": "You resolve browser element candidates for functional testing. Return strict JSON only.",
        "user": "{{ payload_json }}",
        "file": "default_prompts.py",
    },
}
