// Nexus Hestia — API config
// Vite replaces import.meta.env.VITE_* at build time.
// Set VITE_API_URL in Vercel environment variables to your Railway URL.
// Locally it falls back to localhost:5000.

export const API_URL =
  import.meta.env.VITE_API_URL?.replace(/\/$/, "") || "http://localhost:5000";
