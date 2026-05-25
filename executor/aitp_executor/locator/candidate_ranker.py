from dataclasses import dataclass
from typing import Any

from executor.aitp_executor.locator.business_intent_normalizer import BusinessIntent


@dataclass
class RankedCandidate:
    element: dict[str, Any]
    score: float
    reason: str


class CandidateRanker:
    def rank(
        self,
        *,
        candidates: list[dict[str, Any]],
        intent: BusinessIntent,
        action: str,
    ) -> list[RankedCandidate]:
        ranked = [self._score(candidate, intent, action) for candidate in candidates]
        ranked = [candidate for candidate in ranked if candidate.score > 0]
        ranked.sort(key=lambda item: (-item.score, item.element.get("rect", {}).get("y", 0)))
        return ranked

    def _score(self, candidate: dict[str, Any], intent: BusinessIntent, action: str) -> RankedCandidate:
        searchable = str(candidate.get("searchable") or "").lower()
        text = str(candidate.get("text") or candidate.get("label") or "")
        label = str(candidate.get("label") or "")
        role = str(candidate.get("role") or "")
        selector = str(candidate.get("selector") or "")
        score = 0.0
        reasons = []

        if role in intent.preferred_roles:
            score += 0.12
            reasons.append(f"role={role}")

        for negative in intent.negative_texts:
            if negative and negative.lower() in searchable:
                score -= 0.55
                reasons.append(f"negative={negative}")

        for preferred in intent.preferred_texts:
            if not preferred:
                continue
            preferred_lower = preferred.lower()
            if text == preferred or label == preferred:
                score += 0.55
                reasons.append(f"exact={preferred}")
            elif preferred_lower in searchable:
                score += 0.24
                reasons.append(f"contains={preferred}")

        target_lower = intent.normalized_target.lower()
        if target_lower:
            if text == intent.normalized_target or label == intent.normalized_target:
                score += 0.28
                reasons.append("target_exact")
            elif target_lower in searchable:
                score += 0.14
                reasons.append("target_contains")

        if action in {"input", "select", "upload_file"}:
            if label == intent.normalized_target:
                score += 0.45
                reasons.append("input_label_exact")
            if candidate.get("id") == "j_name" and intent.normalized_target == "用户名":
                score += 0.30
                reasons.append("legacy_username_id")
            if candidate.get("tag") in {"input", "textarea", "select"}:
                score += 0.12
                reasons.append("form_control")

        if intent.name == "approval_pass":
            if text == "审批":
                score += 0.50
                reasons.append("approval_action_exact")
            if "查看审批流程" in searchable:
                score -= 0.70
                reasons.append("avoid_flow_view")
        elif intent.name == "approval_flow_view":
            if text == "查看审批流程":
                score += 0.60
                reasons.append("flow_view_exact")
            if text == "审批":
                score -= 0.30
                reasons.append("avoid_approval_action")
        elif intent.name == "enter_todo_list":
            if text == "我的待办" and ("aside" in selector or role in {"button", "link"}):
                score += 0.35
                reasons.append("todo_entry")

        return RankedCandidate(
            element=candidate,
            score=round(max(0.0, min(1.0, score)), 4),
            reason=";".join(reasons) if reasons else "no_match",
        )
