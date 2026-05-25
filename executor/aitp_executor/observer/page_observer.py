from dataclasses import dataclass
from typing import Any


@dataclass
class PageObservation:
    url: str
    title: str
    visible_text: str
    elements: list[dict[str, Any]]


class PageObserver:
    def observe(self, page: Any) -> PageObservation:
        title = page.title()
        visible_text = page.locator("body").inner_text(timeout=3000) if page.locator("body").count() else ""
        elements = page.locator(
            "button, input, textarea, select, a, [role='button'], [data-testid], [aria-label]"
        ).evaluate_all(_ELEMENT_EXTRACTOR)
        return PageObservation(
            url=page.url,
            title=title,
            visible_text=visible_text[:8000],
            elements=[element for element in elements if element.get("visible")],
        )


_ELEMENT_EXTRACTOR = """(elements) => {
  function cssPath(el) {
    if (el.id) {
      return "#" + CSS.escape(el.id);
    }
    const parts = [];
    let node = el;
    while (node && node.nodeType === Node.ELEMENT_NODE && node !== document.body) {
      let part = node.tagName.toLowerCase();
      const parent = node.parentElement;
      if (parent) {
        const siblings = Array.from(parent.children).filter((item) => item.tagName === node.tagName);
        if (siblings.length > 1) {
          part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
        }
      }
      parts.unshift(part);
      node = parent;
    }
    return parts.join(" > ");
  }

  function labelFor(el) {
    if (el.labels && el.labels.length) {
      return Array.from(el.labels).map((label) => label.innerText.trim()).filter(Boolean).join(" ");
    }
    if (el.id) {
      const label = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (label) return label.innerText.trim();
    }
    const wrapper = el.closest("label");
    return wrapper ? wrapper.innerText.trim() : "";
  }

  function implicitRole(el) {
    const tag = el.tagName.toLowerCase();
    if (tag === "button") return "button";
    if (tag === "a") return "link";
    if (tag === "select") return "combobox";
    if (tag === "textarea") return "textbox";
    if (tag === "input") {
      const type = (el.getAttribute("type") || "text").toLowerCase();
      if (type === "button" || type === "submit") return "button";
      if (type === "checkbox") return "checkbox";
      if (type === "radio") return "radio";
      return "textbox";
    }
    return "";
  }

  return elements.map((el) => {
    const rect = el.getBoundingClientRect();
    const tag = el.tagName.toLowerCase();
    const label = labelFor(el);
    const ariaLabel = el.getAttribute("aria-label") || "";
    const placeholder = el.getAttribute("placeholder") || "";
    const text = (el.innerText || el.value || ariaLabel || placeholder || label || "").trim();
    return {
      selector: cssPath(el),
      tag,
      role: el.getAttribute("role") || implicitRole(el),
      text,
      label,
      ariaLabel,
      placeholder,
      id: el.id || "",
      name: el.getAttribute("name") || "",
      type: el.getAttribute("type") || "",
      href: el.getAttribute("href") || "",
      visible: rect.width > 0 && rect.height > 0,
      rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
    };
  });
}"""
