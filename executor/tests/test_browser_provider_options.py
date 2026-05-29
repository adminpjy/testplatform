from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from executor.aitp_executor.browser.cube_sandbox_provider import CubeSandboxProvider
from executor.aitp_executor.browser.local_playwright_provider import _context_options, _launch_options


def test_cube_sandbox_provider_enables_certificate_bypass_by_default() -> None:
    provider = CubeSandboxProvider()

    context_options = _context_options(
        ignore_https_errors=provider.ignore_https_errors,
        auto_continue_security_interstitial=provider.auto_continue_security_interstitial,
    )
    launch_options = _launch_options(
        ignore_https_errors=provider.ignore_https_errors,
        auto_continue_security_interstitial=provider.auto_continue_security_interstitial,
    )

    assert context_options["ignore_https_errors"] is True
    assert "--ignore-certificate-errors" in launch_options["args"]


def test_local_provider_certificate_bypass_can_be_enabled_by_env(monkeypatch) -> None:
    monkeypatch.setenv("PLAYWRIGHT_AUTO_CONTINUE_SECURITY_INTERSTITIAL", "true")

    assert _context_options()["ignore_https_errors"] is True
    assert "--ignore-certificate-errors" in _launch_options()["args"]
