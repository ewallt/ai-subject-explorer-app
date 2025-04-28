// *** frontend/services/api.js ***
// Real API Service - Makes fetch calls to the backend

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

console.log(`API Base URL configured: ${API_BASE_URL}`);

// ---------------------------------------------------------------------------
//  startSession
// ---------------------------------------------------------------------------
export const startSession = async (topic) => {
  console.log(`API CALL: POST /sessions ("${topic}")`);
  try {
    const response = await fetch(`${API_BASE_URL}/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic }),
    });

    const data = await response.json();
    if (!response.ok) {
      const msg =
        data.error?.message || `HTTP error! Status: ${response.status}`;
      throw new Error(msg);
    }
    return data;
  } catch (err) {
    throw new Error(err.message || "Network error starting session.");
  }
};

// ---------------------------------------------------------------------------
//  selectMenuItem
// ---------------------------------------------------------------------------
export const selectMenuItem = async (sessionId, selection) => {
  console.log(`API CALL: POST /menus ("${selection}")`);
  try {
    const response = await fetch(`${API_BASE_URL}/menus`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, selection }),
    });

    const data = await response.json();
    if (!response.ok) {
      const msg =
        data.error?.message || `HTTP error! Status: ${response.status}`;
      throw new Error(msg);
    }
    return data;
  } catch (err) {
    throw new Error(err.message || "Network error selecting menu item.");
  }
};

// ---------------------------------------------------------------------------
//  goBack  (NEW implementation)
// ---------------------------------------------------------------------------
export const goBack = async (sessionId) => {
  console.log(`API CALL: POST /go_back (session "${sessionId}")`);
  try {
    const response = await fetch(`${API_BASE_URL}/go_back`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    });

    const data = await response.json();
    if (!response.ok) {
      const msg =
        data.error?.message || `HTTP error! Status: ${response.status}`;
      throw new Error(msg);
    }
    return data; // { type: "submenu", menu_items: [...] }
  } catch (err) {
    throw new Error(err.message || "Network error navigating back.");
  }
};

// *** End of api.js ***
