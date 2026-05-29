from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.base import Base
from app.models import HumanIntervention, RuntimeMessage, TestProject as ProjectModel, TestRun as RunModel, TestStepRun as StepRunModel
from app.services.human_interventions import execute_human_intervention


def test_execute_human_intervention_starts_recovery_run(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    project = ProjectModel(project_code="P-HI", name="Project", status="active")
    session.add(project)
    session.flush()
    run = RunModel(run_code="RUN-SOURCE", project_id=project.id, status="failed", dsl_snapshot={"steps": []})
    session.add(run)
    session.flush()
    step = StepRunModel(run_id=run.id, step_id="S003", status="failed", action="wait_for_text", target="工作台")
    session.add(step)
    session.flush()
    intervention = HumanIntervention(
        run_id=run.id,
        step_id=step.id,
        user_instruction="等待页面稳定后重试。",
        status="analyzed",
        llm_plan_json={
            "summary": "等待页面稳定后重试原步骤。",
            "steps": [
                {"action": "wait", "value": "1000", "reason": "等待页面稳定"},
                {"action": "retry_step", "target": "S003", "reason": "重试原失败步骤"},
            ],
            "safety_notes": [],
        },
    )
    session.add(intervention)
    session.commit()

    def fake_recover(db: Session, run_id: int, *, intervention_id: int, step_run_id: int | None, plan: dict):
        assert run_id == run.id
        assert intervention_id == intervention.id
        assert step_run_id == step.id
        assert plan["steps"][0]["action"] == "wait"
        return SimpleNamespace(id=99, run_code="RUN-RECOVERY")

    monkeypatch.setattr("app.services.test_run_execution.recover_test_run_from_intervention", fake_recover)

    result = execute_human_intervention(session, run_id=run.id, intervention_id=intervention.id)

    assert result.status == "succeeded"
    assert result.execution_result_json["status"] == "recovery_run_started"
    assert result.execution_result_json["recoveryRunId"] == 99
    assert result.execution_result_json["resumeMode"] == "rerun"
    messages = session.query(RuntimeMessage).filter(RuntimeMessage.run_id == run.id).all()
    assert any("已启动恢复运行 RUN-RECOVERY" in str(message.content) for message in messages)


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return Session(bind=engine)
