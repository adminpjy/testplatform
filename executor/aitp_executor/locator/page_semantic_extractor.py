from typing import Any

from executor.aitp_executor.observer.page_observer import PageObservation


class PageSemanticExtractor:
    def extract(self, observation: PageObservation) -> list[dict[str, Any]]:
        candidates = []
        for element in observation.elements:
            searchable = " ".join(
                str(element.get(key) or "")
                for key in ["text", "label", "ariaLabel", "placeholder", "id", "name", "role", "tag"]
            )
            candidates.append({**element, "searchable": searchable.lower()})
        return candidates
