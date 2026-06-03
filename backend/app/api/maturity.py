from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.maturity import (
    AssetCreate,
    AssetRead,
    AssetUpdate,
    AssetVersionRead,
    DefectCreate,
    DefectRead,
    DefectUpdate,
    FailureSampleUpdate,
    GenerateCasesRequest,
    GenerateCasesResponse,
    LearningItemCreate,
    LearningItemRead,
    LearningItemUpdate,
    PageResponse,
    PlatformUserCreate,
    PlatformUserRead,
    PlatformUserUpdate,
    PluginCreate,
    PluginRead,
    PluginUpdate,
    QualityOverview,
)
from app.services import maturity

router = APIRouter()


@router.get("/assets", response_model=PageResponse)
def read_assets(
    page: int = 1,
    page_size: int = 20,
    q: str | None = None,
    asset_type: str | None = None,
    status: str | None = None,
    project_id: int | None = None,
    db: Session = Depends(get_db),
) -> PageResponse:
    return maturity.paged_assets(db, page=page, page_size=page_size, q=q, asset_type=asset_type, status=status, project_id=project_id)


@router.post("/assets", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
def create_asset(payload: AssetCreate, db: Session = Depends(get_db)) -> AssetRead:
    return maturity.create_asset(db, payload)


@router.put("/assets/{asset_id}", response_model=AssetRead)
def update_asset(asset_id: int, payload: AssetUpdate, db: Session = Depends(get_db)) -> AssetRead:
    try:
        return maturity.update_asset(db, asset_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(asset_id: int, db: Session = Depends(get_db)) -> None:
    try:
        maturity.delete_asset(db, asset_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/assets/{asset_id}/versions", response_model=list[AssetVersionRead])
def read_asset_versions(asset_id: int, db: Session = Depends(get_db)) -> list[AssetVersionRead]:
    try:
        return maturity.asset_versions(db, asset_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/assets/{asset_id}/publish", response_model=AssetRead)
def publish_asset(asset_id: int, db: Session = Depends(get_db)) -> AssetRead:
    try:
        return maturity.publish_asset(db, asset_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/assets/{asset_id}/rollback/{version_id}", response_model=AssetRead)
def rollback_asset(asset_id: int, version_id: int, db: Session = Depends(get_db)) -> AssetRead:
    try:
        return maturity.rollback_asset(db, asset_id, version_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/generation/cases", response_model=GenerateCasesResponse)
def generate_test_cases(payload: GenerateCasesRequest) -> GenerateCasesResponse:
    return maturity.generate_cases(payload)


@router.get("/defects", response_model=PageResponse)
def read_defects(
    page: int = 1,
    page_size: int = 20,
    q: str | None = None,
    status: str | None = None,
    project_id: int | None = None,
    db: Session = Depends(get_db),
) -> PageResponse:
    return maturity.paged_defects(db, page=page, page_size=page_size, q=q, status=status, project_id=project_id)


@router.post("/defects", response_model=DefectRead, status_code=status.HTTP_201_CREATED)
def create_defect(payload: DefectCreate, db: Session = Depends(get_db)) -> DefectRead:
    return maturity.create_defect(db, payload)


@router.put("/defects/{defect_id}", response_model=DefectRead)
def update_defect(defect_id: int, payload: DefectUpdate, db: Session = Depends(get_db)) -> DefectRead:
    try:
        return maturity.update_defect(db, defect_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/defects/{defect_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_defect(defect_id: int, db: Session = Depends(get_db)) -> None:
    try:
        maturity.delete_defect(db, defect_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/defects/from-failure/{failure_sample_id}", response_model=DefectRead, status_code=status.HTTP_201_CREATED)
def create_defect_from_failure(failure_sample_id: int, db: Session = Depends(get_db)) -> DefectRead:
    try:
        return maturity.defect_from_failure(db, failure_sample_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/quality/overview", response_model=QualityOverview)
def read_quality_overview(project_id: int | None = None, db: Session = Depends(get_db)) -> QualityOverview:
    return maturity.quality_overview(db, project_id=project_id)


@router.get("/learning/items", response_model=PageResponse)
def read_learning_items(
    page: int = 1,
    page_size: int = 20,
    q: str | None = None,
    status: str | None = None,
    project_id: int | None = None,
    db: Session = Depends(get_db),
) -> PageResponse:
    return maturity.paged_learning_items(db, page=page, page_size=page_size, q=q, status=status, project_id=project_id)


@router.post("/learning/items", response_model=LearningItemRead, status_code=status.HTTP_201_CREATED)
def create_learning_item(payload: LearningItemCreate, db: Session = Depends(get_db)) -> LearningItemRead:
    return maturity.create_learning_item(db, payload)


@router.put("/learning/items/{item_id}", response_model=LearningItemRead)
def update_learning_item(item_id: int, payload: LearningItemUpdate, db: Session = Depends(get_db)) -> LearningItemRead:
    try:
        return maturity.update_learning_item(db, item_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/learning/items/{item_id}/transition/{target_status}", response_model=LearningItemRead)
def transition_learning_item(item_id: int, target_status: str, db: Session = Depends(get_db)) -> LearningItemRead:
    try:
        return maturity.transition_learning_item(db, item_id, target_status)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/learning/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_learning_item(item_id: int, db: Session = Depends(get_db)) -> None:
    try:
        maturity.delete_learning_item(db, item_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/security/users", response_model=PageResponse)
def read_platform_users(page: int = 1, page_size: int = 20, db: Session = Depends(get_db)) -> PageResponse:
    return maturity.paged_users(db, page=page, page_size=page_size)


@router.post("/security/users", response_model=PlatformUserRead, status_code=status.HTTP_201_CREATED)
def create_platform_user(payload: PlatformUserCreate, db: Session = Depends(get_db)) -> PlatformUserRead:
    return maturity.create_platform_user(db, payload)


@router.put("/security/users/{user_id}", response_model=PlatformUserRead)
def update_platform_user(user_id: int, payload: PlatformUserUpdate, db: Session = Depends(get_db)) -> PlatformUserRead:
    try:
        return maturity.update_platform_user(db, user_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/security/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_platform_user(user_id: int, db: Session = Depends(get_db)) -> None:
    try:
        maturity.delete_platform_user(db, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/plugins", response_model=PageResponse)
def read_plugins(page: int = 1, page_size: int = 20, plugin_type: str | None = None, db: Session = Depends(get_db)) -> PageResponse:
    return maturity.paged_plugins(db, page=page, page_size=page_size, plugin_type=plugin_type)


@router.post("/plugins", response_model=PluginRead, status_code=status.HTTP_201_CREATED)
def register_plugin(payload: PluginCreate, db: Session = Depends(get_db)) -> PluginRead:
    return maturity.register_plugin(db, payload)


@router.put("/plugins/{plugin_id}", response_model=PluginRead)
def update_plugin(plugin_id: int, payload: PluginUpdate, db: Session = Depends(get_db)) -> PluginRead:
    try:
        return maturity.update_plugin(db, plugin_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/plugins/{plugin_id}/health-check", response_model=PluginRead)
def plugin_health_check(plugin_id: int, db: Session = Depends(get_db)) -> PluginRead:
    try:
        return maturity.plugin_health_check(db, plugin_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/plugins/{plugin_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plugin(plugin_id: int, db: Session = Depends(get_db)) -> None:
    try:
        maturity.delete_plugin(db, plugin_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/failure-workbench/items", response_model=PageResponse)
def read_failure_workbench(
    page: int = 1,
    page_size: int = 20,
    project_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> PageResponse:
    return maturity.failure_workbench_items(db, page=page, page_size=page_size, project_id=project_id, status=status)


@router.put("/failure-workbench/{failure_sample_id}", response_model=dict)
def update_failure_workbench_item(failure_sample_id: int, payload: FailureSampleUpdate, db: Session = Depends(get_db)) -> dict:
    try:
        return maturity.failure_workbench_payload(maturity.update_failure_sample(db, failure_sample_id, payload))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/failure-workbench/{failure_sample_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_failure_workbench_item(failure_sample_id: int, db: Session = Depends(get_db)) -> None:
    try:
        maturity.delete_failure_sample(db, failure_sample_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/failure-workbench/{failure_sample_id}/solution", response_model=dict)
def generate_failure_solution(failure_sample_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return maturity.failure_solution(db, failure_sample_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
