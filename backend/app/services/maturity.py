from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from math import ceil
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    AuditEvent,
    DefectCandidate,
    FailureAnalysis,
    FailureSample,
    FailureSolution,
    FixApplication,
    LearningItem,
    MaintenanceResponse,
    PlatformPlugin,
    PlatformUser,
    RuleDraft,
    RuleValidation,
    TestAsset,
    TestAssetVersion,
    TestCase,
    TestProject,
    TestRun,
)
from app.schemas.maturity import (
    AssetCreate,
    AssetUpdate,
    DefectCreate,
    DefectUpdate,
    FailureSampleUpdate,
    GenerateCasesRequest,
    GenerateCasesResponse,
    GeneratedCase,
    LearningItemCreate,
    LearningItemUpdate,
    PageResponse,
    PlatformUserCreate,
    PlatformUserUpdate,
    PluginCreate,
    PluginUpdate,
    QualityOverview,
)


def paged_assets(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    q: str | None = None,
    asset_type: str | None = None,
    status: str | None = None,
    project_id: int | None = None,
) -> PageResponse:
    query = select(TestAsset)
    if q:
        like = f"%{q}%"
        query = query.where(or_(TestAsset.asset_name.like(like), TestAsset.asset_code.like(like), TestAsset.module.like(like)))
    if asset_type:
        query = query.where(TestAsset.asset_type == asset_type)
    if status:
        query = query.where(TestAsset.status == status)
    if project_id is not None:
        query = query.where(TestAsset.project_id == project_id)
    query = query.order_by(TestAsset.updated_at.desc(), TestAsset.id.desc())
    return _paginate(db, query, page=page, page_size=page_size, serializer=_asset_payload)


def create_asset(db: Session, payload: AssetCreate) -> TestAsset:
    asset = TestAsset(
        asset_code=_code("ASSET"),
        asset_name=payload.assetName,
        asset_type=payload.assetType,
        project_id=payload.projectId,
        module=payload.module,
        tags_json={"items": payload.tags},
        owner=payload.owner,
        risk_level=payload.riskLevel,
        description=payload.description,
        content_json=payload.content,
        metadata_json={"createdBy": "system"},
    )
    db.add(asset)
    db.flush()
    version = TestAssetVersion(
        asset_id=asset.id,
        version_no=1,
        status="draft",
        content_json=payload.content,
        diff_summary_json={"created": True},
        change_summary="Initial asset version",
    )
    db.add(version)
    db.flush()
    asset.current_version_id = version.id
    db.add(asset)
    _audit(db, "create_asset", "test_asset", asset.id, project_id=asset.project_id, detail={"assetType": asset.asset_type})
    db.commit()
    db.refresh(asset)
    return asset


def update_asset(db: Session, asset_id: int, payload: AssetUpdate) -> TestAsset:
    asset = _asset_or_error(db, asset_id)
    before = dict(asset.content_json or {})
    data = payload.model_dump(exclude_unset=True)
    if "assetName" in data and data["assetName"]:
        asset.asset_name = data["assetName"]
    if "module" in data:
        asset.module = data["module"]
    if "tags" in data and data["tags"] is not None:
        asset.tags_json = {"items": data["tags"]}
    if "owner" in data:
        asset.owner = data["owner"]
    if "status" in data and data["status"]:
        asset.status = data["status"]
    if "riskLevel" in data and data["riskLevel"]:
        asset.risk_level = data["riskLevel"]
    if "description" in data:
        asset.description = data["description"]
    if "content" in data and data["content"] is not None:
        asset.content_json = data["content"]
        version = TestAssetVersion(
            asset_id=asset.id,
            version_no=_next_asset_version_no(db, asset.id),
            status="draft",
            content_json=data["content"],
            diff_summary_json=_dict_diff(before, data["content"]),
            change_summary=data.get("changeSummary") or "Asset content updated",
        )
        db.add(version)
        db.flush()
        asset.current_version_id = version.id
    db.add(asset)
    _audit(db, "update_asset", "test_asset", asset.id, project_id=asset.project_id, detail={"fields": list(data.keys())})
    db.commit()
    db.refresh(asset)
    return asset


def asset_versions(db: Session, asset_id: int) -> list[TestAssetVersion]:
    _asset_or_error(db, asset_id)
    return list(db.scalars(select(TestAssetVersion).where(TestAssetVersion.asset_id == asset_id).order_by(TestAssetVersion.version_no.desc())).all())


def delete_asset(db: Session, asset_id: int) -> None:
    asset = _asset_or_error(db, asset_id)
    for version in db.scalars(select(TestAssetVersion).where(TestAssetVersion.asset_id == asset.id)).all():
        db.delete(version)
    _audit(db, "delete_asset", "test_asset", asset.id, project_id=asset.project_id, detail={"assetName": asset.asset_name})
    db.delete(asset)
    db.commit()


def publish_asset(db: Session, asset_id: int) -> TestAsset:
    asset = _asset_or_error(db, asset_id)
    if asset.risk_level == "high":
        asset.status = "pending_review"
        _audit(db, "request_high_risk_asset_review", "test_asset", asset.id, project_id=asset.project_id, risk_level="high")
    else:
        asset.status = "published"
        asset.latest_published_version_id = asset.current_version_id
        _audit(db, "publish_asset", "test_asset", asset.id, project_id=asset.project_id, risk_level=asset.risk_level)
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def rollback_asset(db: Session, asset_id: int, version_id: int) -> TestAsset:
    asset = _asset_or_error(db, asset_id)
    version = db.get(TestAssetVersion, version_id)
    if version is None or version.asset_id != asset.id:
        raise ValueError("Asset version not found.")
    asset.content_json = version.content_json or {}
    rollback_version = TestAssetVersion(
        asset_id=asset.id,
        version_no=_next_asset_version_no(db, asset.id),
        status="draft",
        content_json=asset.content_json,
        diff_summary_json={"rollbackToVersionId": version.id, "rollbackToVersionNo": version.version_no},
        change_summary=f"Rollback to version {version.version_no}",
    )
    db.add(rollback_version)
    db.flush()
    asset.current_version_id = rollback_version.id
    asset.status = "draft"
    db.add(asset)
    _audit(db, "rollback_asset", "test_asset", asset.id, project_id=asset.project_id, detail={"versionId": version.id})
    db.commit()
    db.refresh(asset)
    return asset


def generate_cases(payload: GenerateCasesRequest) -> GenerateCasesResponse:
    features = _features_from_text(payload.sourceText)
    generated: list[GeneratedCase] = []
    for feature in features:
        generated.append(_generated_case(feature, "positive"))
        if payload.includeNegative:
            generated.append(_generated_case(feature, "negative"))
        if payload.includeBoundary:
            generated.append(_generated_case(feature, "boundary"))
        if payload.includePermission and _is_high_risk_feature(feature):
            generated.append(_generated_case(feature, "permission"))
    coverage = coverage_summary([item.model_dump() for item in generated])
    return GenerateCasesResponse(
        items=generated,
        coverage=coverage,
        summary={"featureCount": len(features), "caseCount": len(generated), "strategy": payload.strategy},
    )


def coverage_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    scenario_counts: dict[str, int] = {}
    modules: dict[str, int] = {}
    for item in cases:
        scenario = str(item.get("scenarioType") or item.get("scenario_type") or "unknown")
        scenario_counts[scenario] = scenario_counts.get(scenario, 0) + 1
        module = str(item.get("module") or "未分组")
        modules[module] = modules.get(module, 0) + 1
    expected = {"positive", "negative", "boundary", "permission"}
    missing = sorted(expected - set(scenario_counts))
    return {"scenarioCounts": scenario_counts, "moduleCounts": modules, "missingScenarioTypes": missing}


def paged_defects(db: Session, *, page: int = 1, page_size: int = 20, q: str | None = None, status: str | None = None, project_id: int | None = None) -> PageResponse:
    query = select(DefectCandidate)
    if q:
        like = f"%{q}%"
        query = query.where(or_(DefectCandidate.title.like(like), DefectCandidate.defect_code.like(like)))
    if status:
        query = query.where(DefectCandidate.status == status)
    if project_id is not None:
        query = query.where(DefectCandidate.project_id == project_id)
    query = query.order_by(DefectCandidate.updated_at.desc(), DefectCandidate.id.desc())
    return _paginate(db, query, page=page, page_size=page_size, serializer=_defect_payload)


def create_defect(db: Session, payload: DefectCreate) -> DefectCandidate:
    defect = DefectCandidate(
        defect_code=_code("DEF"),
        project_id=payload.projectId,
        case_id=payload.caseId,
        run_id=payload.runId,
        failure_sample_id=payload.failureSampleId,
        title=payload.title,
        description=payload.description,
        defect_type=payload.defectType,
        severity=payload.severity,
        priority=payload.priority,
        assignee=payload.assignee,
        reproduce_steps_json=payload.reproduceSteps,
        evidence_json=payload.evidence,
        dedup_key=_dedup_key(payload.title, payload.projectId),
    )
    db.add(defect)
    db.flush()
    _audit(db, "create_defect_candidate", "defect_candidate", defect.id, project_id=payload.projectId, risk_level=payload.severity)
    db.commit()
    db.refresh(defect)
    return defect


def update_defect(db: Session, defect_id: int, payload: DefectUpdate) -> DefectCandidate:
    defect = _defect_or_error(db, defect_id)
    data = payload.model_dump(exclude_unset=True)
    mapping = {
        "title": "title",
        "description": "description",
        "defectType": "defect_type",
        "severity": "severity",
        "priority": "priority",
        "status": "status",
        "assignee": "assignee",
        "reproduceSteps": "reproduce_steps_json",
        "evidence": "evidence_json",
    }
    for source, target in mapping.items():
        if source in data:
            setattr(defect, target, data[source])
    _audit(db, "update_defect_candidate", "defect_candidate", defect.id, project_id=defect.project_id, risk_level=defect.severity, detail={"fields": list(data.keys())})
    db.add(defect)
    db.commit()
    db.refresh(defect)
    return defect


def delete_defect(db: Session, defect_id: int) -> None:
    defect = _defect_or_error(db, defect_id)
    _audit(db, "delete_defect_candidate", "defect_candidate", defect.id, project_id=defect.project_id, risk_level=defect.severity)
    db.delete(defect)
    db.commit()


def defect_from_failure(db: Session, failure_sample_id: int) -> DefectCandidate:
    sample = db.get(FailureSample, failure_sample_id)
    if sample is None:
        raise ValueError("Failure sample not found.")
    title = _title_from_failure(sample)
    payload = DefectCreate(
        projectId=sample.project_id,
        caseId=sample.case_id,
        runId=sample.run_id,
        failureSampleId=sample.id,
        title=title,
        description=sample.failure_summary,
        defectType=_defect_type(sample.failure_type),
        severity=_severity(sample.failure_type),
        reproduceSteps={"source": "failure_sample", "runId": sample.run_id, "stepId": sample.step_id},
        evidence={
            "screenshot": sample.screenshot_path,
            "domSnapshot": sample.dom_snapshot_path,
            "runtimeStream": sample.runtime_stream_path,
            "analysis": sample.ai_analysis_json,
        },
    )
    return create_defect(db, payload)


def quality_overview(db: Session, project_id: int | None = None) -> QualityOverview:
    case_query = select(func.count(TestCase.id))
    run_query = select(TestRun.status, func.count(TestRun.id)).group_by(TestRun.status)
    failure_query = select(FailureSample.failure_type, func.count(FailureSample.id)).group_by(FailureSample.failure_type)
    defect_query = select(DefectCandidate.severity, func.count(DefectCandidate.id)).group_by(DefectCandidate.severity)
    if project_id is not None:
        case_query = case_query.where(TestCase.project_id == project_id)
        run_query = run_query.where(TestRun.project_id == project_id)
        failure_query = failure_query.where(FailureSample.project_id == project_id)
        defect_query = defect_query.where(DefectCandidate.project_id == project_id)
    case_count = int(db.scalar(case_query) or 0)
    run_counts = {str(status or "unknown"): int(count) for status, count in db.execute(run_query).all()}
    failure_counts = {str(kind or "unknown"): int(count) for kind, count in db.execute(failure_query).all()}
    defect_counts = {str(kind or "unknown"): int(count) for kind, count in db.execute(defect_query).all()}
    passed = run_counts.get("passed", 0)
    failed = run_counts.get("failed", 0)
    executed = sum(run_counts.values())
    pass_rate = round(passed / executed * 100, 2) if executed else 0
    return QualityOverview(
        projectId=project_id,
        totals={
            "cases": case_count,
            "runs": executed,
            "passed": passed,
            "failed": failed,
            "passRate": pass_rate,
            "defects": sum(defect_counts.values()),
        },
        trends=[],
        modules=_module_summary(db, project_id),
        failures=[{"type": key, "count": value} for key, value in failure_counts.items()],
        recommendations=_quality_recommendations(pass_rate, failure_counts, defect_counts),
    )


def paged_learning_items(db: Session, *, page: int = 1, page_size: int = 20, q: str | None = None, status: str | None = None, project_id: int | None = None) -> PageResponse:
    query = select(LearningItem)
    if q:
        like = f"%{q}%"
        query = query.where(or_(LearningItem.title.like(like), LearningItem.learning_code.like(like)))
    if status:
        query = query.where(LearningItem.status == status)
    if project_id is not None:
        query = query.where(LearningItem.project_id == project_id)
    query = query.order_by(LearningItem.updated_at.desc(), LearningItem.id.desc())
    return _paginate(db, query, page=page, page_size=page_size, serializer=_learning_payload)


def create_learning_item(db: Session, payload: LearningItemCreate) -> LearningItem:
    item = LearningItem(
        learning_code=_code("LEARN"),
        project_id=payload.projectId,
        item_type=payload.itemType,
        title=payload.title,
        source_type=payload.sourceType,
        source_id=payload.sourceId,
        risk_level=payload.riskLevel,
        proposal_json=payload.proposal,
    )
    db.add(item)
    db.flush()
    _audit(db, "create_learning_item", "learning_item", item.id, project_id=item.project_id, risk_level=item.risk_level)
    db.commit()
    db.refresh(item)
    return item


def update_learning_item(db: Session, item_id: int, payload: LearningItemUpdate) -> LearningItem:
    item = _learning_item_or_error(db, item_id)
    data = payload.model_dump(exclude_unset=True)
    mapping = {
        "itemType": "item_type",
        "title": "title",
        "status": "status",
        "riskLevel": "risk_level",
        "proposal": "proposal_json",
        "validation": "validation_json",
    }
    for source, target in mapping.items():
        if source in data:
            setattr(item, target, data[source])
    _audit(db, "update_learning_item", "learning_item", item.id, project_id=item.project_id, risk_level=item.risk_level, detail={"fields": list(data.keys())})
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def transition_learning_item(db: Session, item_id: int, status: str) -> LearningItem:
    item = _learning_item_or_error(db, item_id)
    if item.risk_level == "high" and status == "active":
        item.status = "pending_review"
        item.audit_json = {"blocked": "high risk learning item requires review"}
    else:
        item.status = status
    db.add(item)
    _audit(db, "transition_learning_item", "learning_item", item.id, project_id=item.project_id, risk_level=item.risk_level, detail={"status": status})
    db.commit()
    db.refresh(item)
    return item


def delete_learning_item(db: Session, item_id: int) -> None:
    item = _learning_item_or_error(db, item_id)
    _audit(db, "delete_learning_item", "learning_item", item.id, project_id=item.project_id, risk_level=item.risk_level)
    db.delete(item)
    db.commit()


def create_platform_user(db: Session, payload: PlatformUserCreate) -> PlatformUser:
    user = PlatformUser(username=payload.username, display_name=payload.displayName, role=payload.role, status=payload.status)
    db.add(user)
    db.flush()
    _audit(db, "create_platform_user", "platform_user", user.id, actor=payload.username)
    db.commit()
    db.refresh(user)
    return user


def update_platform_user(db: Session, user_id: int, payload: PlatformUserUpdate) -> PlatformUser:
    user = _platform_user_or_error(db, user_id)
    data = payload.model_dump(exclude_unset=True)
    if "displayName" in data:
        user.display_name = data["displayName"]
    if "role" in data and data["role"]:
        user.role = data["role"]
    if "status" in data and data["status"]:
        user.status = data["status"]
    _audit(db, "update_platform_user", "platform_user", user.id, actor=user.username, detail={"fields": list(data.keys())})
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def delete_platform_user(db: Session, user_id: int) -> None:
    user = _platform_user_or_error(db, user_id)
    _audit(db, "delete_platform_user", "platform_user", user.id, actor=user.username)
    db.delete(user)
    db.commit()


def paged_users(db: Session, *, page: int = 1, page_size: int = 20) -> PageResponse:
    return _paginate(db, select(PlatformUser).order_by(PlatformUser.id.desc()), page=page, page_size=page_size, serializer=_user_payload)


def register_plugin(db: Session, payload: PluginCreate) -> PlatformPlugin:
    plugin = PlatformPlugin(
        plugin_code=payload.pluginCode or _code("PLUGIN"),
        plugin_name=payload.pluginName,
        plugin_type=payload.pluginType,
        version=payload.version,
        status=payload.status,
        priority=payload.priority,
        config_schema_json=payload.configSchema,
        config_json=payload.config,
        health_json={"status": "unknown"},
    )
    db.add(plugin)
    db.flush()
    _audit(db, "register_plugin", "platform_plugin", plugin.id, detail={"pluginType": plugin.plugin_type})
    db.commit()
    db.refresh(plugin)
    return plugin


def update_plugin(db: Session, plugin_id: int, payload: PluginUpdate) -> PlatformPlugin:
    plugin = _plugin_or_error(db, plugin_id)
    data = payload.model_dump(exclude_unset=True)
    mapping = {
        "pluginName": "plugin_name",
        "pluginType": "plugin_type",
        "version": "version",
        "status": "status",
        "priority": "priority",
        "configSchema": "config_schema_json",
        "config": "config_json",
    }
    for source, target in mapping.items():
        if source in data:
            setattr(plugin, target, data[source])
    _audit(db, "update_plugin", "platform_plugin", plugin.id, detail={"fields": list(data.keys())})
    db.add(plugin)
    db.commit()
    db.refresh(plugin)
    return plugin


def paged_plugins(db: Session, *, page: int = 1, page_size: int = 20, plugin_type: str | None = None) -> PageResponse:
    query = select(PlatformPlugin)
    if plugin_type:
        query = query.where(PlatformPlugin.plugin_type == plugin_type)
    query = query.order_by(PlatformPlugin.priority, PlatformPlugin.id.desc())
    return _paginate(db, query, page=page, page_size=page_size, serializer=_plugin_payload)


def plugin_health_check(db: Session, plugin_id: int) -> PlatformPlugin:
    plugin = _plugin_or_error(db, plugin_id)
    plugin.health_json = {
        "status": "healthy" if plugin.status == "active" else "disabled",
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "message": "配置结构可读取。",
    }
    db.add(plugin)
    db.commit()
    db.refresh(plugin)
    return plugin


def delete_plugin(db: Session, plugin_id: int) -> None:
    plugin = _plugin_or_error(db, plugin_id)
    _audit(db, "delete_plugin", "platform_plugin", plugin.id, detail={"pluginName": plugin.plugin_name})
    db.delete(plugin)
    db.commit()


def failure_workbench_items(db: Session, *, page: int = 1, page_size: int = 20, project_id: int | None = None, status: str | None = None) -> PageResponse:
    query = select(FailureSample)
    if project_id is not None:
        query = query.where(FailureSample.project_id == project_id)
    if status:
        query = query.where(FailureSample.status == status)
    query = query.order_by(FailureSample.id.desc())
    return _paginate(db, query, page=page, page_size=page_size, serializer=_failure_workbench_payload)


def failure_workbench_payload(sample: FailureSample) -> dict[str, Any]:
    return _failure_workbench_payload(sample)


def update_failure_sample(db: Session, failure_sample_id: int, payload: FailureSampleUpdate) -> FailureSample:
    sample = _failure_sample_or_error(db, failure_sample_id)
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"]:
        sample.status = data["status"]
    if "failureSummary" in data:
        sample.failure_summary = data["failureSummary"]
    if "aiAnalysis" in data:
        sample.ai_analysis_json = data["aiAnalysis"]
    if "suggestedRule" in data:
        sample.suggested_rule_json = data["suggestedRule"]
    _audit(db, "update_failure_sample", "failure_sample", sample.id, project_id=sample.project_id, detail={"fields": list(data.keys())})
    db.add(sample)
    db.commit()
    db.refresh(sample)
    return sample


def delete_failure_sample(db: Session, failure_sample_id: int) -> None:
    sample = _failure_sample_or_error(db, failure_sample_id)
    solutions = list(db.scalars(select(FailureSolution).where(FailureSolution.failure_sample_id == sample.id)).all())
    solution_ids = [solution.id for solution in solutions]
    deleted_response_ids: set[int] = set()
    if solution_ids:
        validations = list(db.scalars(select(RuleValidation).where(RuleValidation.solution_id.in_(solution_ids))).all())
        validation_ids = [validation.id for validation in validations]
        for response in db.scalars(select(MaintenanceResponse).where(MaintenanceResponse.solution_id.in_(solution_ids))).all():
            deleted_response_ids.add(response.id)
            db.delete(response)
        if validation_ids:
            for response in db.scalars(select(MaintenanceResponse).where(MaintenanceResponse.validation_id.in_(validation_ids))).all():
                if response.id not in deleted_response_ids:
                    deleted_response_ids.add(response.id)
                    db.delete(response)
        for validation in validations:
            db.delete(validation)
        for solution in solutions:
            db.delete(solution)
    for response in db.scalars(select(MaintenanceResponse).where(MaintenanceResponse.failure_sample_id == sample.id)).all():
        if response.id not in deleted_response_ids:
            db.delete(response)
    analyses = list(db.scalars(select(FailureAnalysis).where(FailureAnalysis.failure_sample_id == sample.id)).all())
    analysis_ids = [analysis.id for analysis in analyses]
    if analysis_ids:
        for fix in db.scalars(select(FixApplication).where(FixApplication.failure_analysis_id.in_(analysis_ids))).all():
            fix.failure_analysis_id = None
            db.add(fix)
    for defect in db.scalars(select(DefectCandidate).where(DefectCandidate.failure_sample_id == sample.id)).all():
        defect.failure_sample_id = None
        db.add(defect)
    for draft in db.scalars(select(RuleDraft).where(RuleDraft.source_type == "failure_sample", RuleDraft.source_id == sample.id)).all():
        db.delete(draft)
    for analysis in analyses:
        db.delete(analysis)
    _audit(db, "delete_failure_sample", "failure_sample", sample.id, project_id=sample.project_id, detail={"runId": sample.run_id})
    db.delete(sample)
    db.commit()


def failure_solution(db: Session, failure_sample_id: int) -> dict[str, Any]:
    sample = _failure_sample_or_error(db, failure_sample_id)
    category = sample.failure_type or "unknown"
    suggested_type = "create_rule_draft"
    if "data" in category:
        suggested_type = "modify_test_data"
    elif "login" in category:
        suggested_type = "modify_account_or_login_rule"
    elif "assert" in category:
        suggested_type = "add_assertion_rule"
    return {
        "failureSampleId": sample.id,
        "category": category,
        "userMessage": sample.failure_summary or "当前失败需要补充规则或测试数据后重试。",
        "recommendedAction": suggested_type,
        "riskLevel": "high" if category in {"approval_failed", "delete_failed"} else "medium",
        "ruleDraft": {
            "source": "failure_workbench",
            "failureType": category,
            "match": {"target": (sample.ai_analysis_json or {}).get("target")},
            "action": {"strategy": suggested_type},
        },
        "verificationPlan": {"type": "dry_run", "sampleId": sample.id},
    }


def _paginate(db: Session, query, *, page: int, page_size: int, serializer: Callable[[Any], dict[str, Any]]) -> PageResponse:
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 20), 200))
    count_query = select(func.count()).select_from(query.order_by(None).subquery())
    total = int(db.scalar(count_query) or 0)
    items = list(db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all())
    total_pages = ceil(total / page_size) if total else 0
    return PageResponse(
        items=[serializer(item) for item in items],
        page=page,
        pageSize=page_size,
        total=total,
        totalPages=total_pages,
        hasNext=page < total_pages,
        hasPrev=page > 1,
    )


def _asset_payload(asset: TestAsset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "assetCode": asset.asset_code,
        "assetName": asset.asset_name,
        "assetType": asset.asset_type,
        "projectId": asset.project_id,
        "module": asset.module,
        "tags": (asset.tags_json or {}).get("items", []),
        "status": asset.status,
        "owner": asset.owner,
        "riskLevel": asset.risk_level,
        "description": asset.description,
        "currentVersionId": asset.current_version_id,
        "createdAt": str(asset.created_at),
        "updatedAt": str(asset.updated_at),
    }


def _defect_payload(defect: DefectCandidate) -> dict[str, Any]:
    return {
        "id": defect.id,
        "defectCode": defect.defect_code,
        "projectId": defect.project_id,
        "caseId": defect.case_id,
        "runId": defect.run_id,
        "failureSampleId": defect.failure_sample_id,
        "title": defect.title,
        "defectType": defect.defect_type,
        "severity": defect.severity,
        "priority": defect.priority,
        "status": defect.status,
        "assignee": defect.assignee,
        "createdAt": str(defect.created_at),
        "updatedAt": str(defect.updated_at),
    }


def _learning_payload(item: LearningItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "learningCode": item.learning_code,
        "projectId": item.project_id,
        "itemType": item.item_type,
        "title": item.title,
        "status": item.status,
        "riskLevel": item.risk_level,
        "sourceType": item.source_type,
        "sourceId": item.source_id,
        "createdAt": str(item.created_at),
        "updatedAt": str(item.updated_at),
    }


def _user_payload(user: PlatformUser) -> dict[str, Any]:
    return {"id": user.id, "username": user.username, "displayName": user.display_name, "role": user.role, "status": user.status}


def _plugin_payload(plugin: PlatformPlugin) -> dict[str, Any]:
    return {
        "id": plugin.id,
        "pluginCode": plugin.plugin_code,
        "pluginName": plugin.plugin_name,
        "pluginType": plugin.plugin_type,
        "version": plugin.version,
        "status": plugin.status,
        "priority": plugin.priority,
        "health": plugin.health_json or {},
    }


def _failure_workbench_payload(sample: FailureSample) -> dict[str, Any]:
    analysis = sample.ai_analysis_json or {}
    return {
        "id": sample.id,
        "projectId": sample.project_id,
        "caseId": sample.case_id,
        "runId": sample.run_id,
        "stepId": sample.step_id,
        "failureType": sample.failure_type,
        "failureSummary": sample.failure_summary,
        "status": sample.status,
        "riskLevel": "high" if sample.failure_type in {"approval_failed", "delete_failed"} else "medium",
        "analysisStatus": "analyzed" if analysis else "pending",
        "recommendedAction": (sample.suggested_rule_json or {}).get("candidateRuleType") or "analyze",
        "screenshotPath": sample.screenshot_path,
        "createdAt": str(sample.created_at),
    }


def _asset_or_error(db: Session, asset_id: int) -> TestAsset:
    asset = db.get(TestAsset, asset_id)
    if asset is None:
        raise ValueError("Asset not found.")
    return asset


def _defect_or_error(db: Session, defect_id: int) -> DefectCandidate:
    defect = db.get(DefectCandidate, defect_id)
    if defect is None:
        raise ValueError("Defect candidate not found.")
    return defect


def _learning_item_or_error(db: Session, item_id: int) -> LearningItem:
    item = db.get(LearningItem, item_id)
    if item is None:
        raise ValueError("Learning item not found.")
    return item


def _platform_user_or_error(db: Session, user_id: int) -> PlatformUser:
    user = db.get(PlatformUser, user_id)
    if user is None:
        raise ValueError("Platform user not found.")
    return user


def _plugin_or_error(db: Session, plugin_id: int) -> PlatformPlugin:
    plugin = db.get(PlatformPlugin, plugin_id)
    if plugin is None:
        raise ValueError("Plugin not found.")
    return plugin


def _failure_sample_or_error(db: Session, failure_sample_id: int) -> FailureSample:
    sample = db.get(FailureSample, failure_sample_id)
    if sample is None:
        raise ValueError("Failure sample not found.")
    return sample


def _next_asset_version_no(db: Session, asset_id: int) -> int:
    current = db.scalar(select(func.max(TestAssetVersion.version_no)).where(TestAssetVersion.asset_id == asset_id))
    return int(current or 0) + 1


def _dict_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_keys = set(before)
    after_keys = set(after)
    changed = sorted(key for key in before_keys & after_keys if before.get(key) != after.get(key))
    return {"added": sorted(after_keys - before_keys), "removed": sorted(before_keys - after_keys), "changed": changed}


def _features_from_text(text: str) -> list[dict[str, str]]:
    lines = [line.strip(" -#\t") for line in (text or "").splitlines() if line.strip()]
    features: list[dict[str, str]] = []
    for line in lines:
        if len(features) >= 200:
            break
        if not any(token in line for token in ["查询", "新增", "修改", "删除", "审批", "导入", "导出", "上传", "菜单", "/"]):
            continue
        features.append({"raw": line, "module": _module_from_line(line), "operation": _operation_from_line(line)})
    if not features and text.strip():
        features.append({"raw": text.strip()[:500], "module": "默认模块", "operation": "验证"})
    return features


def _generated_case(feature: dict[str, str], scenario_type: str) -> GeneratedCase:
    operation = feature.get("operation") or "验证"
    module = feature.get("module") or "默认模块"
    raw = feature.get("raw") or operation
    suffix = {"positive": "正例", "negative": "反例", "boundary": "边界", "permission": "权限"}.get(scenario_type, scenario_type)
    return GeneratedCase(
        caseName=f"{module}-{operation}-{suffix}",
        module=module,
        feature=operation,
        scenarioType=scenario_type,
        naturalLanguageGoal=_goal_for_scenario(raw, scenario_type),
        testData=_data_for_scenario(operation, scenario_type),
        expectedResult=_expected_for_scenario(operation, scenario_type),
        riskLevel="high" if operation in {"删除", "审批", "提交"} else "medium" if operation in {"新增", "修改", "上传"} else "low",
        coverage=[module, operation, scenario_type],
        automationScore=0.75 if scenario_type == "positive" else 0.6,
    )


def _module_from_line(line: str) -> str:
    parts = re.split(r"[/>\-→]", line)
    return parts[0].strip()[:40] if len(parts) > 1 else "默认模块"


def _operation_from_line(line: str) -> str:
    for token in ["查询", "新增", "修改", "删除", "审批", "提交", "导入", "导出", "上传"]:
        if token in line:
            return token
    return "验证"


def _is_high_risk_feature(feature: dict[str, str]) -> bool:
    return feature.get("operation") in {"删除", "审批", "提交"}


def _goal_for_scenario(raw: str, scenario_type: str) -> str:
    if scenario_type == "negative":
        return f"{raw}，使用无效或缺失数据验证系统提示。"
    if scenario_type == "boundary":
        return f"{raw}，使用边界值验证系统处理。"
    if scenario_type == "permission":
        return f"{raw}，使用无权限账号验证访问控制。"
    return raw


def _data_for_scenario(operation: str, scenario_type: str) -> dict[str, Any]:
    if scenario_type == "negative":
        return {"invalid": True, "requiredField": ""}
    if scenario_type == "boundary":
        return {"boundaryValue": "MAX_LENGTH_OR_LIMIT"}
    if scenario_type == "permission":
        return {"role": "unauthorized"}
    return {"operation": operation}


def _expected_for_scenario(operation: str, scenario_type: str) -> str:
    if scenario_type == "negative":
        return "系统阻止无效输入，并显示明确校验提示。"
    if scenario_type == "boundary":
        return "系统按边界规则处理，并给出正确结果或提示。"
    if scenario_type == "permission":
        return "系统阻止无权限操作，并显示权限提示。"
    return f"{operation}操作成功，并出现明确成功证据。"


def _title_from_failure(sample: FailureSample) -> str:
    summary = str(sample.failure_summary or sample.failure_type or "自动化执行失败")
    return summary[:80]


def _defect_type(failure_type: str | None) -> str:
    text = str(failure_type or "")
    if any(token in text for token in ["locator", "rule", "dsl"]):
        return "automation_issue"
    if "permission" in text or "auth" in text:
        return "permission_issue"
    if "environment" in text or "timeout" in text:
        return "environment_issue"
    return "system_defect"


def _severity(failure_type: str | None) -> str:
    text = str(failure_type or "")
    if any(token in text for token in ["approval", "delete", "security"]):
        return "high"
    if any(token in text for token in ["login", "permission", "timeout"]):
        return "medium"
    return "low"


def _dedup_key(title: str, project_id: int | None) -> str:
    return hashlib.sha1(f"{project_id}:{title}".encode("utf-8")).hexdigest()


def _module_summary(db: Session, project_id: int | None) -> list[dict[str, Any]]:
    query = select(TestCase.business_intent, func.count(TestCase.id)).group_by(TestCase.business_intent)
    if project_id is not None:
        query = query.where(TestCase.project_id == project_id)
    return [{"module": module or "未分组", "caseCount": int(count)} for module, count in db.execute(query).all()]


def _quality_recommendations(pass_rate: float, failures: dict[str, int], defects: dict[str, int]) -> list[str]:
    recommendations = []
    if pass_rate < 80:
        recommendations.append("通过率低于 80%，建议优先处理高频失败样本并生成规则草案。")
    if failures:
        top_failure = max(failures.items(), key=lambda item: item[1])[0]
        recommendations.append(f"高频失败类型为 {top_failure}，建议进入失败工作台批量分析。")
    if defects.get("high", 0):
        recommendations.append("存在高严重级别缺陷，建议阻止上线或执行专项回归。")
    if not recommendations:
        recommendations.append("当前质量指标稳定，可继续补充覆盖率和边界场景。")
    return recommendations


def _audit(
    db: Session,
    action: str,
    target_type: str | None = None,
    target_id: int | None = None,
    *,
    project_id: int | None = None,
    actor: str | None = "system",
    risk_level: str = "low",
    detail: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditEvent(
            project_id=project_id,
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            risk_level=risk_level,
            detail_json=detail or {},
        )
    )


def _code(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{stamp}-{uuid4().hex[:6].upper()}"
