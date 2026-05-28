from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm.mock_provider import MockLLMProvider
from app.schemas.test_runs import NaturalLanguageTestRequest
from app.services.dsl_post_processor import DslPostProcessor
from app.services.natural_language_parser import NaturalLanguageParser
from app.services.prompt_manager import PromptManager


def test_natural_language_plan_generates_navigate_path() -> None:
    payload = NaturalLanguageTestRequest(
        instruction="登录系统，进入工作台/我的待办，确认页面存在我的待办。",
        base_url="https://work.example.test/",
        credentials={"username": "tester", "secret_ref": "runtime"},
        stream=True,
    )
    dsl = NaturalLanguageParser(provider=MockLLMProvider()).plan(payload)
    assert any(step.get("action") == "navigate_path" and step.get("pathSegments") == ["工作台", "我的待办"] for step in dsl.steps)


def test_natural_language_plan_generates_open_table_row_for_single_todo() -> None:
    payload = NaturalLanguageTestRequest(
        instruction="进入工作台/我的待办，打开一条我的待办。",
        base_url="https://work.example.test/",
        stream=True,
    )
    dsl = NaturalLanguageParser(provider=MockLLMProvider()).plan(payload)
    assert any(step.get("action") == "open_table_row" for step in dsl.steps)
    assert not any(step.get("action") == "process_table_rows" for step in dsl.steps)


def test_natural_language_plan_generates_process_table_rows_only_for_all_todos() -> None:
    payload = NaturalLanguageTestRequest(
        instruction="进入工作台/我的待办，处理所有我的待办，每一条都打开后关闭。",
        base_url="https://work.example.test/",
        stream=True,
    )
    dsl = NaturalLanguageParser(provider=MockLLMProvider()).plan(payload)
    assert any(step.get("action") == "process_table_rows" for step in dsl.steps)


def test_natural_language_plan_generates_approval_pass_business_goal() -> None:
    payload = NaturalLanguageTestRequest(
        instruction="审批通过当前单据，并验证审批成功。",
        base_url="https://work.example.test/",
        stream=True,
    )
    dsl = NaturalLanguageParser(provider=MockLLMProvider()).plan(payload)
    assert any(step.get("action") == "business_goal" and step.get("intent") == "approval_pass" for step in dsl.steps)


def test_natural_language_plan_generates_approval_flow_view_intent() -> None:
    payload = NaturalLanguageTestRequest(
        instruction="查看审批流程，确认流程图出现。",
        base_url="https://work.example.test/",
        stream=True,
    )
    dsl = NaturalLanguageParser(provider=MockLLMProvider()).plan(payload)
    assert any(step.get("action") == "business_goal" and step.get("intent") == "approval_flow_view" for step in dsl.steps)


def test_natural_language_plan_extracts_form_test_data() -> None:
    payload = NaturalLanguageTestRequest(
        instruction="新增用户，组织机构为信息中心，负责人张三。",
        base_url="https://work.example.test/",
        stream=True,
    )
    dsl = NaturalLanguageParser(provider=MockLLMProvider()).plan(payload)
    assert dsl.testData["组织机构"] == "信息中心"
    assert dsl.testData["负责人"] == "张三"
    assert any(step.get("intent") == "create_record" for step in dsl.steps)


def test_natural_language_plan_marks_delete_missing_record_target() -> None:
    payload = NaturalLanguageTestRequest(
        instruction="删除用户。",
        base_url="https://work.example.test/",
        stream=True,
    )
    dsl = NaturalLanguageParser(provider=MockLLMProvider()).plan(payload)
    assert "删除目标记录" in dsl.missingFields
    assert not any(step.get("intent") == "delete_record" for step in dsl.steps)


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
                {"action": "query_table", "target": "用户列表"},
                {"action": "fill_form", "target": "新增用户"},
            ],
        }
    )
    assert "preconditions" not in normalized["steps"][0]
    assert normalized["steps"][1]["preconditions"] == {"authState": "logged_in"}
    assert normalized["steps"][2]["preconditions"] == {"authState": "logged_in"}


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
    result = NaturalLanguageParser(provider=MockLLMProvider()).analyze(payload)
    assert result.readyToExecute is True
    assert result.missingFields == []
