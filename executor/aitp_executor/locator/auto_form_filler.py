from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


@dataclass
class AutoFormFillResult:
    filled: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[dict[str, Any]] = field(default_factory=list)
    defaults_used: dict[str, Any] = field(default_factory=dict)
    needs_clarification: list[str] = field(default_factory=list)


class AutoFormFiller:
    critical_labels = {"组织机构", "所属机构", "部门", "所属部门", "单位", "审批人", "审核人", "角色", "数据权限"}
    file_labels = {"附件", "文件", "上传"}

    def fill(self, page: Any, *, test_data: dict[str, Any] | None = None) -> AutoFormFillResult:
        test_data = test_data or {}
        result = AutoFormFillResult()
        labels = self._visible_labels(page)
        for label in labels:
            value = test_data.get(label)
            if value is None:
                value = self._default_value(label)
                if value is not None:
                    result.defaults_used[label] = value
            if value is None and self._is_critical(label):
                result.needs_clarification.append(label)
                continue
            if value is None:
                result.skipped.append({"label": label, "reason": "no_value"})
                continue
            if self._fill_by_label(page, label, str(value)):
                result.filled.append({"label": label, "value": value})
            else:
                result.skipped.append({"label": label, "reason": "control_not_found"})
        if result.needs_clarification:
            return result
        self._fill_unlabeled_required_inputs(page, result)
        return result

    def _visible_labels(self, page: Any) -> list[str]:
        labels = page.locator("label").all()
        names: list[str] = []
        for label in labels:
            try:
                text = " ".join(label.inner_text().split())
            except Exception:
                continue
            if text and text not in names:
                names.append(text)
        return names

    def _fill_by_label(self, page: Any, label: str, value: str) -> bool:
        try:
            locator = page.get_by_label(label, exact=True)
            if locator.count() == 1 and self._can_fill(locator):
                locator.fill(value)
                return True
        except Exception:
            pass
        try:
            locator = page.get_by_placeholder(label, exact=True)
            if locator.count() == 1 and self._can_fill(locator):
                locator.fill(value)
                return True
        except Exception:
            pass
        return False

    def _fill_unlabeled_required_inputs(self, page: Any, result: AutoFormFillResult) -> None:
        inputs = page.locator("input[required]:not([type=file]), textarea[required]").all()
        for index, locator in enumerate(inputs, start=1):
            try:
                if not self._can_fill(locator):
                    continue
                current = locator.input_value()
                if current:
                    continue
                value = f"AUTO_{self._timestamp()}"
                locator.fill(value)
                result.defaults_used[f"required_{index}"] = value
                result.filled.append({"label": f"required_{index}", "value": value})
            except Exception:
                continue

    def _can_fill(self, locator: Any) -> bool:
        try:
            return locator.is_visible() and locator.is_enabled() and not locator.get_attribute("readonly")
        except Exception:
            return False

    def _is_critical(self, label: str) -> bool:
        return any(keyword in label for keyword in self.critical_labels) or any(keyword in label for keyword in self.file_labels)

    def _default_value(self, label: str) -> str | None:
        timestamp = self._timestamp()
        if "用户名" in label:
            return f"test_ai_{timestamp}"
        if "姓名" in label:
            return f"测试用户{timestamp}"
        if "手机号" in label:
            return "13800000000"
        if "邮箱" in label:
            return f"test_{timestamp}@example.com"
        if "备注" in label:
            return "自动化测试"
        if "审批意见" in label:
            return "自动化测试审批通过"
        if "标题" in label:
            return f"自动化测试标题{timestamp}"
        if "编号" in label:
            return f"AUTO_{timestamp}"
        if "开始日期" in label or "申请日期" in label:
            return datetime.now().strftime("%Y-%m-%d")
        if "结束日期" in label or "计划完成时间" in label:
            return (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        return None

    def _timestamp(self) -> str:
        return datetime.now().strftime("%Y%m%d%H%M%S")
