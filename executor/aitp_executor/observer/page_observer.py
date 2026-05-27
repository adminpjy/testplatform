from dataclasses import dataclass
from typing import Any


@dataclass
class PageObservation:
    url: str
    title: str
    visible_text: str
    elements: list[dict[str, Any]]
    menus: list[dict[str, Any]]


class PageObserver:
    def observe(self, page: Any) -> PageObservation:
        title = page.title()
        visible_text = page.locator("body").inner_text(timeout=3000) if page.locator("body").count() else ""
        elements = page.locator(
            "button, input, textarea, select, a, [role='button'], [role='menuitem'], [role='tab'], [data-testid], [aria-label]"
        ).evaluate_all(_ELEMENT_EXTRACTOR)
        menus = self._extract_menus(page)
        return PageObservation(
            url=page.url,
            title=title,
            visible_text=visible_text[:8000],
            elements=[element for element in elements if element.get("visible")],
            menus=menus,
        )

    def _extract_menus(self, page: Any) -> list[dict[str, Any]]:
        menu_selector = ",".join(
            [
                "[role='menuitem']",
                "[role='tab']",
                "nav a",
                "nav button",
                "aside a",
                "aside button",
                ".menu a",
                ".menu button",
                ".sidebar a",
                ".sidebar button",
                ".ant-menu-item",
                ".ant-menu-submenu-title",
                ".el-menu-item",
                ".el-submenu__title",
                ".tabs [role='tab']",
                ".breadcrumb a",
                ".ant-breadcrumb a",
                ".el-breadcrumb a",
                ".card",
                ".shortcut",
            ]
        )
        menus: list[dict[str, Any]] = []
        try:
            menus.extend(page.locator(menu_selector).evaluate_all(_MENU_EXTRACTOR))
        except Exception:
            pass
        for frame_index, frame in enumerate(page.frames):
            if frame == page.main_frame:
                continue
            try:
                frame_menus = frame.locator(menu_selector).evaluate_all(_MENU_EXTRACTOR)
            except Exception:
                continue
            for item in frame_menus:
                item["elementRef"] = f"F{frame_index + 1}-{item.get('elementRef') or ''}"
                item["frameUrl"] = frame.url
                item["inFrame"] = True
                menus.append(item)
        return [item for item in menus if item.get("visible") and item.get("text")]


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


_MENU_EXTRACTOR = """(elements) => {
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

  function textOf(el) {
    return (el.innerText || el.textContent || el.getAttribute("aria-label") || el.getAttribute("title") || "").trim();
  }

  function areaOf(el) {
    if (el.closest(".ant-breadcrumb,.el-breadcrumb,.breadcrumb,[aria-label*='breadcrumb' i]")) return "breadcrumb";
    if (el.closest(".tabs,.ant-tabs,.el-tabs,[role='tablist']")) return "tab";
    if (el.closest("aside,.sidebar,.side-menu,.ant-layout-sider,.el-aside")) return "left_menu";
    if (el.closest("header,.top-nav,.navbar,.ant-menu-horizontal,nav")) return "top_nav";
    if (el.closest(".card,.shortcut,.quick-entry,.workbench,.dashboard")) return "dashboard_card";
    return "unknown";
  }

  function levelOf(el) {
    const ariaLevel = Number(el.getAttribute("aria-level") || "");
    if (Number.isFinite(ariaLevel) && ariaLevel > 0) return ariaLevel;
    let submenuDepth = 0;
    let cursor = el.parentElement;
    while (cursor && cursor !== document.body) {
      if (cursor.classList && (cursor.classList.contains("ant-menu-submenu") || cursor.classList.contains("el-submenu"))) {
        submenuDepth += 1;
      }
      cursor = cursor.parentElement;
    }
    if (submenuDepth > 0) return submenuDepth + 1;
    const nestedMenus = [];
    let node = el.parentElement;
    while (node && node !== document.body) {
      if (node.matches && node.matches("[role='menu'],.ant-menu,.el-menu,ul")) nestedMenus.push(node);
      node = node.parentElement;
    }
    return Math.max(1, nestedMenus.length);
  }

  function parentTextOf(el) {
    const li = el.closest("li");
    if (li) {
      const parentLi = li.parentElement ? li.parentElement.closest("li") : null;
      if (parentLi) {
        const title = parentLi.querySelector(".ant-menu-submenu-title,.el-submenu__title,[role='menuitem'],a,button");
        if (title) return textOf(title);
      }
    }
    const group = el.closest("[role='group'],.ant-menu-submenu,.el-submenu");
    if (group && group !== el) {
      const title = group.querySelector(".ant-menu-submenu-title,.el-submenu__title");
      if (title && title !== el) return textOf(title);
    }
    return null;
  }

  return elements.map((el, index) => {
    const rect = el.getBoundingClientRect();
    const text = textOf(el);
    const expanded = el.getAttribute("aria-expanded");
    return {
      elementRef: `M${String(index + 1).padStart(3, "0")}`,
      selector: cssPath(el),
      text,
      level: levelOf(el),
      parentText: parentTextOf(el),
      expanded: expanded === null ? null : expanded === "true",
      visible: rect.width > 0 && rect.height > 0,
      enabled: !el.disabled && el.getAttribute("aria-disabled") !== "true",
      area: areaOf(el),
      bbox: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
    };
  });
}"""
