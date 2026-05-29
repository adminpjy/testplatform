from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import DocumentSource, ExtractedTestCaseDraft, TestCase, TestCaseVersion, TestProject
from app.schemas.documents import DocumentUploadRequest, ExtractDraftUpdate
from app.services.dsl_post_processor import normalize_dsl, parse_menu_path


ALLOWED_DOC_TYPES = {"txt", "md", "docx", "pdf"}


def list_project_documents(db: Session, project_id: int) -> list[DocumentSource]:
    return list(
        db.scalars(select(DocumentSource).where(DocumentSource.project_id == project_id).order_by(DocumentSource.id.desc())).all()
    )


def get_document(db: Session, document_id: int) -> DocumentSource | None:
    return db.get(DocumentSource, document_id)


def create_document(db: Session, project: TestProject, payload: DocumentUploadRequest) -> DocumentSource:
    doc_type = _doc_type(payload.file_name, payload.doc_type)
    if doc_type not in ALLOWED_DOC_TYPES:
        raise ValueError("Only txt, md, docx and pdf files are supported in this phase.")
    directory = Path(settings.data_dir) / "documents" / str(project.id)
    directory.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_.\-\u4e00-\u9fff]+", "_", payload.file_name).strip("_") or f"document.{doc_type}"
    file_path = directory / f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}-{safe_name}"
    file_path.write_text(payload.content or "", encoding="utf-8")
    document = DocumentSource(
        project_id=project.id,
        file_name=payload.file_name,
        file_path=str(file_path.as_posix()),
        doc_type=doc_type,
        status="uploaded",
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def delete_document(db: Session, document: DocumentSource) -> None:
    document.status = "deleted"
    db.add(document)
    db.commit()


def extract_test_case_drafts(db: Session, document: DocumentSource) -> list[ExtractedTestCaseDraft]:
    text = _read_document_text(document)
    candidates = _extract_candidates(text, document.file_name)
    drafts: list[ExtractedTestCaseDraft] = []
    for candidate in candidates:
        draft = ExtractedTestCaseDraft(
            project_id=document.project_id,
            document_id=document.id,
            case_name=candidate["case_name"],
            natural_language_goal=candidate["natural_language_goal"],
            menu_path=candidate.get("menu_path"),
            test_data_json=candidate.get("test_data_json") or {},
            suggested_account_role=candidate.get("suggested_account_role"),
            confidence=candidate.get("confidence", 0.55),
            status="draft",
        )
        db.add(draft)
        drafts.append(draft)
    document.status = "extracted"
    db.add(document)
    db.commit()
    for draft in drafts:
        db.refresh(draft)
    return drafts


def list_project_drafts(db: Session, project_id: int) -> list[ExtractedTestCaseDraft]:
    return list(
        db.scalars(
            select(ExtractedTestCaseDraft)
            .where(ExtractedTestCaseDraft.project_id == project_id)
            .order_by(ExtractedTestCaseDraft.id.desc())
        ).all()
    )


def update_draft(db: Session, draft: ExtractedTestCaseDraft, payload: ExtractDraftUpdate) -> ExtractedTestCaseDraft:
    for field_name, value in payload.model_dump(exclude_unset=True).items():
        setattr(draft, field_name, value)
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def accept_draft(db: Session, draft: ExtractedTestCaseDraft) -> TestCase:
    if draft.status == "converted" and draft.created_case_id:
        case = db.get(TestCase, draft.created_case_id)
        if case:
            return case
    dsl = normalize_dsl(
        {
            "caseName": draft.case_name,
            "baseUrl": "",
            "credentials": {},
            "testData": draft.test_data_json or {},
            "settings": {},
            "steps": _steps_from_draft(draft),
        }
    )
    case = TestCase(
        project_id=draft.project_id,
        case_code=f"CASE-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6].upper()}",
        case_name=draft.case_name,
        source_type="document_extracted",
        source_document_id=draft.document_id,
        instruction=draft.natural_language_goal,
        natural_language_goal=draft.natural_language_goal,
        menu_path=draft.menu_path,
        test_data_json=draft.test_data_json or {},
        dsl_json=dsl,
        status="draft",
    )
    db.add(case)
    db.flush()
    version = TestCaseVersion(
        case_id=case.id,
        version_no=1,
        natural_language_goal=case.natural_language_goal,
        dsl_json=case.dsl_json,
        test_data_json=case.test_data_json,
        settings_json={},
        change_type="document_extracted",
        change_summary=f"Extracted from document {draft.document_id}",
    )
    db.add(version)
    db.flush()
    case.current_version_id = version.id
    draft.status = "converted"
    draft.created_case_id = case.id
    db.add_all([case, draft])
    db.commit()
    db.refresh(case)
    return case


def reject_draft(db: Session, draft: ExtractedTestCaseDraft) -> ExtractedTestCaseDraft:
    draft.status = "rejected"
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def get_draft(db: Session, draft_id: int) -> ExtractedTestCaseDraft | None:
    return db.get(ExtractedTestCaseDraft, draft_id)


def _doc_type(file_name: str, declared: str) -> str:
    suffix = Path(file_name).suffix.lower().lstrip(".")
    return suffix or declared.lower()


def _read_document_text(document: DocumentSource) -> str:
    path = Path(document.file_path)
    if not path.exists():
        return ""
    if document.doc_type in {"txt", "md"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    return f"{document.file_name}\n第一阶段暂未解析 {document.doc_type} 正文，请人工编辑提取草案。"


def _extract_candidates(text: str, file_name: str) -> list[dict]:
    lines = [line.strip(" -#\t") for line in text.splitlines() if line.strip()]
    candidates: list[dict] = []
    for line in lines:
        if len(candidates) >= 10:
            break
        if any(token in line for token in ["测试", "验证", "进入", "查询", "新增", "审批", "菜单", "/"]):
            menu_path = _first_menu_path(line)
            candidates.append(
                {
                    "case_name": line[:60],
                    "natural_language_goal": line,
                    "menu_path": menu_path,
                    "test_data_json": {},
                    "confidence": 0.68 if menu_path else 0.55,
                }
            )
    if not candidates:
        candidates.append(
            {
                "case_name": f"{Path(file_name).stem} 提取用例草案",
                "natural_language_goal": f"请根据文档 {file_name} 补充功能测试目标。",
                "menu_path": None,
                "test_data_json": {},
                "confidence": 0.35,
            }
        )
    return candidates


def _first_menu_path(text: str) -> str | None:
    match = re.search(r"[\u4e00-\u9fffA-Za-z0-9_]+(?:\s*(?:/|>|-|→|\\)\s*[\u4e00-\u9fffA-Za-z0-9_]+)+", text)
    if not match:
        return None
    value = match.group(0)
    return value if parse_menu_path(value) else None


def _steps_from_draft(draft: ExtractedTestCaseDraft) -> list[dict]:
    steps: list[dict] = []
    if draft.menu_path:
        steps.append(
            {
                "action": "navigate_path",
                "target": draft.menu_path,
                "pathSegments": parse_menu_path(draft.menu_path),
                "navigationType": "menu_path",
            }
        )
    steps.append({"action": "assert_result", "target": draft.case_name})
    return steps
