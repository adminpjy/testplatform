from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utc_now


class TestSystem(Base):
    __tablename__ = "test_systems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    system_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    system_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    login_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    home_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    environment: Mapped[str] = mapped_column(String(32), default="test", nullable=False)
    auth_type: Mapped[str] = mapped_column(String(64), default="username_password", nullable=False)
    default_timeout_ms: Mapped[int] = mapped_column(Integer, default=15000, nullable=False)
    allow_write: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allow_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allow_delete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    projects = relationship("TestProject", back_populates="system")
    accounts = relationship("TestAccount", back_populates="system")
    runs = relationship("TestRun", back_populates="system")


class TestProject(Base):
    __tablename__ = "test_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    project_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_id: Mapped[int | None] = mapped_column(ForeignKey("test_systems.id"), nullable=True, index=True)
    system_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    login_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    home_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    auth_type: Mapped[str] = mapped_column(String(64), default="username_password", nullable=False)
    default_account_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    default_timeout_ms: Mapped[int] = mapped_column(Integer, default=15000, nullable=False)
    enable_trace_default: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    enable_screenshot_default: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    enable_dom_snapshot_default: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    enable_accessibility_snapshot_default: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    enable_vision_fallback_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    environment: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    system = relationship("TestSystem", back_populates="projects")
    environments = relationship("TestEnvironment", back_populates="project")
    accounts = relationship("TestAccount", back_populates="project")
    cases = relationship("TestCase", back_populates="project")
    runs = relationship("TestRun", back_populates="project")


class TestEnvironment(Base):
    __tablename__ = "test_environments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("test_projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    login_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    environment_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    project = relationship("TestProject", back_populates="environments")
    accounts = relationship("TestAccount", back_populates="test_environment")


class TestAccount(Base):
    __tablename__ = "test_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    system_id: Mapped[int | None] = mapped_column(ForeignKey("test_systems.id"), nullable=True, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("test_projects.id"), nullable=True, index=True)
    environment_id: Mapped[int | None] = mapped_column(
        ForeignKey("test_environments.id"), nullable=True, index=True
    )
    environment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    password_encrypted: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    secret_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    role_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    allow_read: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_write: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allow_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allow_delete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    expires_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    system = relationship("TestSystem", back_populates="accounts")
    project = relationship("TestProject", back_populates="accounts")
    test_environment = relationship("TestEnvironment", back_populates="accounts")

    @property
    def has_password(self) -> bool:
        return bool(self.password_encrypted)


class TestCase(Base):
    __tablename__ = "test_cases"
    __table_args__ = (UniqueConstraint("project_id", "case_code", name="uq_test_cases_project_case_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("test_projects.id"), nullable=False, index=True)
    case_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    case_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), default="manual", nullable=False)
    source_document_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    source_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    instruction: Mapped[str | None] = mapped_column(Text, nullable=True)
    natural_language_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    menu_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    business_intent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    inherit_project_account: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("test_accounts.id"), nullable=True, index=True)
    test_data_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    preconditions_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    success_criteria_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    settings_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(32), default="low", nullable=False)
    dsl_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    current_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    last_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    last_run_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_run_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pass_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project = relationship("TestProject", back_populates="cases")
    runs = relationship("TestRun", back_populates="case")
    versions = relationship("TestCaseVersion", back_populates="case", foreign_keys="TestCaseVersion.case_id")
    account = relationship("TestAccount", foreign_keys=[account_id])


FunctionalTestCase = TestCase


class TestCaseVersion(Base):
    __tablename__ = "test_case_versions"
    __table_args__ = (UniqueConstraint("case_id", "version_no", name="uq_test_case_versions_case_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    version_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    natural_language_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    dsl_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    test_data_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    preconditions_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    success_criteria_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    settings_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    change_type: Mapped[str] = mapped_column(String(64), default="manual_edit", nullable=False)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_analysis_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    source_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    case = relationship("TestCase", back_populates="versions", foreign_keys=[case_id])


class TestRun(Base):
    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("test_projects.id"), nullable=False, index=True)
    system_id: Mapped[int | None] = mapped_column(ForeignKey("test_systems.id"), nullable=True, index=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("test_cases.id"), nullable=True, index=True)
    case_version_id: Mapped[int | None] = mapped_column(ForeignKey("test_case_versions.id"), nullable=True, index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("test_accounts.id"), nullable=True, index=True)
    instruction: Mapped[str | None] = mapped_column(Text, nullable=True)
    instruction_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    base_url_snapshot: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    login_url_snapshot: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    home_url_snapshot: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="created", nullable=False)
    current_phase: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dsl_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    dsl_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    test_data_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    settings_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    account_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    project = relationship("TestProject", back_populates="runs")
    system = relationship("TestSystem", back_populates="runs")
    case = relationship("TestCase", back_populates="runs")
    case_version = relationship("TestCaseVersion", foreign_keys=[case_version_id])
    account = relationship("TestAccount", foreign_keys=[account_id])
    step_runs = relationship("TestStepRun", back_populates="run")


class TestStepRun(Base):
    __tablename__ = "test_step_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("test_runs.id"), nullable=False, index=True)
    step_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    step_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str | None] = mapped_column(String(128), nullable=True)
    target: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="created", nullable=False)
    locator_strategy: Mapped[str | None] = mapped_column(String(128), nullable=True)
    element_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    screenshot_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    run = relationship("TestRun", back_populates="step_runs")


class TestArtifact(Base):
    __tablename__ = "test_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("test_runs.id"), nullable=False, index=True)
    step_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class AbilityRule(Base):
    __tablename__ = "ability_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    rule_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    rule_name: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False)
    intent: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    match_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    action_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    success_criteria_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fallback_strategies_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    failure_patterns_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    recovery_strategies_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(32), default="medium", nullable=False)
    confidence_threshold: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)
    auto_handle: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_human_confirmation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    production_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class AbilityKnowledge(Base):
    __tablename__ = "ability_knowledge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    knowledge_type: Mapped[str] = mapped_column(String(64), nullable=False)
    system_id: Mapped[int | None] = mapped_column(ForeignKey("test_systems.id"), nullable=True, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("test_projects.id"), nullable=True, index=True)
    page_url_pattern: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    page_fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    semantic_target: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_intent: Mapped[str | None] = mapped_column(Text, nullable=True)
    success_locator_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    action_path_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rejected_candidates_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class FailureSample(Base):
    __tablename__ = "failure_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("test_projects.id"), nullable=True, index=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("test_cases.id"), nullable=True, index=True)
    case_version_id: Mapped[int | None] = mapped_column(ForeignKey("test_case_versions.id"), nullable=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("test_runs.id"), nullable=False, index=True)
    step_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    failure_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    failure_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    screenshot_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    dom_snapshot_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    accessibility_snapshot_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    locator_debug_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    runtime_stream_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    execution_trace_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    report_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    ai_analysis_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    suggested_rule_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="new", nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class FailureAnalysis(Base):
    __tablename__ = "failure_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("test_projects.id"), nullable=True, index=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("test_cases.id"), nullable=True, index=True)
    case_version_id: Mapped[int | None] = mapped_column(ForeignKey("test_case_versions.id"), nullable=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("test_runs.id"), nullable=False, index=True)
    failure_sample_id: Mapped[int] = mapped_column(ForeignKey("failure_samples.id"), nullable=False, index=True)
    analysis_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    failure_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    suggestions_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    recommended_actions_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(32), default="medium", nullable=False)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    llm_prompt_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    llm_prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    llm_provider: Mapped[str | None] = mapped_column(String(128), nullable=True)
    elapsed_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class FixApplication(Base):
    __tablename__ = "fix_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("test_projects.id"), nullable=True, index=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("test_cases.id"), nullable=True, index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("test_runs.id"), nullable=True, index=True)
    failure_analysis_id: Mapped[int | None] = mapped_column(ForeignKey("failure_analyses.id"), nullable=True, index=True)
    fix_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    before_snapshot_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_snapshot_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_case_version_id: Mapped[int | None] = mapped_column(ForeignKey("test_case_versions.id"), nullable=True)
    created_rule_draft_id: Mapped[int | None] = mapped_column(ForeignKey("rule_drafts.id"), nullable=True)
    verify_run_id: Mapped[int | None] = mapped_column(ForeignKey("test_runs.id"), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    defect_draft_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    applied_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DocumentSource(Base):
    __tablename__ = "document_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("test_projects.id"), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="uploaded", nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class ExtractedTestCaseDraft(Base):
    __tablename__ = "extracted_test_case_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("test_projects.id"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("document_sources.id"), nullable=False, index=True)
    case_name: Mapped[str] = mapped_column(String(255), nullable=False)
    natural_language_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    menu_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    test_data_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    suggested_account_role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    created_case_id: Mapped[int | None] = mapped_column(ForeignKey("test_cases.id"), nullable=True, index=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class HumanIntervention(Base):
    __tablename__ = "human_interventions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("test_runs.id"), nullable=False, index=True)
    step_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    user_instruction: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_plan_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    execution_result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="submitted", nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class RuleDraft(Base):
    __tablename__ = "rule_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(255), nullable=False)
    proposed_content_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending_review", nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class RuntimeMessage(Base):
    __tablename__ = "runtime_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("test_runs.id"), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    phase: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    value_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class LLMCallLog(Base):
    __tablename__ = "llm_call_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    step_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    prompt_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    elapsed_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
