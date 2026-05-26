import { X } from "lucide-react";

export function ScreenshotPreviewModal({
  src,
  title,
  onClose
}: {
  src: string | null;
  title?: string;
  onClose: () => void;
}) {
  if (!src) return null;
  return (
    <div className="screenshot-modal" role="dialog" aria-modal="true">
      <div className="screenshot-modal__header">
        <strong>{title || "截图预览"}</strong>
        <button className="icon-button" type="button" onClick={onClose} title="关闭">
          <X size={18} />
        </button>
      </div>
      <div className="screenshot-modal__body" onClick={onClose}>
        <img src={src} alt={title || "截图预览"} onClick={(event) => event.stopPropagation()} />
      </div>
    </div>
  );
}
