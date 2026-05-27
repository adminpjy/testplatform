import { ChevronDown, ChevronUp, Copy } from "lucide-react";
import { useState } from "react";

export function JsonCollapseBlock({
  title = "查看详情",
  value,
  defaultOpen = false
}: {
  title?: string;
  value: unknown;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2) ?? "";
  return (
    <div className="json-collapse">
      <div className="json-collapse__actions">
        <button className="ghost-button json-collapse__trigger" type="button" onClick={() => setOpen((current) => !current)}>
          {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          {open ? "收起详情" : title}
        </button>
        <button className="ghost-button" type="button" onClick={() => void navigator.clipboard?.writeText(text)}>
          <Copy size={14} />
          复制
        </button>
      </div>
      {open ? <pre className="metadata-block">{text}</pre> : null}
    </div>
  );
}
