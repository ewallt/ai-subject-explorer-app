// *** frontend/src/services/api.js ***

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

console.log(`API Base URL: ${API_BASE_URL}`);

// ───────────────────────────────
//  startSession
// ───────────────────────────────
export const startSession = async (topic) => {
  const resp = await fetch(`${API_BASE_URL}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic }),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.error?.message || resp.statusText);
  return data;
};

// ───────────────────────────────
//  selectMenuItem
// ───────────────────────────────
export const selectMenuItem = async (sessionId, selection) => {
  const resp = await fetch(`${API_BASE_URL}/menus`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, selection }),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.error?.message || resp.statusText);
  return data;
};

// ───────────────────────────────
//  goBack
// ───────────────────────────────
export const goBack = async (sessionId) => {
  const resp = await fetch(`${API_BASE_URL}/go_back`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.error?.message || resp.statusText);
  return data;
};

// ───────────────────────────────
//  NEW: returnToMainMenu
// ───────────────────────────────
export const returnToMainMenu = async (sessionId) => {
  const resp = await fetch(`${API_BASE_URL}/main_menu`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.error?.message || resp.statusText);
  return data; // { type:"submenu", menu_items:[...] }
};

// *** End of api.js ***
