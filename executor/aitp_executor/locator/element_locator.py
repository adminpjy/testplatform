from dataclasses import dataclass, field
from typing import Any

from executor.aitp_executor.locator.ambiguity_resolver import AmbiguityResolver
from executor.aitp_executor.locator.business_intent_normalizer import BusinessIntentNormalizer
from executor.aitp_executor.locator.candidate_ranker import CandidateRanker
from executor.aitp_executor.locator.llm_element_resolver import LLMElementResolver
from executor.aitp_executor.locator.page_semantic_extractor import PageSemanticExtractor
from executor.aitp_executor.locator.vision_resolver import VisionResolver
from executor.aitp_executor.observer.page_observer import PageObserver


@dataclass
class LocatorResult:
    locator: Any | None
    strategy: str
    element_ref: str | None
    confidence: float
    reason: str
    needs_vision_fallback: bool = False
    fallback_reason: str | None = None
    candidates: list[dict[str, Any]] = field(default_factory=list)


class ElementLocator:
    def __init__(
        self,
        *,
        observer: PageObserver | None = None,
        semantic_extractor: PageSemanticExtractor | None = None,
        normalizer: BusinessIntentNormalizer | None = None,
        ranker: CandidateRanker | None = None,
        ambiguity_resolver: AmbiguityResolver | None = None,
        llm_resolver: LLMElementResolver | None = None,
        vision_resolver: VisionResolver | None = None,
    ) -> None:
        self.observer = observer or PageObserver()
        self.semantic_extractor = semantic_extractor or PageSemanticExtractor()
        self.normalizer = normalizer or BusinessIntentNormalizer()
        self.ranker = ranker or CandidateRanker()
        self.ambiguity_resolver = ambiguity_resolver or AmbiguityResolver()
        self.llm_resolver = llm_resolver or LLMElementResolver()
        self.vision_resolver = vision_resolver or VisionResolver(configured=False)

    def locate(self, page: Any, *, action: str, target: str, step: dict[str, Any] | None = None) -> LocatorResult:
        step = step or {}

        knowledge_selector = step.get("knowledge_selector")
        if knowledge_selector:
            locator = page.locator(str(knowledge_selector))
            if locator.count() > 0:
                return LocatorResult(locator, "knowledge_base", str(knowledge_selector), 0.99, "knowledge selector")

        if step.get("selector"):
            selector = str(step["selector"])
            locator = page.locator(selector)
            if locator.count() > 0:
                return LocatorResult(locator, "explicit_selector", selector, 0.98, "explicit selector")

        direct = self._direct_playwright(page, action=action, target=target)
        if direct is not None:
            return direct

        observation = self.observer.observe(page)
        candidates = self.semantic_extractor.extract(observation)
        intent = self.normalizer.normalize(action=action, target=target)
        ranked = self.ranker.rank(candidates=candidates, intent=intent, action=action)
        decision = self.ambiguity_resolver.resolve(ranked)
        ranked_payload = [
            {
                "text": item.element.get("text"),
                "label": item.element.get("label"),
                "role": item.element.get("role"),
                "selector": item.element.get("selector"),
                "score": item.score,
                "reason": item.reason,
            }
            for item in ranked[:8]
        ]

        if decision.selected and not decision.needs_vision_fallback:
            selector = str(decision.selected.element.get("selector"))
            return LocatorResult(
                page.locator(selector),
                f"page_semantic:{intent.name}",
                decision.selected.element.get("text") or decision.selected.element.get("label") or selector,
                decision.confidence,
                decision.reason,
                candidates=ranked_payload,
            )

        llm_result = self.llm_resolver.resolve(
            page_context={
                "url": observation.url,
                "title": observation.title,
                "visible_text": observation.visible_text[:2000],
                "candidates": ranked_payload,
            },
            target=target,
            action=action,
        )
        if llm_result.selector:
            return LocatorResult(
                page.locator(llm_result.selector),
                "llm_resolver",
                llm_result.selector,
                llm_result.confidence,
                llm_result.reason,
                candidates=ranked_payload,
            )

        vision_result = self.vision_resolver.resolve(page=page, target=target, action=action)
        selected = decision.selected
        if selected and selected.score > 0 and vision_result.selector:
            selector = str(selected.element.get("selector"))
            return LocatorResult(
                page.locator(selector),
                f"low_confidence_semantic:{intent.name}",
                selected.element.get("text") or selected.element.get("label") or selector,
                selected.score,
                decision.reason,
                needs_vision_fallback=True,
                fallback_reason=vision_result.status,
                candidates=ranked_payload,
            )

        return LocatorResult(
            None,
            "vision_fallback",
            None,
            0.0,
            decision.reason,
            needs_vision_fallback=True,
            fallback_reason=vision_result.status,
            candidates=ranked_payload,
        )

    def _direct_playwright(self, page: Any, *, action: str, target: str) -> LocatorResult | None:
        if not target:
            return None

        target_text = target.split("/")[-1] if "/" in target else target
        if action in {"input", "select", "upload_file"}:
            label = page.get_by_label(target_text, exact=True)
            if label.count() == 1:
                return LocatorResult(label, "playwright_label_exact", target_text, 0.96, "label exact")

        if action == "navigate_menu":
            menu = page.locator("aside").get_by_role("button", name=target_text, exact=True)
            if menu.count() == 1:
                return LocatorResult(menu, "playwright_side_menu_exact", target_text, 0.96, "side menu exact")

        if action in {"click", "confirm_dialog"}:
            role = page.get_by_role("button", name=target_text, exact=True)
            if role.count() == 1:
                return LocatorResult(role, "playwright_button_exact", target_text, 0.95, "button exact")
            link = page.get_by_role("link", name=target_text, exact=True)
            if link.count() == 1:
                return LocatorResult(link, "playwright_link_exact", target_text, 0.93, "link exact")
            text = page.get_by_text(target_text, exact=True)
            if text.count() == 1:
                return LocatorResult(text, "playwright_text_exact", target_text, 0.86, "text exact")

        return None
