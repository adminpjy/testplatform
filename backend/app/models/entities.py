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
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("platform_users.id"), nullable=True, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("platform_users.id"), nullable=True, index=True)
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
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("platform_users.id"), nullable=True, index=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("platform_users.id"), nullable=True, index=True)
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
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("test_campaigns.id"), nullable=True, index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("test_accounts.id"), nullable=True, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("platform_users.id"), nullable=True, index=True)
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
    generalized_pattern_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    solution_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rule_draft_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    validation_plan_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    user_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_raw_response_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
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


class FailurePattern(Base):
    __tablename__ = "failure_patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    pattern_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    pattern_name: Mapped[str] = mapped_column(String(255), nullable=False)
    failure_type: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    generalized_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_schema_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    applicability_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    exclusion_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(32), default="medium", nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_sample_ids_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class FailureSolution(Base):
    __tablename__ = "failure_solutions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    solution_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    failure_sample_id: Mapped[int] = mapped_column(ForeignKey("failure_samples.id"), nullable=False, index=True)
    failure_analysis_id: Mapped[int | None] = mapped_column(ForeignKey("failure_analyses.id"), nullable=True, index=True)
    pattern_id: Mapped[int | None] = mapped_column(ForeignKey("failure_patterns.id"), nullable=True, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("test_projects.id"), nullable=True, index=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("test_cases.id"), nullable=True, index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("test_runs.id"), nullable=True, index=True)
    rule_draft_id: Mapped[int | None] = mapped_column(ForeignKey("rule_drafts.id"), nullable=True, index=True)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    solution_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    generalized_pattern_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    strategy_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    suggested_rule_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    validation_plan_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    context_snapshot_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    llm_prompt_snapshot_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    llm_response_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    user_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_adjustment_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("platform_users.id"), nullable=True, index=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("platform_users.id"), nullable=True, index=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class RuleValidation(Base):
    __tablename__ = "rule_validations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    validation_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    solution_id: Mapped[int | None] = mapped_column(ForeignKey("failure_solutions.id"), nullable=True, index=True)
    rule_draft_id: Mapped[int | None] = mapped_column(ForeignKey("rule_drafts.id"), nullable=True, index=True)
    ability_rule_id: Mapped[int | None] = mapped_column(ForeignKey("ability_rules.id"), nullable=True, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("test_projects.id"), nullable=True, index=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("test_cases.id"), nullable=True, index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("test_runs.id"), nullable=True, index=True)
    validation_type: Mapped[str] = mapped_column(String(64), default="evidence_static_precheck", nullable=False)
    sample_ids_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="created", nullable=False)
    passed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    false_positive_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    report_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("platform_users.id"), nullable=True, index=True)
    started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class ProjectBootstrapPackage(Base):
    __tablename__ = "project_bootstrap_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("test_projects.id"), nullable=False, index=True)
    package_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft_generated", nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), default="two_file_compare", nullable=False)
    file_a_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_a_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    file_a_role: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_b_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_b_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    file_b_role: Mapped[str | None] = mapped_column(String(128), nullable=True)
    generator_result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    draft_cases_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    imported_case_ids_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class PrescanSession(Base):
    __tablename__ = "prescan_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("test_projects.id"), nullable=False, index=True)
    session_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="created", nullable=False)
    mode: Mapped[str] = mapped_column(String(64), default="case_driven", nullable=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    case_ids_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    plan_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    findings_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rule_draft_ids_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ability_knowledge_ids_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    enhanced_cases_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class TestCampaign(Base):
    __tablename__ = "test_campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("test_projects.id"), nullable=False, index=True)
    campaign_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="created", nullable=False)
    case_ids_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    settings_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    queued_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    running_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    blocked_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("platform_users.id"), nullable=True, index=True)
    started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class TestCampaignCase(Base):
    __tablename__ = "test_campaign_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("test_campaigns.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("test_projects.id"), nullable=False, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"), nullable=False, index=True)
    case_version_id: Mapped[int | None] = mapped_column(ForeignKey("test_case_versions.id"), nullable=True, index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("test_runs.id"), nullable=True, index=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    failure_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class MaintenanceFeedback(Base):
    __tablename__ = "maintenance_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    feedback_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("test_projects.id"), nullable=True, index=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("test_cases.id"), nullable=True, index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("test_runs.id"), nullable=True, index=True)
    failure_sample_id: Mapped[int | None] = mapped_column(ForeignKey("failure_samples.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="submitted", nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_package_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    artifact_paths_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    maintainer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class MaintenanceResponse(Base):
    __tablename__ = "maintenance_responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    response_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    failure_sample_id: Mapped[int | None] = mapped_column(ForeignKey("failure_samples.id"), nullable=True, index=True)
    solution_id: Mapped[int | None] = mapped_column(ForeignKey("failure_solutions.id"), nullable=True, index=True)
    validation_id: Mapped[int | None] = mapped_column(ForeignKey("rule_validations.id"), nullable=True, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("test_projects.id"), nullable=True, index=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("test_cases.id"), nullable=True, index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("test_runs.id"), nullable=True, index=True)
    submitted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("platform_users.id"), nullable=True, index=True)
    handled_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("platform_users.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    fix_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    resolved_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class TestAsset(Base):
    __tablename__ = "test_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    asset_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    asset_name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("test_projects.id"), nullable=True, index=True)
    module: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    tags_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False, index=True)
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    latest_published_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_from: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    risk_level: Mapped[str] = mapped_column(String(32), default="low", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class TestAssetVersion(Base):
    __tablename__ = "test_asset_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("test_assets.id"), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    version_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    content_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    diff_summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class DefectCandidate(Base):
    __tablename__ = "defect_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    defect_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("test_projects.id"), nullable=True, index=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("test_cases.id"), nullable=True, index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("test_runs.id"), nullable=True, index=True)
    failure_sample_id: Mapped[int | None] = mapped_column(ForeignKey("failure_samples.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    defect_type: Mapped[str] = mapped_column(String(64), default="system_defect", nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(32), default="medium", nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(32), default="normal", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="candidate", nullable=False, index=True)
    assignee: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reproduce_steps_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    external_ref_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    dedup_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class LearningItem(Base):
    __tablename__ = "learning_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    learning_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("test_projects.id"), nullable=True, index=True)
    item_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="proposed", nullable=False, index=True)
    source_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    risk_level: Mapped[str] = mapped_column(String(32), default="medium", nullable=False)
    proposal_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    validation_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    audit_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class PlatformUser(Base):
    __tablename__ = "platform_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(64), default="testuser", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(512), nullable=True)
    config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class ProjectMembership(Base):
    __tablename__ = "project_memberships"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_memberships_project_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("test_projects.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("platform_users.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(64), default="testuser", nullable=False, index=True)
    permissions_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("platform_users.id"), nullable=True, index=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("test_projects.id"), nullable=True, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("platform_users.id"), nullable=True, index=True)
    actor: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("test_cases.id"), nullable=True, index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("test_runs.id"), nullable=True, index=True)
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("test_campaigns.id"), nullable=True, index=True)
    result: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    risk_level: Mapped[str] = mapped_column(String(32), default="low", nullable=False)
    before_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    detail_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class SecretVaultItem(Base):
    __tablename__ = "secret_vault_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    secret_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("test_projects.id"), nullable=True, index=True)
    secret_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    expires_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class PlatformPlugin(Base):
    __tablename__ = "platform_plugins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plugin_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    plugin_name: Mapped[str] = mapped_column(String(255), nullable=False)
    plugin_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    config_schema_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    health_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
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
