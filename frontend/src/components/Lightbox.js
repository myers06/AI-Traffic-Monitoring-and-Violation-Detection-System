import { useEffect } from "react";

export default function Lightbox({ src, onClose }) {
  useEffect(() => {
    if (!src) return;
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [src, onClose]);

  if (!src) return null;
  return (
    <div className="lightbox" onClick={onClose}>
      <img src={src} alt="Evidence enlarged" />
    </div>
  );
}