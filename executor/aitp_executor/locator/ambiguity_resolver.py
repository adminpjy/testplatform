from dataclasses import dataclass

from executor.aitp_executor.locator.candidate_ranker import RankedCandidate


@dataclass
class AmbiguityDecision:
    selected: RankedCandidate | None
    confidence: float
    status: str
    reason: str
    needs_vision_fallback: bool = False


class AmbiguityResolver:
    def resolve(self, ranked: list[RankedCandidate], *, threshold: float = 0.62) -> AmbiguityDecision:
        if not ranked:
            return AmbiguityDecision(
                selected=None,
                confidence=0.0,
                status="low_confidence",
                reason="no_semantic_candidate",
                needs_vision_fallback=True,
            )

        top = ranked[0]
        second = ranked[1] if len(ranked) > 1 else None
        if top.score < threshold:
            return AmbiguityDecision(
                selected=top,
                confidence=top.score,
                status="low_confidence",
                reason=f"top_score_below_threshold:{top.reason}",
                needs_vision_fallback=True,
            )

        if second and top.score - second.score < 0.05 and top.element.get("text") != second.element.get("text"):
            return AmbiguityDecision(
                selected=top,
                confidence=top.score,
                status="ambiguous_selected_top",
                reason=f"close_score:{top.reason}",
                needs_vision_fallback=False,
            )

        return AmbiguityDecision(
            selected=top,
            confidence=top.score,
            status="selected",
            reason=top.reason,
            needs_vision_fallback=False,
        )
