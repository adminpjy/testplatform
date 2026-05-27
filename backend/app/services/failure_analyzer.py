from typing import Any

from executor.aitp_executor.goal.recovery_policy import RecoveryPolicy


class FailureAnalyzer:
    def __init__(self, *, recovery_policy: RecoveryPolicy | None = None) -> None:
        self.recovery_policy = recovery_policy or RecoveryPolicy()

    def analyze_step_failure(self, step_result: dict[str, Any]) -> dict[str, Any]:
        existing = step_result.get("failure_analysis")
        if isinstance(existing, dict) and existing.get("failureType"):
            return _normalize_payload(existing)
        return self.recovery_policy.analyze_failure(
            error_summary=step_result.get("error_summary"),
            action=step_result.get("action"),
            target=step_result.get("target"),
            failure_type=step_result.get("failure_type"),
            fallback_reason=step_result.get("fallback_reason"),
            details=step_result.get("failure_details"),
        )

    def failure_type(self, step_result: dict[str, Any]) -> str:
        return str(self.analyze_step_failure(step_result).get("failureType") or "unknown_failure")


def analyze_step_failure(step_result: dict[str, Any]) -> dict[str, Any]:
    return FailureAnalyzer().analyze_step_failure(step_result)


def failure_type(step_result: dict[str, Any]) -> str:
    return FailureAnalyzer().failure_type(step_result)


def _normalize_payload(value: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(value)
    normalized.setdefault("suggestedRecovery", [])
    normalized.setdefault("attemptedStrategies", [])
    normalized.setdefault("canIntervene", True)
    normalized.setdefault("canGenerateRuleDraft", True)
    return normalized
