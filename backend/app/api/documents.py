from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.cases import FunctionalTestCaseRead
from app.schemas.documents import DocumentSourceRead, DocumentUploadRequest, ExtractDraftUpdate, ExtractedCaseDraftRead
from app.services.documents import (
    accept_draft,
    create_document,
    delete_document,
    extract_test_case_drafts,
    get_document,
    get_draft,
    list_project_documents,
    list_project_drafts,
    reject_draft,
    update_draft,
)
from app.services.projects import get_project_model

router = APIRouter()


@router.get("/api/projects/{project_id}/documents", response_model=list[DocumentSourceRead])
def read_project_documents(project_id: int, db: Session = Depends(get_db)) -> list[DocumentSourceRead]:
    _project_or_404(db, project_id)
    return list_project_documents(db, project_id)


@router.post("/api/projects/{project_id}/documents", response_model=DocumentSourceRead, status_code=status.HTTP_201_CREATED)
def upload_project_document(
    project_id: int,
    payload: DocumentUploadRequest,
    db: Session = Depends(get_db),
) -> DocumentSourceRead:
    project = _project_or_404(db, project_id)
    try:
        return create_document(db, project, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/api/documents/{document_id}", response_model=DocumentSourceRead)
def read_document(document_id: int, db: Session = Depends(get_db)) -> DocumentSourceRead:
    document = get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return document


@router.delete("/api/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document(document_id: int, db: Session = Depends(get_db)) -> None:
    document = get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    delete_document(db, document)


@router.post("/api/documents/{document_id}/extract-test-cases", response_model=list[ExtractedCaseDraftRead])
def extract_document_test_cases(document_id: int, db: Session = Depends(get_db)) -> list[ExtractedCaseDraftRead]:
    document = get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return extract_test_case_drafts(db, document)


@router.get("/api/projects/{project_id}/extracted-case-drafts", response_model=list[ExtractedCaseDraftRead])
def read_project_case_drafts(project_id: int, db: Session = Depends(get_db)) -> list[ExtractedCaseDraftRead]:
    _project_or_404(db, project_id)
    return list_project_drafts(db, project_id)


@router.put("/api/extracted-case-drafts/{draft_id}", response_model=ExtractedCaseDraftRead)
def update_extracted_draft(
    draft_id: int,
    payload: ExtractDraftUpdate,
    db: Session = Depends(get_db),
) -> ExtractedCaseDraftRead:
    draft = _draft_or_404(db, draft_id)
    return update_draft(db, draft, payload)


@router.post("/api/extracted-case-drafts/{draft_id}/accept", response_model=FunctionalTestCaseRead)
def accept_extracted_draft(draft_id: int, db: Session = Depends(get_db)) -> FunctionalTestCaseRead:
    draft = _draft_or_404(db, draft_id)
    return accept_draft(db, draft)


@router.post("/api/extracted-case-drafts/{draft_id}/reject", response_model=ExtractedCaseDraftRead)
def reject_extracted_draft(draft_id: int, db: Session = Depends(get_db)) -> ExtractedCaseDraftRead:
    draft = _draft_or_404(db, draft_id)
    return reject_draft(db, draft)


def _project_or_404(db: Session, project_id: int):
    project = get_project_model(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


def _draft_or_404(db: Session, draft_id: int):
    draft = get_draft(db, draft_id)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extracted draft not found.")
    return draft
