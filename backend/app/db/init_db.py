from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import engine
from app.models import PlatformUser, TestProject
from app.services.abilities import ensure_base_ability_rules
from app.services.auth import ensure_default_admin
from app.services.permissions import ensure_project_owner_membership


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_compatible_columns()


def ensure_compatible_columns() -> None:
    inspector = inspect(engine)
    additions = {
        "test_projects": {
            "system_id": "INTEGER",
            "project_name": "VARCHAR(255)",
            "home_url": "VARCHAR(1024)",
            "auth_type": "VARCHAR(64) DEFAULT 'username_password' NOT NULL",
            "default_account_id": "INTEGER",
            "default_timeout_ms": "INTEGER DEFAULT 15000 NOT NULL",
            "owner_user_id": "INTEGER",
            "created_by_user_id": "INTEGER",
            "enable_trace_default": "BOOLEAN DEFAULT TRUE NOT NULL",
            "enable_screenshot_default": "BOOLEAN DEFAULT TRUE NOT NULL",
            "enable_dom_snapshot_default": "BOOLEAN DEFAULT TRUE NOT NULL",
            "enable_accessibility_snapshot_default": "BOOLEAN DEFAULT TRUE NOT NULL",
            "enable_vision_fallback_default": "BOOLEAN DEFAULT FALSE NOT NULL",
            "deleted_at": "DATETIME",
        },
        "test_accounts": {
            "system_id": "INTEGER",
            "environment": "VARCHAR(32)",
            "project_id": "INTEGER",
            "account_name": "VARCHAR(255)",
            "description": "TEXT",
            "allow_read": "BOOLEAN DEFAULT TRUE NOT NULL",
            "is_default": "BOOLEAN DEFAULT FALSE NOT NULL",
            "deleted_at": "DATETIME",
        },
        "test_cases": {
            "case_code": "VARCHAR(64)",
            "description": "TEXT",
            "source_document_id": "INTEGER",
            "source_run_id": "INTEGER",
            "natural_language_goal": "TEXT",
            "menu_path": "VARCHAR(1024)",
            "business_intent": "VARCHAR(255)",
            "inherit_project_account": "BOOLEAN DEFAULT TRUE NOT NULL",
            "account_id": "INTEGER",
            "test_data_json": "JSON",
            "preconditions_json": "JSON",
            "success_criteria_json": "JSON",
            "settings_json": "JSON",
            "risk_level": "VARCHAR(32) DEFAULT 'low' NOT NULL",
            "current_version_id": "INTEGER",
            "last_run_id": "INTEGER",
            "last_run_status": "VARCHAR(32)",
            "last_run_at": "DATETIME",
            "run_count": "INTEGER DEFAULT 0 NOT NULL",
            "pass_count": "INTEGER DEFAULT 0 NOT NULL",
            "fail_count": "INTEGER DEFAULT 0 NOT NULL",
            "created_by_user_id": "INTEGER",
            "updated_by_user_id": "INTEGER",
            "deleted_at": "DATETIME",
        },
        "test_runs": {
            "system_id": "INTEGER",
            "case_version_id": "INTEGER",
            "campaign_id": "INTEGER",
            "account_id": "INTEGER",
            "created_by_user_id": "INTEGER",
            "instruction_snapshot": "TEXT",
            "base_url_snapshot": "VARCHAR(1024)",
            "login_url_snapshot": "VARCHAR(1024)",
            "home_url_snapshot": "VARCHAR(1024)",
            "dsl_snapshot": "JSON",
            "test_data_snapshot": "JSON",
            "settings_snapshot": "JSON",
            "account_snapshot": "JSON",
            "error_summary": "TEXT",
            "duration_ms": "INTEGER",
        },
        "test_campaigns": {
            "created_by_user_id": "INTEGER",
        },
        "project_memberships": {
            "permissions_json": "JSON",
            "created_by_user_id": "INTEGER",
            "updated_at": "DATETIME",
        },
        "audit_events": {
            "actor_user_id": "INTEGER",
            "case_id": "INTEGER",
            "run_id": "INTEGER",
            "campaign_id": "INTEGER",
            "result": "VARCHAR(64)",
            "before_json": "JSON",
            "after_json": "JSON",
        },
        "failure_samples": {
            "project_id": "INTEGER",
            "case_id": "INTEGER",
            "case_version_id": "INTEGER",
            "evidence_json": "JSON",
        },
        "failure_analyses": {
            "generalized_pattern_json": "JSON",
            "solution_json": "JSON",
            "rule_draft_json": "JSON",
            "validation_plan_json": "JSON",
            "user_reply": "TEXT",
            "internal_notes": "TEXT",
            "llm_raw_response_json": "JSON",
        },
        "ability_knowledge": {
            "system_id": "INTEGER",
            "evidence_json": "JSON",
        },
        "ability_rules": {
            "failure_patterns_json": "JSON",
            "recovery_strategies_json": "JSON",
            "auto_handle": "BOOLEAN DEFAULT FALSE NOT NULL",
            "requires_human_confirmation": "BOOLEAN DEFAULT FALSE NOT NULL",
            "version": "VARCHAR(32) DEFAULT '1.0.0' NOT NULL",
        },
    }

    with engine.begin() as connection:
        for table_name, columns in additions.items():
            if not inspector.has_table(table_name):
                continue
            existing = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))
        if inspector.has_table("test_projects"):
            connection.execute(text("UPDATE test_projects SET project_name = name WHERE project_name IS NULL"))
        if inspector.has_table("test_cases"):
            connection.execute(text("UPDATE test_cases SET natural_language_goal = instruction WHERE natural_language_goal IS NULL"))
        if inspector.has_table("platform_users"):
            connection.execute(text("UPDATE platform_users SET role = 'testuser' WHERE role IN ('tester', 'member', 'user')"))
        if inspector.has_table("project_memberships"):
            connection.execute(text("UPDATE project_memberships SET role = 'testuser' WHERE role IN ('tester', 'member', 'user')"))


def ensure_default_project(db: Session, admin_user: PlatformUser) -> None:
    has_project = db.query(TestProject.id).first()
    if has_project is not None:
        projects = db.query(TestProject).filter(TestProject.deleted_at.is_(None), TestProject.status != "deleted").all()
        for project in projects:
            if project.owner_user_id is None:
                ensure_project_owner_membership(db, project, admin_user)
        db.commit()
        return

    project = TestProject(
        project_code="DEFAULT",
        name="默认测试项目",
        project_name="默认测试项目",
        description="Initial project for enterprise MIS functional testing.",
        environment="test",
        status="active",
        owner_user_id=admin_user.id,
        created_by_user_id=admin_user.id,
    )
    db.add(project)
    db.flush()
    ensure_project_owner_membership(db, project, admin_user)
    db.commit()


def init_db() -> None:
    create_tables()
    with Session(bind=engine) as db:
        admin_user = ensure_default_admin(db)
        ensure_default_project(db, admin_user)
        ensure_base_ability_rules(db)
