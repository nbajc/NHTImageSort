// CloudBanner.jsx
// Shows a small banner when running in cloud mode (USE_CLOUD=true on Railway).
// Turns your on-premise pitch into a feature, not a disclaimer.

import { useEffect, useState } from "react";
import { API_URL } from "./config";

export default function CloudBanner() {
  const [info, setInfo] = useState(null);

  useEffect(() => {
    fetch(`${API_URL}/api/info`)
      .then((r) => r.json())
      .then(setInfo)
      .catch(() => {});
  }, []);

  if (!info || !info.cloud_mode) return null;

  return (
    <div
      style={{
        background: "rgba(255, 107, 0, 0.08)",
        border: "1px solid rgba(255, 107, 0, 0.25)",
        borderRadius: "4px",
        padding: "6px 14px",
        fontSize: "11px",
        color: "#FF6B00",
        letterSpacing: "0.04em",
        display: "flex",
        alignItems: "center",
        gap: "8px",
        marginBottom: "12px",
      }}
    >
      <span style={{ opacity: 0.7 }}>⬡</span>
      <span>
        <strong>Cloud demo</strong> — AI powered by OpenAI GPT-4o-mini.
        Client deployments run <strong>100% on-premise</strong> with Ollama — your data never leaves the network.
      </span>
    </div>
  );
}
