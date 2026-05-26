import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models import TestAccount, TestProject, TestSystem
from app.schemas.systems import LoginCheckRequest, SystemCheckResult, TestSystemCreate, TestSystemUpdate
from app.utils.secrets import decrypt_secret, encrypt_secret


def list_systems(db: Session) -> list[TestSystem]:
    return list(
        db.scalars(
            select(TestSystem)
            .options(selectinload(TestSystem.accounts))
            .order_by(TestSystem.id.desc())
        ).all()
    )


def get_system(db: Session, system_id: int) -> TestSystem | None:
    return db.scalars(
        select(TestSystem)
        .options(selectinload(TestSystem.accounts))
        .where(TestSystem.id == system_id)
    ).first()


def create_system(db: Session, payload: TestSystemCreate) -> TestSystem:
    data = payload.model_dump(exclude={"default_account"})
    system = TestSystem(**data)
    db.add(system)
    db.flush()
    if payload.default_account:
        db.add(_account_from_payload(db, system.id, payload.default_account.model_dump()))
    db.commit()
    db.refresh(system)
    return get_system(db, system.id) or system


def update_system(db: Session, system: TestSystem, payload: TestSystemUpdate) -> TestSystem:
    update_data = payload.model_dump(exclude_unset=True, exclude={"default_account"})
    for field_name, value in update_data.items():
        setattr(system, field_name, value)
    if payload.default_account:
        account = _get_default_account(db, system.id)
        account_data = payload.default_account.model_dump()
        if account is None:
            db.add(_account_from_payload(db, system.id, account_data))
        else:
            _update_account_from_payload(account, account_data)
            db.add(account)
    db.add(system)
    db.commit()
    db.refresh(system)
    return get_system(db, system.id) or system


def check_connectivity(db: Session, system: TestSystem) -> SystemCheckResult:
    started = time.perf_counter()
    http_status = None
    message = "Connectivity check completed."
    status = "passed"
    metadata: dict[str, Any] = {}
    try:
        verify_tls = bool((system.config_json or {}).get("verify_tls", True))
        with httpx.Client(follow_redirects=True, verify=verify_tls, timeout=system.default_timeout_ms / 1000) as client:
            response = client.get(system.base_url)
            http_status = response.status_code
            metadata["final_url"] = str(response.url)
            if response.status_code >= 400:
                status = "failed"
                message = f"Connectivity check returned HTTP {response.status_code}."
    except Exception as exc:
        status = "failed"
        message = str(exc)
    response_time_ms = int((time.perf_counter() - started) * 1000)
    screenshot_path = _capture_page_screenshot(system, system.base_url, "connectivity")
    result = SystemCheckResult(
        system_id=system.id,
        check_type="connectivity",
        status=status,
        http_status=http_status,
        response_time_ms=response_time_ms,
        screenshot_path=screenshot_path,
        message=message,
        metadata=metadata,
    )
    _store_last_check(db, system, "last_connectivity_check", result.model_dump())
    return result


def check_login(db: Session, system: TestSystem, payload: LoginCheckRequest | None = None) -> SystemCheckResult:
    payload = payload or LoginCheckRequest()
    account = db.get(TestAccount, payload.account_id) if payload.account_id else _get_default_account(db, system.id)
    username = payload.username or (account.username if account else None)
    password = payload.password or decrypt_secret(account.password_encrypted if account else None)
    if not username or not password:
        raise ValueError("A username and password are required for login check.")
    if not system.login_url:
        raise ValueError("System login_url is required for login check.")

    run_dir = _system_check_dir(system, "login")
    screenshot_path = _relative(run_dir / "login-check.png")
    runtime_path = _relative(run_dir / "runtime-stream.jsonl")
    runtime_events: list[dict[str, Any]] = []

    def emit(message_type: str, phase: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        event = {
            "type": message_type,
            "phase": phase,
            "content": content,
            "method": "system_login_check",
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        runtime_events.append(event)
        with open(Path(runtime_path), "a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")

    status = "failed"
    message = "Login check failed."
    http_status = None
    started = time.perf_counter()
    metadata: dict[str, Any] = {}
    run_dir.mkdir(parents=True, exist_ok=True)
    Path(runtime_path).write_text("", encoding="utf-8")

    try:
        emit("progress", "browser", "正在启动浏览器")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(system.default_timeout_ms)
            emit("progress", "open_login", "正在打开登录页", {"url": system.login_url})
            response = page.goto(system.login_url, wait_until="domcontentloaded", timeout=system.default_timeout_ms)
            http_status = response.status if response else None
            emit("progress", "observe", "正在读取页面")
            _handle_global_interruptions(page, emit)
            emit("progress", "input_username", "正在填写用户名")
            _fill_first(page, ["用户名", "账号", "登录名", "用户名/账号", "username", "account"], username)
            emit("progress", "input_password", "正在填写密码")
            _fill_password(page, password)
            emit("progress", "submit", "正在点击登录")
            _click_first(page, ["登录", "登 录", "确定", "提交", "Sign in", "Login"])
            page.wait_for_load_state("domcontentloaded", timeout=system.default_timeout_ms)
            _handle_global_interruptions(page, emit)
            emit("progress", "verify", "正在验证登录结果")
            if _login_success(page, system):
                status = "passed"
                message = "Login check passed."
                emit("success", "completed", "登录检查通过", {"url": page.url})
            else:
                message = "Login check did not reach the expected home page or main page signal."
                emit("error", "completed", message, {"url": page.url})
            metadata["final_url"] = page.url
            page.screenshot(path=str(Path(screenshot_path)), full_page=True)
            browser.close()
    except (PlaywrightError, PlaywrightTimeoutError, RuntimeError) as exc:
        message = str(exc)
        emit("error", "failed", message)
    response_time_ms = int((time.perf_counter() - started) * 1000)
    result = SystemCheckResult(
        system_id=system.id,
        check_type="login",
        status=status,
        http_status=http_status,
        response_time_ms=response_time_ms,
        screenshot_path=screenshot_path if Path(screenshot_path).exists() else None,
        runtime_stream_path=runtime_path,
        message=message,
        metadata=metadata,
    )
    _store_last_check(db, system, "last_login_check", result.model_dump())
    return result


def _account_from_payload(db: Session, system_id: int, payload: dict[str, Any]) -> TestAccount:
    default_project_id = db.scalar(select(TestProject.id).order_by(TestProject.id))
    return TestAccount(
        system_id=system_id,
        project_id=default_project_id,
        environment=payload.get("environment"),
        username=payload["username"],
        password_encrypted=encrypt_secret(payload.get("password")),
        secret_ref=payload.get("secret_ref"),
        role_name=payload.get("role_name"),
        allow_write=bool(payload.get("allow_write", False)),
        allow_approval=bool(payload.get("allow_approval", False)),
        allow_delete=bool(payload.get("allow_delete", False)),
        status=payload.get("status") or "active",
        expires_at=payload.get("expires_at"),
    )


def _update_account_from_payload(account: TestAccount, payload: dict[str, Any]) -> None:
    account.environment = payload.get("environment")
    account.username = payload["username"]
    if payload.get("password"):
        account.password_encrypted = encrypt_secret(payload.get("password"))
    account.secret_ref = payload.get("secret_ref")
    account.role_name = payload.get("role_name")
    account.allow_write = bool(payload.get("allow_write", False))
    account.allow_approval = bool(payload.get("allow_approval", False))
    account.allow_delete = bool(payload.get("allow_delete", False))
    account.status = payload.get("status") or "active"
    account.expires_at = payload.get("expires_at")


def _get_default_account(db: Session, system_id: int) -> TestAccount | None:
    return db.scalars(
        select(TestAccount)
        .where(TestAccount.system_id == system_id, TestAccount.status == "active")
        .order_by(TestAccount.id)
    ).first()


def _store_last_check(db: Session, system: TestSystem, key: str, value: dict[str, Any]) -> None:
    config = dict(system.config_json or {})
    config[key] = value
    system.config_json = config
    db.add(system)
    db.commit()


def _capture_page_screenshot(system: TestSystem, url: str, check_type: str) -> str | None:
    run_dir = _system_check_dir(system, check_type)
    run_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = run_dir / f"{check_type}.png"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=system.default_timeout_ms)
            page.screenshot(path=str(screenshot_path), full_page=True)
            browser.close()
        return _relative(screenshot_path)
    except PlaywrightError:
        return None


def _system_check_dir(system: TestSystem, check_type: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    safe_code = re.sub(r"[^A-Za-z0-9_.-]+", "_", system.system_code)
    return Path(settings.artifacts_dir) / "system-checks" / safe_code / f"{stamp}-{check_type}"


def _relative(path: Path) -> str:
    return str(path.as_posix())


def _fill_first(page: Any, labels: list[str], value: str) -> None:
    for label in labels:
        locator = page.get_by_label(label, exact=True)
        if locator.count() == 1:
            locator.fill(value)
            return
    for selector in [
        'input[name*="user" i]',
        'input[id*="user" i]',
        'input[name*="account" i]',
        'input[id*="account" i]',
        "input[type=text]",
    ]:
        locator = page.locator(selector).first
        if locator.count() > 0:
            locator.fill(value)
            return
    raise RuntimeError("Username field was not found.")


def _fill_password(page: Any, value: str) -> None:
    password = page.locator("input[type=password]").first
    if password.count() > 0:
        password.fill(value)
        return
    for label in ["密码", "口令", "password"]:
        locator = page.get_by_label(label, exact=True)
        if locator.count() == 1:
            locator.fill(value)
            return
    raise RuntimeError("Password field was not found.")


def _click_first(page: Any, names: list[str]) -> None:
    for name in names:
        button = page.get_by_role("button", name=name, exact=True)
        if button.count() > 0:
            button.first.click()
            return
        text = page.get_by_text(name, exact=True)
        if text.count() == 1:
            text.click()
            return
    submit = page.locator("button[type=submit], input[type=submit]").first
    if submit.count() > 0:
        submit.click()
        return
    raise RuntimeError("Login submit action was not found.")


def _handle_global_interruptions(page: Any, emit) -> None:
    for name in ["我知道了", "关闭", "跳过", "稍后", "继续访问", "确定"]:
        button = page.get_by_role("button", name=name, exact=True)
        if button.count() > 0:
            emit("warning", "global_interruption", "检测到全局中断提示，正在尝试关闭", {"button": name})
            button.first.click()
            return


def _login_success(page: Any, system: TestSystem) -> bool:
    if system.home_url and page.url.startswith(system.home_url):
        return True
    signals = (system.config_json or {}).get("home_signals") or ["退出", "工作台", "首页", "个人中心", "菜单"]
    for signal in signals:
        try:
            if page.get_by_text(str(signal), exact=False).count() > 0:
                return True
        except PlaywrightError:
            continue
    if page.locator("input[type=password]").count() == 0 and page.get_by_role("button", name="登录", exact=True).count() == 0:
        return True
    return False
