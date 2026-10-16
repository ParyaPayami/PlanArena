import { useEffect, useState } from "react";
import { useStore } from "../store";

export default function Toast() {
  const toast = useStore((s) => s.toast);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (!toast) return;
    setVisible(true);
    const t = window.setTimeout(() => setVisible(false), 2600);
    return () => window.clearTimeout(t);
  }, [toast?.id]);
  if (!toast || !visible) return null;
  return <div className={`toast ${toast.tone}`}>{toast.text}</div>;
}
