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
