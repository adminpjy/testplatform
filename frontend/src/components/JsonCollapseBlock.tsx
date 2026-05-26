import { ChevronDown, ChevronUp } from "lucide-react";
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
  return (
    <div className="json-collapse">
      <button className="ghost-button json-collapse__trigger" type="button" onClick={() => setOpen((current) => !current)}>
        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        {open ? "收起详情" : title}
      </button>
      {open ? <pre className="metadata-block">{JSON.stringify(value, null, 2)}</pre> : null}
    </div>
  );
}
