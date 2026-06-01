from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm.provider import LLMRequest
from app.schemas.test_runs import NaturalLanguageTestRequest
from app.services.dsl_post_processor import DslPostProcessor
from app.services.natural_language_parser import NaturalLanguageParser
from app.services.operation_intent_classifier import OperationIntentClassifier
from app.services.prompt_manager import PromptManager


class StaticTestLLMProvider:
    def complete(self, request: LLMRequest) -> str:
        if request.prompt_key == "test_dsl_generation":
            return json.dumps(_test_plan_response(request.user_prompt), ensure_ascii=False)
        return json.dumps(_test_analysis_response(request.user_prompt), ensure_ascii=False)

    def stream_complete(self, request: LLMRequest):
        yield self.complete(request)


def _test_analysis_response(prompt: str) -> dict:
    return {
        "readyToExecute": True,
        "confidence": 0.9,
        "understoodGoal": "测试目标已识别",
        "missingFields": [],
        "clarifyingQuestions": [],
        "assumptions": [],
        "riskLevel": "low",
        "normalizedInstruction": "测试目标已识别",
    }


def _test_plan_response(prompt: str) -> dict:
    instruction = _instruction_from_prompt(prompt)
    steps: list[dict] = []
    test_data: dict = {}
    missing_fields: list[str] = []
    if "登录系统" in instruction:
        steps.append({"action": "business_goal", "target": "登录系统", "intent": "login_system"})
    if "工作台/我的待办" in instruction:
        steps.append(
            {
                "action": "navigate_path",
                "target": "工作台/我的待办",
                "pathSegments": ["工作台", "我的待办"],
                "navigationType": "menu_path",
            }
        )
    if "打开一条我的待办" in instruction:
        steps.append({"action": "open_table_row", "target": "我的待办列表"})
    if "处理所有我的待办" in instruction or "每一条" in instruction:
        steps.append({"action": "process_table_rows", "target": "我的待办列表"})
    if "审批通过" in instruction:
        steps.append({"action": "business_goal", "target": "审批通过当前单据", "intent": "approval_pass"})
    if "查看审批流程" in instruction:
        steps.append({"action": "business_goal", "target": "查看审批流程", "intent": "approval_flow_view"})
    if "新增用户" in instruction:
        steps.append({"action": "business_goal", "target": "新增用户", "intent": "create_record"})
        if "组织机构为信息中心" in instruction:
            test_data["组织机构"] = "信息中心"
        if "负责人张三" in instruction:
            test_data["负责人"] = "张三"
    if "删除用户" in instruction and "用户名" not in instruction:
        missing_fields.append("删除目标记录")
    return {
        "caseName": "静态测试用例",
        "baseUrl": "https://work.example.test/",
        "credentials": {},
        "testData": test_data,
        "settings": {},
        "steps": steps,
        "missingFields": missing_fields,
        "clarifyingQuestions": [],
    }


def _instruction_from_prompt(prompt: str) -> str:
    text = prompt.split("INPUT_JSON:", 1)[-1]
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return str(value.get("instruction") or "")
    return prompt


def test_natural_language_plan_generates_navigate_path() -> None:
    payload = NaturalLanguageTestRequest(
        instruction="登录系统，进入工作台/我的待办，确认页面存在我的待办。",
        base_url="https://work.example.test/",
        credentials={"username": "tester", "secret_ref": "runtime"},
        stream=True,
    )
    dsl = NaturalLanguageParser(provider=StaticTestLLMProvider()).plan(payload)
    assert any(step.get("action") == "navigate_path" and step.get("pathSegments") == ["工作台", "我的待办"] for step in dsl.steps)


def test_natural_language_plan_generates_open_table_row_for_single_todo() -> None:
    payload = NaturalLanguageTestRequest(
        instruction="进入工作台/我的待办，打开一条我的待办。",
        base_url="https://work.example.test/",
        stream=True,
    )
    dsl = NaturalLanguageParser(provider=StaticTestLLMProvider()).plan(payload)
    assert any(step.get("action") == "open_table_row" for step in dsl.steps)
    assert not any(step.get("action") == "process_table_rows" for step in dsl.steps)


def test_natural_language_plan_generates_process_table_rows_only_for_all_todos() -> None:
    payload = NaturalLanguageTestRequest(
        instruction="进入工作台/我的待办，处理所有我的待办，每一条都打开后关闭。",
        base_url="https://work.example.test/",
        stream=True,
    )
    dsl = NaturalLanguageParser(provider=StaticTestLLMProvider()).plan(payload)
    assert any(step.get("action") == "process_table_rows" for step in dsl.steps)


def test_natural_language_plan_builds_todo_batch_approval_row_steps() -> None:
    payload = NaturalLanguageTestRequest(
        instruction="1、登录系统\n2、读取待办列表\n3、逐一点开待办，填写意见“按要求执行”，点击提交",
        base_url="https://work.example.test/",
        stream=True,
    )
    dsl = NaturalLanguageParser(provider=StaticTestLLMProvider()).plan(payload)

    process_steps = [step for step in dsl.steps if step.get("action") == "process_table_rows"]
    assert process_steps
    process_step = process_steps[0]
    row_steps = process_step["loopPolicy"]["rowSteps"]
    assert row_steps[0]["action"] == "business_goal"
    assert row_steps[0]["intent"] == "approval_pass"
    assert row_steps[0]["value"] == "按要求执行"
    assert process_step["loopPolicy"]["openMode"] == "new_page_or_same_page"
    assert not any(str(step.get("target") or "") == "待办表格中的第一行任意列" for step in dsl.steps)


def test_natural_language_plan_generates_approval_pass_business_goal() -> None:
    payload = NaturalLanguageTestRequest(
        instruction="审批通过当前单据，并验证审批成功。",
        base_url="https://work.example.test/",
        stream=True,
    )
    dsl = NaturalLanguageParser(provider=StaticTestLLMProvider()).plan(payload)
    assert any(step.get("action") == "business_goal" and step.get("intent") == "approval_pass" for step in dsl.steps)


def test_natural_language_plan_generates_approval_flow_view_intent() -> None:
    payload = NaturalLanguageTestRequest(
        instruction="查看审批流程，确认流程图出现。",
        base_url="https://work.example.test/",
        stream=True,
    )
    dsl = NaturalLanguageParser(provider=StaticTestLLMProvider()).plan(payload)
    assert any(step.get("action") == "business_goal" and step.get("intent") == "approval_flow_view" for step in dsl.steps)


def test_natural_language_plan_extracts_form_test_data() -> None:
    payload = NaturalLanguageTestRequest(
        instruction="新增用户，组织机构为信息中心，负责人张三。",
        base_url="https://work.example.test/",
        stream=True,
    )
    dsl = NaturalLanguageParser(provider=StaticTestLLMProvider()).plan(payload)
    assert dsl.testData["组织机构"] == "信息中心"
    assert dsl.testData["负责人"] == "张三"
    assert any(step.get("intent") == "create_record" for step in dsl.steps)


def test_natural_language_plan_marks_delete_missing_record_target() -> None:
    payload = NaturalLanguageTestRequest(
        instruction="删除用户。",
        base_url="https://work.example.test/",
        stream=True,
    )
    dsl = NaturalLanguageParser(provider=StaticTestLLMProvider()).plan(payload)
    assert "删除目标记录" in dsl.missingFields
    assert not any(step.get("intent") == "delete_record" for step in dsl.steps)


def test_plan_instruction_instance_number_overrides_stale_test_data() -> None:
    payload = NaturalLanguageTestRequest(
        instruction="1、打开门户\n2、登录用户\n3、打开“工作台/我的待办”\n4、审批实例号“26058”",
        base_url="https://work.example.test/",
        testData={"实例号": "26097"},
        stream=True,
    )
    raw = json.dumps(
        {
            "caseName": "审批待办",
            "baseUrl": "https://work.example.test/",
            "credentials": {},
            "testData": {"实例号": "26097"},
            "settings": {},
            "steps": [
                {"action": "business_goal", "target": "登录用户", "intent": "login_system"},
                {
                    "action": "navigate_path",
                    "target": "工作台/我的待办",
                    "pathSegments": ["工作台", "我的待办"],
                    "navigationType": "menu_path",
                },
                {"action": "business_goal", "target": "审批实例号26097", "intent": "approval_pass"},
            ],
        },
        ensure_ascii=False,
    )

    dsl = NaturalLanguageParser().parse_plan(raw, payload)

    assert dsl.testData["实例号"] == "26058"
    query_steps = [step for step in dsl.steps if step.get("action") == "query_table"]
    open_steps = [step for step in dsl.steps if step.get("action") == "open_table_row"]
    assert query_steps[0]["queryConditions"]["实例号"] == "26058"
    assert open_steps[0]["rowCriteria"]["实例号"] == "26058"
    assert "26097" not in json.dumps(dsl.model_dump(), ensure_ascii=False)


def test_analysis_instruction_instance_number_overrides_stale_test_data_wording() -> None:
    payload = NaturalLanguageTestRequest(
        instruction="审批实例号“26058”",
        base_url="https://work.example.test/",
        testData={"实例号": "26097"},
        stream=True,
    )
    raw = json.dumps(
        {
            "readyToExecute": True,
            "confidence": 0.9,
            "understoodGoal": "审批实例号26058（测试数据中为26097，以测试数据为准）",
            "missingFields": [],
            "clarifyingQuestions": [],
            "assumptions": ["测试数据中为26097，以测试数据为准"],
            "riskLevel": "low",
            "normalizedInstruction": "审批实例号26058（测试数据中为26097，以测试数据为准）",
        },
        ensure_ascii=False,
    )

    analysis = NaturalLanguageParser().parse_analysis(raw, payload)

    assert analysis.normalizedInstruction == "审批实例号“26058”"
    assert analysis.understoodGoal == "审批实例号“26058”"
    assert not any("以测试数据为准" in item for item in analysis.assumptions)
    assert any("以本次目标为准" in item for item in analysis.assumptions)


def test_post_processor_converts_business_goal_path() -> None:
    dsl = {
        "caseName": "case",
        "baseUrl": "",
        "credentials": {},
        "testData": {},
        "settings": {},
        "steps": [{"action": "business_goal", "target": "工作台/我的待办"}],
    }
    normalized = DslPostProcessor().normalize_dsl(dsl)
    step = normalized["steps"][0]
    assert step["action"] == "navigate_path"
    assert step["pathSegments"] == ["工作台", "我的待办"]
    assert step["originalAction"] == "business_goal"
    assert step["preconditions"] == {"authState": "logged_in"}


def test_post_processor_converts_for_each_table_row_to_process_table_rows() -> None:
    normalized = DslPostProcessor().normalize_dsl(
        {"steps": [{"action": "for_each_table_row", "target": "我的待办列表", "maxRows": 10}]}
    )
    step = normalized["steps"][0]
    assert step["action"] == "process_table_rows"
    assert step["loopPolicy"]["maxRows"] == 10
    assert step["originalAction"] == "for_each_table_row"


def test_post_processor_folds_table_row_approval_steps_into_row_steps() -> None:
    normalized = DslPostProcessor().normalize_dsl(
        {
            "testData": {},
            "steps": [
                {"action": "process_table_rows", "target": "我的待办列表"},
                {"action": "click", "target": "待办表格中的第一行任意列"},
                {"action": "fill_form", "target": "审批意见表单", "formData": {"我的意见": "按要求执行"}},
                {"action": "click", "target": "提交按钮"},
            ],
        }
    )

    assert len(normalized["steps"]) == 1
    step = normalized["steps"][0]
    assert step["action"] == "process_table_rows"
    assert step["loopPolicy"]["rowSteps"][0]["value"] == "按要求执行"
    assert step["loopPolicy"]["rowSteps"][0]["intent"] == "approval_pass"


def test_post_processor_converts_approval_clicks_to_business_goals() -> None:
    pass_step = DslPostProcessor().normalize_step({"action": "click", "target": "审批通过"})
    flow_step = DslPostProcessor().normalize_step({"action": "click", "target": "查看审批流程"})
    assert pass_step["action"] == "business_goal"
    assert pass_step["intent"] == "approval_pass"
    assert pass_step["preconditions"] == {"authState": "logged_in"}
    assert flow_step["action"] == "business_goal"
    assert flow_step["intent"] == "approval_flow_view"
    assert flow_step["preconditions"] == {"authState": "logged_in"}


def test_post_processor_adds_auth_precondition_to_business_steps() -> None:
    normalized = DslPostProcessor().normalize_dsl(
        {
            "steps": [
                {"action": "business_goal", "target": "登录系统", "intent": "login_system"},
                {"action": "fill_form", "target": "登录表单"},
                {"action": "query_table", "target": "用户列表"},
                {"action": "fill_form", "target": "新增用户"},
            ],
        }
    )
    assert "preconditions" not in normalized["steps"][0]
    assert "preconditions" not in normalized["steps"][1]
    assert normalized["steps"][2]["preconditions"] == {"authState": "logged_in"}
    assert normalized["steps"][3]["preconditions"] == {"authState": "logged_in"}


def test_post_processor_carries_query_conditions_to_next_table_row_step() -> None:
    normalized = DslPostProcessor().normalize_dsl(
        {
            "steps": [
                {"action": "query_table", "queryConditions": {"实例号": "26097"}, "operationIntent": {"intent": "query_list"}},
                {"action": "open_table_row", "target": "我的待办列表"},
            ],
        }
    )
    assert normalized["steps"][0]["criteria"] == {"实例号": "26097"}
    assert normalized["steps"][1]["rowCriteria"] == {"实例号": "26097"}


def test_post_processor_never_requires_auth_for_open_url() -> None:
    normalized = DslPostProcessor().normalize_dsl(
        {
            "steps": [
                {
                    "action": "open_url",
                    "target": "https://work.example.test/",
                    "operationIntent": {"intent": "fill_form"},
                    "preconditions": {"authState": "logged_in"},
                }
            ]
        }
    )
    assert normalized["steps"][0]["action"] == "open_url"
    assert "preconditions" not in normalized["steps"][0]


def test_post_processor_relaxes_generic_login_success_marker() -> None:
    normalized = DslPostProcessor().normalize_dsl(
        {
            "steps": [
                {"action": "business_goal", "target": "登录系统", "intent": "login_system"},
                {"action": "wait_for_text", "target": "登录成功标识", "text": "工作台"},
                {"action": "navigate_path", "target": "门户首页/应用中心", "pathSegments": ["门户首页", "应用中心"]},
            ],
        }
    )
    marker_step = normalized["steps"][1]
    assert marker_step["action"] == "wait"
    assert marker_step["target"] == "登录后页面稳定"
    assert marker_step["originalAction"] == "wait_for_text"
    assert "text" not in marker_step


def test_post_processor_does_not_require_auth_for_login_stabilization_wait() -> None:
    step = DslPostProcessor().normalize_step(
        {
            "action": "wait",
            "target": "登录后页面稳定",
            "preconditions": {"authState": "logged_in"},
            "operationIntent": {"intent": "enter_page"},
        }
    )
    assert step["action"] == "wait"
    assert "preconditions" not in step


def test_operation_intent_classifies_login_button_before_enter_page_context() -> None:
    result = OperationIntentClassifier().classify(
        action="click",
        target="登录按钮",
        instruction="1、进入门户\n2、用户登录\n3、进入：系统导航/办公自动化/中国石化公文管理系统",
    )
    assert result.intent == "login"
    assert result.intentType == "authentication"


def test_post_processor_keeps_explicit_post_login_assertion() -> None:
    normalized = DslPostProcessor().normalize_dsl(
        {
            "steps": [
                {"action": "click", "target": "Login"},
                {"action": "assert_text_exists", "target": "退出", "description": "登录成功后验证退出入口出现"},
            ],
        }
    )
    assert normalized["steps"][1]["action"] == "assert_text_exists"
    assert normalized["steps"][1]["target"] == "退出"


def test_post_processor_collects_missing_critical_fields() -> None:
    normalized = DslPostProcessor().normalize_dsl(
        {
            "testData": {},
            "steps": [
                {"action": "fill_form", "target": "组织机构"},
                {"action": "fill_form", "target": "审批人"},
                {"action": "upload_file", "target": "附件"},
                {"action": "business_goal", "intent": "delete_record", "target": "删除用户"},
            ],
        }
    )
    assert {"组织机构", "审批人", "上传文件", "删除目标记录"}.issubset(set(normalized["missingFields"]))


def test_post_processor_does_not_treat_url_as_menu_path() -> None:
    step = DslPostProcessor().normalize_step({"action": "click", "target": "https://example.com/a/b"})
    assert step["action"] == "click"
    assert "pathSegments" not in step


def test_post_processor_does_not_treat_single_segment_as_path() -> None:
    step = DslPostProcessor().normalize_step({"action": "business_goal", "target": "工作台"})
    assert step["action"] == "business_goal"
    assert "pathSegments" not in step


def test_post_processor_supports_three_segment_path() -> None:
    step = DslPostProcessor().normalize_step({"action": "navigate_menu", "target": "审批管理/待审批/出差审批"})
    assert step["action"] == "navigate_path"
    assert step["pathSegments"] == ["审批管理", "待审批", "出差审批"]


def test_post_processor_parses_portal_app_path_with_hyphen() -> None:
    step = DslPostProcessor().normalize_step({"action": "business_goal", "target": "进入系统导航-办公自动化-中国石化公文管理系统"})
    assert step["action"] == "navigate_path"
    assert step["pathSegments"] == ["系统导航", "办公自动化", "中国石化公文管理系统"]
    assert step["navigationType"] == "portal_app_path"


def test_post_processor_splits_single_path_segment_list() -> None:
    step = DslPostProcessor().normalize_step(
        {"action": "navigate_path", "target": "系统导航", "pathSegments": ["系统导航-办公自动化-中国石化公文管理系统"]}
    )
    assert step["pathSegments"] == ["系统导航", "办公自动化", "中国石化公文管理系统"]
    assert step["navigationType"] == "portal_app_path"


def test_post_processor_keeps_portal_app_name_hyphen_suffix() -> None:
    step = DslPostProcessor().normalize_step({"action": "navigate_menu", "target": "系统导航-办公自动化-燕山业务流程管理系统-BPM"})
    assert step["action"] == "navigate_path"
    assert step["pathSegments"] == ["系统导航", "办公自动化", "燕山业务流程管理系统-BPM"]


def test_prompt_reload_picks_up_yaml_change(tmp_path: Path) -> None:
    registry = """
registry:
  test_dsl_generation:
    file: dsl-generation.yaml
    key: test_dsl_generation
    enabled: true
    version: "1.0.0"
"""
    prompt_v1 = """
prompts:
  - key: test_dsl_generation
    name: DSL
    version: "1.0.0"
    enabled: true
    variables: [instruction, allowed_actions, input_json]
    output_format: json
    description: v1
    system: "system"
    user: "TASK: plan {{ instruction }} {{ allowed_actions }} {{ input_json }}"
"""
    prompt_v2 = prompt_v1.replace("description: v1", "description: v2")
    (tmp_path / "prompt-registry.yaml").write_text(registry, encoding="utf-8")
    prompt_path = tmp_path / "dsl-generation.yaml"
    prompt_path.write_text(prompt_v1, encoding="utf-8")

    manager = PromptManager(root=tmp_path)
    assert manager.get_prompt("test_dsl_generation")["description"] == "v1"

    prompt_path.write_text(prompt_v2, encoding="utf-8")
    manager.reload()
    assert manager.get_prompt("test_dsl_generation")["description"] == "v2"


def test_prompt_metadata_is_attached_to_plan_request() -> None:
    payload = NaturalLanguageTestRequest(
        instruction="进入工作台/我的待办",
        base_url="https://work.example.test/",
        credentials={"secret_ref": "runtime"},
    )
    request = NaturalLanguageParser().build_plan_request(payload)
    assert request.prompt_key == "test_dsl_generation"
    assert request.prompt_version == "1.0.0"


def test_connectivity_goal_is_ready_when_base_url_is_provided() -> None:
    payload = NaturalLanguageTestRequest(
        instruction="打开真实系统入口，确认页面可访问",
        base_url="https://work.example.test/health",
        stream=True,
    )
    result = NaturalLanguageParser(provider=StaticTestLLMProvider()).analyze(payload)
    assert result.readyToExecute is True
    assert result.missingFields == []
