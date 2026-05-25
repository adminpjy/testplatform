from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import TestCase, TestProject
from app.schemas.test_runs import AnalyzeResult, NaturalLanguageTestRequest, TestCaseDSL
from app.services.natural_language_parser import NaturalLanguageParser

router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResult)
def analyze_test_goal(payload: NaturalLanguageTestRequest) -> AnalyzeResult:
    return NaturalLanguageParser().analyze(payload)


@router.post("/plan", response_model=TestCaseDSL)
def plan_test_case(payload: NaturalLanguageTestRequest, db: Session = Depends(get_db)) -> TestCaseDSL:
    parser = NaturalLanguageParser()
    analysis = parser.analyze(payload)
    if not analysis.readyToExecute:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=analysis.model_dump(),
        )

    dsl = parser.plan(payload)
    if payload.project_id is not None:
        if db.get(TestProject, payload.project_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
        test_case = TestCase(
            project_id=payload.project_id,
            case_name=dsl.caseName,
            source_type="natural_language",
            instruction=payload.instruction,
            dsl_json=dsl.model_dump(),
            status="draft",
        )
        db.add(test_case)
        db.commit()
    return dsl
