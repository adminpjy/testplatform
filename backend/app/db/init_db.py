from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import engine
from app.models import TestProject
from app.services.abilities import ensure_base_ability_rules


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_compatible_columns()


def ensure_compatible_columns() -> None:
    inspector = inspect(engine)
    additions = {
        "test_projects": {
            "system_id": "INTEGER",
        },
        "test_accounts": {
            "system_id": "INTEGER",
            "environment": "VARCHAR(32)",
        },
        "test_runs": {
            "system_id": "INTEGER",
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


def ensure_default_project(db: Session) -> None:
    has_project = db.query(TestProject.id).first()
    if has_project is not None:
        return

    project = TestProject(
        project_code="DEFAULT",
        name="默认测试项目",
        description="Initial project for enterprise MIS functional testing.",
        environment="test",
        status="active",
    )
    db.add(project)
    db.commit()


def init_db() -> None:
    create_tables()
    with Session(bind=engine) as db:
        ensure_default_project(db)
        ensure_base_ability_rules(db)
