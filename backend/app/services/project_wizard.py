from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import ProjectBootstrapPackage, TestCase, TestProject
from app.schemas.cases import FunctionalTestCaseCreate
from app.schemas.enterprise import (
    ImportBootstrapCasesRequest,
    ImportBootstrapCasesResponse,
    InitialCaseDraft,
    ProjectWizardBootstrapRequest,
)
from app.services.cases import create_case
from app.services.dsl_post_processor import normalize_dsl, parse_menu_path
from app.services.projects import create_project, create_project_account, get_project_model, update_project


def bootstrap_project(db: Session, payload: ProjectWizardBootstrapRequest) -> dict[str, Any]:
    project = _create_or_update_project(db, payload)
    if payload.account:
        _ensure_account(db, project, payload)

    stored_files = [_store_bootstrap_file(project.id, file, index) for index, file in enumerate(payload.files, start=1)]
    draft_sources = _candidate_sources(payload, [file["content"] for file in stored_files])
    drafts = _normalize_drafts(draft_sources)
    package = ProjectBootstrapPackage(
        project_id=project.id,
        package_code=_package_code(),
        status="draft_generated",
        source_type=payload.sourceType,
        file_a_name=stored_files[0]["file_name"],
        file_a_path=stored_files[0]["path"],
        file_a_role=stored_files[0]["role"],
        file_b_name=stored_files[1]["file_name"],
        file_b_path=stored_files[1]["path"],
        file_b_role=stored_files[1]["role"],
        generator_result_json={"value": payload.generatorResult} if payload.generatorResult is not None else None,
        draft_cases_json={"items": [draft.model_dump() for draft in drafts]},
        summary_json={
            "draftCount": len(drafts),
            "sourceType": payload.sourceType,
            "fileNames": [item["file_name"] for item in stored_files],
        },
    )
    db.add(package)
    db.commit()
    db.refresh(package)
    return {
        "projectId": project.id,
        "package": package,
        "drafts": drafts,
        "summary": package.summary_json or {},
    }


def import_bootstrap_cases(
    db: Session,
    package_id: int,
    payload: ImportBootstrapCasesRequest,
) -> ImportBootstrapCasesResponse:
    package = db.get(ProjectBootstrapPackage, package_id)
    if package is None:
        raise ValueError("Bootstrap package not found.")
    project = get_project_model(db, package.project_id)
    if project is None:
        raise ValueError("Project not found.")

    draft_items = _package_drafts(package)
    selected_indexes = set(payload.draftIndexes or [int(item.get("index", 0)) for item in draft_items])
    imported_case_ids: list[int] = []
    skipped_indexes: list[int] = []
    for item in draft_items:
        draft = InitialCaseDraft.model_validate(item)
        if draft.index not in selected_indexes:
            skipped_indexes.append(draft.index)
            continue
        case = create_case(db, project, _case_payload_from_draft(project, draft, activate=payload.activate))
        imported_case_ids.append(case.id)

    package.status = "imported" if imported_case_ids else "draft_generated"
    package.imported_case_ids_json = {"items": imported_case_ids}
    package.summary_json = {
        **(package.summary_json or {}),
        "importedCount": len(imported_case_ids),
        "skippedCount": len(skipped_indexes),
    }
    db.add(package)
    db.commit()
    db.refresh(package)
    return ImportBootstrapCasesResponse(
        packageId=package.id,
        projectId=package.project_id,
        importedCaseIds=imported_case_ids,
        skippedIndexes=skipped_indexes,
        summary=package.summary_json or {},
    )


def get_bootstrap_package(db: Session, package_id: int) -> ProjectBootstrapPackage | None:
    return db.get(ProjectBootstrapPackage, package_id)


def _create_or_update_project(db: Session, payload: ProjectWizardBootstrapRequest) -> TestProject:
    project_code = payload.project.project_code
    existing = None
    if project_code:
        existing = db.scalars(
            select(TestProject).where(
                TestProject.project_code == project_code,
                TestProject.deleted_at.is_(None),
                TestProject.status != "deleted",
            )
        ).first()
    if existing is not None:
        update_project(db, existing, payload.project)
        db.refresh(existing)
        return existing
    created = create_project(db, payload.project)
    project = get_project_model(db, int(created["id"]))
    if project is None:
        raise ValueError("Project creation failed.")
    return project


def _ensure_account(db: Session, project: TestProject, payload: ProjectWizardBootstrapRequest) -> None:
    if payload.account is None:
        return
    create_project_account(db, project, payload.account)


def _store_bootstrap_file(project_id: int, file_payload: Any, index: int) -> dict[str, str]:
    directory = Path(settings.data_dir) / "bootstrap" / str(project_id)
    directory.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_.\-\u4e00-\u9fff]+", "_", file_payload.file_name).strip("_")
    safe_name = safe_name or f"bootstrap-{index}.txt"
    path = directory / f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}-{safe_name}"
    path.write_text(file_payload.content or "", encoding="utf-8")
    return {
        "file_name": file_payload.file_name,
        "role": file_payload.role,
        "path": str(path.as_posix()),
        "content": file_payload.content or "",
    }


def _candidate_sources(payload: ProjectWizardBootstrapRequest, file_texts: list[str]) -> list[dict[str, Any]]:
    explicit = _cases_from_structured(payload.generatorResult)
    if explicit:
        return explicit
    for text in file_texts:
        structured = _cases_from_text_json(text)
        if structured:
            return structured
    return _cases_from_plain_text("\n".join(file_texts))


def _cases_from_text_json(text: str) -> list[dict[str, Any]]:
    try:
        return _cases_from_structured(json.loads(text))
    except Exception:
        return []


def _cases_from_structured(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        for key in ("cases", "testCases", "items"):
            if isinstance(value.get(key), list):
                return [item for item in value[key] if isinstance(item, dict)]
        if value.get("caseName") or value.get("case_name") or value.get("naturalLanguageGoal"):
            return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _cases_from_plain_text(text: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip(" \t-#|")
        if not line or line in seen:
            continue
        seen.add(line)
        if not _looks_like_case_line(line):
            continue
        candidates.append(
            {
                "caseName": _case_name_from_text(line),
                "naturalLanguageGoal": line,
                "menuPath": _first_menu_path(line),
                "testData": _extract_inline_test_data(line),
            }
        )
        if len(candidates) >= 2000:
            break
    if not candidates and text.strip():
        candidates.append(
            {
                "caseName": "项目初始功能测试",
                "naturalLanguageGoal": text.strip()[:1000],
                "menuPath": _first_menu_path(text),
                "testData": {},
            }
        )
    return candidates


def _normalize_drafts(candidates: list[dict[str, Any]]) -> list[InitialCaseDraft]:
    drafts: list[InitialCaseDraft] = []
    for index, item in enumerate(candidates, start=1):
        goal = str(
            item.get("naturalLanguageGoal")
            or item.get("natural_language_goal")
            or item.get("goal")
            or item.get("instruction")
            or item.get("caseName")
            or item.get("case_name")
            or ""
        ).strip()
        if not goal:
            continue
        case_name = str(item.get("caseName") or item.get("case_name") or _case_name_from_text(goal)).strip()
        menu_path = item.get("menuPath") or item.get("menu_path") or _first_menu_path(goal)
        risk_level = str(item.get("riskLevel") or item.get("risk_level") or _risk_level(goal))
        test_data = item.get("testData") or item.get("test_data") or item.get("test_data_json") or _extract_inline_test_data(goal)
        drafts.append(
            InitialCaseDraft(
                index=index,
                caseName=case_name[:255],
                naturalLanguageGoal=goal,
                menuPath=str(menu_path) if menu_path else None,
                businessIntent=item.get("businessIntent") or item.get("business_intent") or _business_intent(goal),
                testData=test_data if isinstance(test_data, dict) else {},
                riskLevel=risk_level,
                confidence=_confidence(goal, menu_path),
            )
        )
    return drafts


def _package_drafts(package: ProjectBootstrapPackage) -> list[dict[str, Any]]:
    draft_json = package.draft_cases_json or {}
    items = draft_json.get("items") if isinstance(draft_json, dict) else []
    return [item for item in items if isinstance(item, dict)]


def _case_payload_from_draft(project: TestProject, draft: InitialCaseDraft, *, activate: bool) -> FunctionalTestCaseCreate:
    dsl = _minimal_dsl(project, draft)
    return FunctionalTestCaseCreate(
        case_name=draft.caseName,
        description="由项目初始化向导导入。",
        source_type="bootstrap_import",
        natural_language_goal=draft.naturalLanguageGoal,
        menu_path=draft.menuPath,
        business_intent=draft.businessIntent,
        inherit_project_account=True,
        test_data_json=draft.testData,
        preconditions_json={},
        success_criteria_json=_success_criteria(draft),
        settings_json={"visionFallbackEnabled": bool(project.enable_vision_fallback_default)},
        dsl_json=dsl,
        risk_level=draft.riskLevel,
        status="active" if activate else "draft",
    )


def _minimal_dsl(project: TestProject, draft: InitialCaseDraft) -> dict[str, Any]:
    steps: list[dict[str, Any]] = [
        {"action": "business_goal", "target": "登录系统", "description": "进入统一身份认证页面并完成登录。"}
    ]
    if draft.menuPath:
        steps.append(
            {
                "action": "navigate_path",
                "target": draft.menuPath,
                "pathSegments": parse_menu_path(draft.menuPath),
                "navigationType": "menu_path",
            }
        )
    steps.append({"action": "business_goal", "target": draft.naturalLanguageGoal, "description": draft.caseName})
    return normalize_dsl(
        {
            "caseName": draft.caseName,
            "baseUrl": project.login_url or project.base_url or "",
            "credentials": {},
            "testData": draft.testData,
            "settings": {"visionFallbackEnabled": bool(project.enable_vision_fallback_default)},
            "steps": steps,
        }
    )


def _success_criteria(draft: InitialCaseDraft) -> dict[str, Any]:
    if draft.riskLevel == "high":
        return {"requiresEvidence": True, "expected": "高风险操作完成后必须检测到明确成功提示或状态变化。"}
    return {"requiresEvidence": True, "expected": "页面完成目标操作并出现结果页、列表变化或成功提示。"}


def _looks_like_case_line(line: str) -> bool:
    tokens = ["测试", "验证", "进入", "查询", "新增", "修改", "删除", "审批", "提交", "菜单", "/"]
    return any(token in line for token in tokens) and len(line) >= 4


def _case_name_from_text(text: str) -> str:
    compact = re.sub(r"\s+", " ", text).strip("：:;；,.，。")
    return compact[:60] or "未命名功能测试"


def _first_menu_path(text: str) -> str | None:
    match = re.search(r"[\u4e00-\u9fffA-Za-z0-9_]+(?:\s*(?:/|>|→|\\)\s*[\u4e00-\u9fffA-Za-z0-9_]+)+", text)
    if not match:
        return None
    value = match.group(0)
    return value if parse_menu_path(value) else None


def _extract_inline_test_data(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    quoted = re.findall(r"([\u4e00-\u9fffA-Za-z0-9_]{2,16})[为是：:]\s*[“\"]?([^”\"\s，,。；;]+)[”\"]?", text)
    for key, value in quoted:
        if key in {"目标", "测试", "验证", "进入", "点击"}:
            continue
        data[key] = value
    return data


def _risk_level(text: str) -> str:
    if any(token in text for token in ["删除", "作废", "审批", "提交", "发布", "同意", "驳回"]):
        return "high"
    if any(token in text for token in ["新增", "修改", "上传", "保存", "导入"]):
        return "medium"
    return "low"


def _business_intent(text: str) -> str | None:
    for token in ["审批", "查询", "新增", "修改", "删除", "导入", "导出", "打开", "进入"]:
        if token in text:
            return token
    return None


def _confidence(goal: str, menu_path: Any) -> float:
    score = 0.55
    if menu_path:
        score += 0.15
    if any(token in goal for token in ["查询", "新增", "修改", "删除", "审批", "提交"]):
        score += 0.1
    return min(score, 0.9)


def _package_code() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"BOOT-{stamp}-{uuid4().hex[:6].upper()}"

