import { useEffect, useState } from "react";
import { API_URL } from "./config";

export default function CloudBanner() {
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
        <strong>Demo Purposes:</strong> Running OpenAI instead of Llama on a local airgapped server.
      </span>
    </div>
  );
}
