from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PageObservation:
    url: str
    title: str
    visible_text: str
    elements: list[dict[str, Any]]
    menus: list[dict[str, Any]]
    visibleTexts: list[str] = field(default_factory=list)
    pageType: str = "unknown"
    buttons: list[dict[str, Any]] = field(default_factory=list)
    links: list[dict[str, Any]] = field(default_factory=list)
    inputs: list[dict[str, Any]] = field(default_factory=list)
    textareas: list[dict[str, Any]] = field(default_factory=list)
    selects: list[dict[str, Any]] = field(default_factory=list)
    comboboxes: list[dict[str, Any]] = field(default_factory=list)
    radios: list[dict[str, Any]] = field(default_factory=list)
    checkboxes: list[dict[str, Any]] = field(default_factory=list)
    datePickers: list[dict[str, Any]] = field(default_factory=list)
    treeSelectors: list[dict[str, Any]] = field(default_factory=list)
    orgSelectors: list[dict[str, Any]] = field(default_factory=list)
    personSelectors: list[dict[str, Any]] = field(default_factory=list)
    fileUploads: list[dict[str, Any]] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    dialogs: list[dict[str, Any]] = field(default_factory=list)
    drawers: list[dict[str, Any]] = field(default_factory=list)
    tabs: list[dict[str, Any]] = field(default_factory=list)
    breadcrumbs: list[dict[str, Any]] = field(default_factory=list)
    toasts: list[dict[str, Any]] = field(default_factory=list)
    loadingIndicators: list[dict[str, Any]] = field(default_factory=list)
    iframes: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class PageObserver:
    def observe(self, page: Any) -> PageObservation:
        data = self._observe_scope(page, frame_prefix="")
        frame_observations = self._observe_frames(page)
        for frame_data in frame_observations:
            _merge_observation_data(data, frame_data)

        visible_text = "\n".join(data.get("visibleTexts") or [])[:8000]
        elements = _aggregate_elements(data)
        return PageObservation(
            url=data.get("url") or page.url,
            title=data.get("title") or "",
            visible_text=visible_text,
            elements=elements,
            menus=data.get("menus") or [],
            visibleTexts=(data.get("visibleTexts") or [])[:300],
            pageType=data.get("pageType") or "unknown",
            buttons=data.get("buttons") or [],
            links=data.get("links") or [],
            inputs=data.get("inputs") or [],
            textareas=data.get("textareas") or [],
            selects=data.get("selects") or [],
            comboboxes=data.get("comboboxes") or [],
            radios=data.get("radios") or [],
            checkboxes=data.get("checkboxes") or [],
            datePickers=data.get("datePickers") or [],
            treeSelectors=data.get("treeSelectors") or [],
            orgSelectors=data.get("orgSelectors") or [],
            personSelectors=data.get("personSelectors") or [],
            fileUploads=data.get("fileUploads") or [],
            tables=data.get("tables") or [],
            dialogs=data.get("dialogs") or [],
            drawers=data.get("drawers") or [],
            tabs=data.get("tabs") or [],
            breadcrumbs=data.get("breadcrumbs") or [],
            toasts=data.get("toasts") or [],
            loadingIndicators=data.get("loadingIndicators") or [],
            iframes=data.get("iframes") or [],
        )

    def _observe_scope(self, scope: Any, *, frame_prefix: str) -> dict[str, Any]:
        try:
            return scope.evaluate(_PAGE_OBSERVER_SCRIPT, {"framePrefix": frame_prefix})
        except Exception:
            return _empty_data()

    def _observe_frames(self, page: Any) -> list[dict[str, Any]]:
        observations: list[dict[str, Any]] = []
        for frame_index, frame in enumerate(page.frames):
            if frame == page.main_frame:
                continue
            frame_ref = f"F{frame_index}"
            try:
                frame_data = self._observe_scope(frame, frame_prefix=f"{frame_ref}-")
                frame_data["iframes"] = [
                    {
                        "frameIndex": frame_index,
                        "src": frame.url,
                        "title": frame.name,
                        "visible": True,
                        "accessible": True,
                    }
                ]
            except Exception:
                frame_data = {
                    **_empty_data(),
                    "iframes": [
                        {
                            "frameIndex": frame_index,
                            "src": getattr(frame, "url", ""),
                            "title": getattr(frame, "name", ""),
                            "visible": None,
                            "accessible": False,
                        }
                    ],
                }
            observations.append(frame_data)
        return observations


def _aggregate_elements(data: dict[str, Any]) -> list[dict[str, Any]]:
    groups = [
        "buttons",
        "links",
        "inputs",
        "textareas",
        "selects",
        "comboboxes",
        "radios",
        "checkboxes",
        "datePickers",
        "treeSelectors",
        "orgSelectors",
        "personSelectors",
        "fileUploads",
        "tabs",
    ]
    elements: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group in groups:
        for item in data.get(group) or []:
            selector = str(item.get("selector") or item.get("elementRef") or "")
            if selector and selector in seen:
                continue
            seen.add(selector)
            elements.append(_as_legacy_element(item, group))
    return elements


def _as_legacy_element(item: dict[str, Any], group: str) -> dict[str, Any]:
    role = item.get("role") or _role_from_group(group)
    return {
        **item,
        "tag": item.get("tag") or item.get("controlType") or group,
        "role": role,
        "text": item.get("text") or item.get("label") or item.get("title") or "",
        "label": item.get("label") or "",
        "ariaLabel": item.get("ariaLabel") or "",
        "placeholder": item.get("placeholder") or "",
        "id": item.get("id") or "",
        "name": item.get("name") or "",
        "type": item.get("type") or item.get("controlType") or "",
        "href": item.get("href") or "",
        "rect": item.get("bbox") or item.get("rect") or {},
    }


def _role_from_group(group: str) -> str:
    return {
        "buttons": "button",
        "links": "link",
        "inputs": "textbox",
        "textareas": "textbox",
        "selects": "combobox",
        "comboboxes": "combobox",
        "radios": "radio",
        "checkboxes": "checkbox",
        "tabs": "tab",
    }.get(group, "")


def _merge_observation_data(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, list):
            target.setdefault(key, []).extend(value)


def _empty_data() -> dict[str, Any]:
    return {
        "url": "",
        "title": "",
        "visibleTexts": [],
        "pageType": "unknown",
        "menus": [],
        "buttons": [],
        "links": [],
        "inputs": [],
        "textareas": [],
        "selects": [],
        "comboboxes": [],
        "radios": [],
        "checkboxes": [],
        "datePickers": [],
        "treeSelectors": [],
        "orgSelectors": [],
        "personSelectors": [],
        "fileUploads": [],
        "tables": [],
        "dialogs": [],
        "drawers": [],
        "tabs": [],
        "breadcrumbs": [],
        "toasts": [],
        "loadingIndicators": [],
        "iframes": [],
    }


_PAGE_OBSERVER_SCRIPT = r"""(args) => {
  const framePrefix = (args && args.framePrefix) || "";

  function cssPath(el) {
    if (!el || !el.tagName) return "";
    if (el.id) return "#" + CSS.escape(el.id);
    const parts = [];
    let node = el;
    while (node && node.nodeType === Node.ELEMENT_NODE && node !== document.body) {
      let part = node.tagName.toLowerCase();
      const parent = node.parentElement;
      if (parent) {
        const siblings = Array.from(parent.children).filter((item) => item.tagName === node.tagName);
        if (siblings.length > 1) part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
      }
      parts.unshift(part);
      node = parent;
    }
    return parts.join(" > ");
  }

  function textOf(el) {
    return normalize(el.innerText || el.textContent || el.getAttribute("aria-label") || el.getAttribute("title") || el.getAttribute("placeholder") || el.value || "");
  }

  function normalize(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function visible(el) {
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
  }

  function bbox(el) {
    const rect = el.getBoundingClientRect();
    return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
  }

  function enabled(el) {
    return !el.disabled && el.getAttribute("aria-disabled") !== "true";
  }

  function labelFor(el) {
    if (el.labels && el.labels.length) {
      return Array.from(el.labels).map((label) => textOf(label)).filter(Boolean).join(" ");
    }
    if (el.id) {
      const label = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (label) return textOf(label);
    }
    const wrapper = el.closest("label");
    if (wrapper) return textOf(wrapper);
    const formItem = el.closest(".ant-form-item,.el-form-item,.form-item,.form-group,[class*='formItem'],[class*='form-item']");
    if (formItem) {
      const label = formItem.querySelector("label,.ant-form-item-label,.el-form-item__label,.form-label,[class*='label']");
      if (label) return textOf(label);
    }
    return "";
  }

  function formTitle(el) {
    const form = el.closest("form,.ant-form,.el-form,[role='form'],.ant-modal,.el-dialog,.ant-drawer,.el-drawer");
    if (!form) return "";
    const title = form.querySelector("h1,h2,h3,.ant-modal-title,.el-dialog__title,.ant-drawer-title,.form-title,.section-title");
    return title ? textOf(title) : "";
  }

  function sectionTitle(el) {
    const section = el.closest("section,.ant-card,.el-card,.panel,.fieldset,.form-section");
    if (!section) return "";
    const title = section.querySelector("h1,h2,h3,h4,.ant-card-head-title,.el-card__header,.section-title,.panel-title,legend");
    return title ? textOf(title) : "";
  }

  function nearbyText(el) {
    const container = el.closest(".ant-form-item,.el-form-item,.form-item,.form-group,td,li,div") || el.parentElement;
    if (!container) return [];
    const texts = [];
    for (const item of Array.from(container.querySelectorAll("label,span,div,p,b,strong")).slice(0, 12)) {
      const value = textOf(item);
      if (value && value.length <= 80 && !texts.includes(value)) texts.push(value);
    }
    return texts.slice(0, 8);
  }

  function validationErrors(el) {
    const container = el.closest(".ant-form-item,.el-form-item,.form-item,.form-group,td,div") || el.parentElement;
    if (!container) return [];
    const errors = [];
    const selectors = ".ant-form-item-explain-error,.el-form-item__error,.invalid-feedback,.error,.help-block,[class*='error']";
    for (const item of Array.from(container.querySelectorAll(selectors)).slice(0, 6)) {
      const value = textOf(item);
      if (value && !errors.includes(value)) errors.push(value);
    }
    return errors;
  }

  function requiredOf(el) {
    if (el.required || el.getAttribute("aria-required") === "true") return true;
    const container = el.closest(".ant-form-item,.el-form-item,.form-item,.form-group,label");
    return !!(container && /[*]|必填|不能为空/.test(textOf(container)));
  }

  function readonlyOf(el) {
    return !!(el.readOnly || el.getAttribute("readonly") !== null || el.getAttribute("aria-readonly") === "true");
  }

  function locatorCandidates(el) {
    const candidates = [];
    if (el.id) candidates.push({ strategy: "css", value: "#" + CSS.escape(el.id) });
    const aria = el.getAttribute("aria-label");
    if (aria) candidates.push({ strategy: "aria-label", value: aria });
    const label = labelFor(el);
    if (label) candidates.push({ strategy: "label", value: label });
    const placeholder = el.getAttribute("placeholder");
    if (placeholder) candidates.push({ strategy: "placeholder", value: placeholder });
    const title = el.getAttribute("title");
    if (title) candidates.push({ strategy: "title", value: title });
    candidates.push({ strategy: "cssPath", value: cssPath(el) });
    return candidates;
  }

  function controlBase(el, ref, controlType) {
    return {
      elementRef: `${framePrefix}${ref}`,
      selector: cssPath(el),
      tag: el.tagName.toLowerCase(),
      role: el.getAttribute("role") || implicitRole(el),
      controlType,
      text: textOf(el),
      label: labelFor(el),
      placeholder: el.getAttribute("placeholder") || "",
      ariaLabel: el.getAttribute("aria-label") || "",
      title: el.getAttribute("title") || "",
      id: el.id || "",
      name: el.getAttribute("name") || "",
      type: el.getAttribute("type") || "",
      nearbyText: nearbyText(el),
      formTitle: formTitle(el),
      sectionTitle: sectionTitle(el),
      required: requiredOf(el),
      readonly: readonlyOf(el),
      visible: visible(el),
      enabled: enabled(el),
      bbox: bbox(el),
      validationErrors: validationErrors(el),
      locatorCandidates: locatorCandidates(el)
    };
  }

  function implicitRole(el) {
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute("type") || "text").toLowerCase();
    if (tag === "button" || type === "button" || type === "submit") return "button";
    if (tag === "a") return "link";
    if (tag === "select") return "combobox";
    if (tag === "textarea") return "textbox";
    if (type === "checkbox") return "checkbox";
    if (type === "radio") return "radio";
    if (tag === "input") return "textbox";
    return "";
  }

  function isDateControl(el) {
    const type = (el.getAttribute("type") || "").toLowerCase();
    const text = [labelFor(el), el.getAttribute("placeholder"), el.getAttribute("aria-label"), el.className, el.id, el.name].join(" ");
    return ["date", "datetime-local", "month", "time"].includes(type) || /日期|时间|开始|结束|有效期|date|time|picker/i.test(text);
  }

  function isDropdown(el) {
    const role = el.getAttribute("role");
    const cls = String(el.className || "");
    return role === "combobox" || /select|dropdown|picker/.test(cls);
  }

  function isTreeSelector(el) {
    const text = [labelFor(el), textOf(el), el.className, el.getAttribute("aria-label")].join(" ");
    return /tree|树|分类|区域|设备|字典/.test(text);
  }

  function isOrgSelector(el) {
    const text = [labelFor(el), textOf(el), el.getAttribute("placeholder"), el.getAttribute("aria-label")].join(" ");
    return /组织|机构|部门|单位/.test(text);
  }

  function isPersonSelector(el) {
    const text = [labelFor(el), textOf(el), el.getAttribute("placeholder"), el.getAttribute("aria-label")].join(" ");
    return /人员|负责人|经办人|审批人|申请人|处理人|用户/.test(text);
  }

  function buttonLike(el, ref) {
    return {
      elementRef: `${framePrefix}${ref}`,
      selector: cssPath(el),
      tag: el.tagName.toLowerCase(),
      role: el.getAttribute("role") || implicitRole(el),
      text: textOf(el),
      label: labelFor(el),
      ariaLabel: el.getAttribute("aria-label") || "",
      title: el.getAttribute("title") || "",
      id: el.id || "",
      name: el.getAttribute("name") || "",
      type: el.getAttribute("type") || "",
      visible: visible(el),
      enabled: enabled(el),
      bbox: bbox(el),
      locatorCandidates: locatorCandidates(el)
    };
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
    let depth = 0;
    let cursor = el.parentElement;
    while (cursor && cursor !== document.body) {
      if (cursor.matches && cursor.matches("[role='menu'],.ant-menu,.el-menu,ul,.tree,.ant-tree,.el-tree")) depth += 1;
      cursor = cursor.parentElement;
    }
    return Math.max(1, depth);
  }

  function parentTextOf(el) {
    const li = el.closest("li");
    if (li && li.parentElement) {
      const parentLi = li.parentElement.closest("li");
      if (parentLi) {
        const title = parentLi.querySelector(".ant-menu-submenu-title,.el-submenu__title,[role='menuitem'],a,button");
        if (title) return textOf(title);
      }
    }
    const group = el.closest("[role='group'],.ant-menu-submenu,.el-submenu,.tree-node");
    if (group && group !== el) {
      const title = group.querySelector(".ant-menu-submenu-title,.el-submenu__title,[role='treeitem']");
      if (title && title !== el) return textOf(title);
    }
    return null;
  }

  function menuItem(el, index) {
    const expanded = el.getAttribute("aria-expanded");
    return {
      elementRef: `${framePrefix}M${String(index + 1).padStart(3, "0")}`,
      selector: cssPath(el),
      text: textOf(el),
      level: levelOf(el),
      parentText: parentTextOf(el),
      expanded: expanded === null ? null : expanded === "true",
      visible: visible(el),
      enabled: enabled(el),
      area: areaOf(el),
      bbox: bbox(el)
    };
  }

  function tableOf(el, index) {
    const headers = Array.from(el.querySelectorAll("th,[role='columnheader'],.ant-table-thead cell,.el-table__header th"))
      .map(textOf).filter(Boolean);
    const rowElements = Array.from(el.querySelectorAll("tbody tr,.ant-table-tbody tr,.el-table__row,.vxe-body--row,[role='row']")).slice(0, 50);
    const rows = rowElements.map((row, rowIndex) => {
      const text = textOf(row);
      const cells = Array.from(row.querySelectorAll("td,[role='gridcell'],.cell,.vxe-cell")).map(textOf).filter(Boolean);
      const actions = Array.from(row.querySelectorAll("button,[role='button'],.ant-btn,.el-button")).map((item) => buttonLike(item, `T${index + 1}A${rowIndex + 1}`)).filter((item) => item.visible && item.text);
      const links = Array.from(row.querySelectorAll("a[href],a,[role='link']")).map((item) => buttonLike(item, `T${index + 1}L${rowIndex + 1}`)).filter((item) => item.visible && item.text);
      let rowType = "data_row";
      if (/暂无数据|无数据|没有数据|No Data/i.test(text)) rowType = "empty_row";
      else if (/合计|总计|小计/.test(text)) rowType = "summary_row";
      else if (/skeleton|loading|加载中|placeholder/i.test(row.className + " " + text)) rowType = "placeholder_row";
      else if (/分页|上一页|下一页|共\s*\d+/.test(text)) rowType = "pagination_row";
      return { rowIndex: rowIndex + 1, rowType, cells, actions, links };
    });
    const root = el.closest(".ant-table-wrapper,.el-table,.vxe-table,.table-wrapper") || el.parentElement || el;
    const paginationEl = root.querySelector(".ant-pagination,.el-pagination,.pagination,[class*='pagination']");
    const emptyState = rows.some((row) => row.rowType === "empty_row") || !!root.querySelector(".ant-empty,.el-empty,.empty,.no-data");
    return {
      elementRef: `${framePrefix}T${String(index + 1).padStart(3, "0")}`,
      selector: cssPath(el),
      headers,
      rows,
      pagination: paginationEl ? { text: textOf(paginationEl), visible: visible(paginationEl), bbox: bbox(paginationEl) } : {},
      emptyState,
      visible: visible(el),
      bbox: bbox(el)
    };
  }

  function dialogType(el) {
    const text = textOf(el);
    if (/审批|审核|通过|驳回/.test(text)) return "approval";
    if (/选择|查询/.test(text) && el.querySelector("table,[role='grid'],.ant-table,.el-table")) return "selector";
    if (/详情|明细|基本信息/.test(text)) return "detail";
    if (/错误|失败|异常/.test(text)) return "error";
    if (/确定|确认|是否/.test(text)) return "confirm";
    if (el.querySelector("input,textarea,select,[role='combobox']")) return "form";
    return "info";
  }

  function dialogOf(el, index) {
    const title = el.querySelector(".ant-modal-title,.el-dialog__title,.ant-drawer-title,h1,h2,h3,.title");
    const texts = Array.from(el.querySelectorAll("p,span,div,label")).map(textOf).filter((item) => item && item.length <= 160).slice(0, 40);
    const buttons = Array.from(el.querySelectorAll("button,[role='button'],.ant-btn,.el-button")).map((item, buttonIndex) => buttonLike(item, `D${index + 1}B${buttonIndex + 1}`)).filter((item) => item.visible && item.text);
    return {
      elementRef: `${framePrefix}D${String(index + 1).padStart(3, "0")}`,
      selector: cssPath(el),
      dialogType: dialogType(el),
      title: title ? textOf(title) : "",
      texts,
      buttons,
      blocking: !!document.querySelector(".ant-modal-mask,.el-overlay,.modal-backdrop,.overlay,.mask,[aria-modal='true']"),
      visible: visible(el),
      bbox: bbox(el)
    };
  }

  const result = {
    url: location.href,
    title: document.title || "",
    visibleTexts: [],
    pageType: "unknown",
    menus: [],
    buttons: [],
    links: [],
    inputs: [],
    textareas: [],
    selects: [],
    comboboxes: [],
    radios: [],
    checkboxes: [],
    datePickers: [],
    treeSelectors: [],
    orgSelectors: [],
    personSelectors: [],
    fileUploads: [],
    tables: [],
    dialogs: [],
    drawers: [],
    tabs: [],
    breadcrumbs: [],
    toasts: [],
    loadingIndicators: [],
    iframes: []
  };

  const bodyText = normalize(document.body ? document.body.innerText : "");
  result.visibleTexts = bodyText.split(/\n+/).map(normalize).filter(Boolean).slice(0, 300);

  const controls = Array.from(document.querySelectorAll("input,textarea,select,[role='combobox'],.ant-select,.el-select,.ant-picker,.el-date-editor,.ant-tree-select,.el-tree-select,.upload,.ant-upload,.el-upload"));
  controls.forEach((el, index) => {
    if (!visible(el)) return;
    const inputType = (el.getAttribute("type") || "").toLowerCase();
    let type = "input";
    if (el.tagName.toLowerCase() === "textarea") type = "textarea";
    else if (el.tagName.toLowerCase() === "select") type = "dropdown";
    else if (inputType === "radio") type = "radio";
    else if (inputType === "checkbox") type = "checkbox";
    else if (el.getAttribute("role") === "combobox" || isDropdown(el)) type = "dropdown";
    if (isDateControl(el)) type = /range|起止|开始|结束/.test([labelFor(el), el.getAttribute("placeholder"), el.className].join(" ")) ? "date_range" : "date_picker";
    if (isTreeSelector(el)) type = "tree_selector";
    if (isOrgSelector(el)) type = "org_selector";
    if (isPersonSelector(el)) type = "person_selector";
    if (inputType === "file" || /upload|上传|附件/i.test([labelFor(el), textOf(el), el.className].join(" "))) type = "file_upload";
    const item = controlBase(el, `F${String(index + 1).padStart(3, "0")}`, type);
    if (type === "textarea") result.textareas.push(item);
    else if (type === "dropdown") result.comboboxes.push(item);
    else if (type === "date_picker" || type === "date_range") result.datePickers.push(item);
    else if (type === "tree_selector") result.treeSelectors.push(item);
    else if (type === "org_selector") result.orgSelectors.push(item);
    else if (type === "person_selector") result.personSelectors.push(item);
    else if (type === "file_upload") result.fileUploads.push(item);
    else if (type === "radio") result.radios.push(item);
    else if (type === "checkbox") result.checkboxes.push(item);
    else result.inputs.push(item);
    if (el.tagName.toLowerCase() === "select") result.selects.push(item);
  });

  Array.from(document.querySelectorAll("button,[role='button'],input[type='button'],input[type='submit'],.ant-btn,.el-button")).forEach((el, index) => {
    const item = buttonLike(el, `B${String(index + 1).padStart(3, "0")}`);
    if (item.visible) result.buttons.push(item);
  });
  Array.from(document.querySelectorAll("a[href],a,[role='link']")).forEach((el, index) => {
    const item = { ...buttonLike(el, `L${String(index + 1).padStart(3, "0")}`), href: el.getAttribute("href") || "" };
    if (item.visible) result.links.push(item);
  });

  const menuSelector = "[role='menuitem'],[role='tab'],[role='treeitem'],nav a,nav button,aside a,aside button,.menu a,.menu button,.sidebar a,.sidebar button,.ant-menu-item,.ant-menu-submenu-title,.el-menu-item,.el-submenu__title,.tabs [role='tab'],.breadcrumb a,.ant-breadcrumb a,.el-breadcrumb a,.card,.shortcut,.quick-entry";
  Array.from(document.querySelectorAll(menuSelector)).forEach((el, index) => {
    const item = menuItem(el, index);
    if (item.visible && item.text) result.menus.push(item);
  });

  Array.from(document.querySelectorAll("[role='tab'],.ant-tabs-tab,.el-tabs__item")).forEach((el, index) => {
    const item = menuItem(el, index);
    if (item.visible && item.text) result.tabs.push(item);
  });
  Array.from(document.querySelectorAll(".ant-breadcrumb,.el-breadcrumb,.breadcrumb,[aria-label*='breadcrumb' i]")).forEach((el, index) => {
    if (visible(el)) result.breadcrumbs.push({ elementRef: `${framePrefix}BC${String(index + 1).padStart(3, "0")}`, selector: cssPath(el), text: textOf(el), visible: true, bbox: bbox(el) });
  });

  const tableSelector = "table,[role='grid'],.ant-table,.el-table,.vxe-table,.data-grid,.grid-table,[class*='table']";
  Array.from(document.querySelectorAll(tableSelector)).forEach((el, index) => {
    const item = tableOf(el, index);
    if (item.visible) result.tables.push(item);
  });

  const dialogSelector = "[role='dialog'],[aria-modal='true'],.ant-modal,.el-dialog,.modal,.message-box,.el-message-box,.popover,.ant-popover";
  Array.from(document.querySelectorAll(dialogSelector)).forEach((el, index) => {
    const item = dialogOf(el, index);
    if (item.visible) result.dialogs.push(item);
  });
  Array.from(document.querySelectorAll(".ant-drawer,.el-drawer,.drawer")).forEach((el, index) => {
    const item = dialogOf(el, index);
    if (item.visible) result.drawers.push({ ...item, elementRef: `${framePrefix}DR${String(index + 1).padStart(3, "0")}` });
  });
  Array.from(document.querySelectorAll(".ant-message,.el-message,.toast,.notification,.ant-notification,.el-notification")).forEach((el, index) => {
    if (visible(el)) result.toasts.push({ elementRef: `${framePrefix}TO${String(index + 1).padStart(3, "0")}`, selector: cssPath(el), text: textOf(el), visible: true, bbox: bbox(el) });
  });
  Array.from(document.querySelectorAll(".ant-spin,.el-loading-mask,.loading,.spinner,.skeleton,.ant-skeleton,[aria-busy='true']")).forEach((el, index) => {
    if (visible(el)) result.loadingIndicators.push({ elementRef: `${framePrefix}LD${String(index + 1).padStart(3, "0")}`, selector: cssPath(el), text: textOf(el), visible: true, bbox: bbox(el) });
  });
  Array.from(document.querySelectorAll("iframe,frame")).forEach((el, index) => {
    result.iframes.push({ frameIndex: index + 1, src: el.getAttribute("src") || "", title: el.getAttribute("title") || el.getAttribute("name") || "", visible: visible(el), accessible: null, bbox: bbox(el) });
  });

  if (result.dialogs.length) result.pageType = "dialog_overlay";
  else if (result.tables.length && (result.inputs.length || result.comboboxes.length || result.datePickers.length)) result.pageType = "list_query";
  else if (result.tables.length) result.pageType = "list";
  else if (result.inputs.length || result.textareas.length || result.comboboxes.length) result.pageType = "form";
  else if (result.menus.length) result.pageType = "portal";
  return result;
}"""
