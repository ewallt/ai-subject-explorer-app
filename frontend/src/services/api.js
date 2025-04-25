// Real API Service - Makes fetch calls to the backend

// Get the backend URL from environment variables (set in Render)
// Fallback to localhost:8000 for potential local development later
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

console.log(`API Base URL configured: ${API_BASE_URL}`); // Log for debugging deployment

/**
 * Starts a new session by calling the backend API.
 * @param {string} topic - The initial topic from the user.
 * @returns {Promise<object>} - The response data ({ session_id, menu_items }).
 * @throws {Error} - Throws error on API failure.
 */
export const startSession = async (topic) => {
    console.log(`API CALL: POST /sessions with topic "${topic}" to ${API_BASE_URL}`);
    try {
        const response = await fetch(`${API_BASE_URL}/sessions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ topic }),
        });

        const responseData = await response.json(); // Always try to parse JSON

        if (!response.ok) {
            // Use error message from backend if available, otherwise use HTTP status
            const errorMessage = responseData.error?.message || `HTTP error! Status: ${response.status}`;
            console.error("API Error Response:", responseData);
            throw new Error(errorMessage);
        }

        console.log("API Success Response (/sessions):", responseData);
        return responseData; // { session_id, menu_items }

    } catch (error) {
        console.error("Network or parsing error starting session:", error);
        // Re-throw the error so the component can catch it
        // Provide a default message if the caught error has none
        throw new Error(error.message || "Network error or invalid response from server.");
    }
};

/**
 * Sends the user's menu selection to the backend API.
 * @param {string} sessionId - The current session ID.
 * @param {string} selection - The menu item text selected by the user.
 * @returns {Promise<object>} - The response data ({ menu_items }).
 * @throws {Error} - Throws error on API failure.
 */
export const selectMenuItem = async (sessionId, selection) => {
    console.log(`API CALL: POST /menus with session "${sessionId}" and selection "${selection}" to ${API_BASE_URL}`);
    try {
        const response = await fetch(`${API_BASE_URL}/menus`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ session_id: sessionId, selection }),
        });

        const responseData = await response.json(); // Always try to parse JSON

        if (!response.ok) {
            const errorMessage = responseData.error?.message || `HTTP error! Status: ${response.status}`;
            console.error("API Error Response:", responseData);
             // Specific handling for session not found might be useful
             if (response.status === 404) {
                 console.warn("Session potentially expired or invalid.");
                 // Throw a specific error or let generic one handle? For now, generic.
             }
            throw new Error(errorMessage);
        }

        console.log("API Success Response (/menus):", responseData);
        return responseData; // { menu_items }

    } catch (error) {
        console.error("Network or parsing error selecting menu item:", error);
        throw new Error(error.message || "Network error or invalid response from server.");
    }
};

/**
 * Sends a request to the backend to navigate back one level in the session.
 * @param {string} sessionId - The current session ID.
 * @returns {Promise<object>} - The promise resolving to the API response (should contain previous menu).
 */
export const goBack = async (sessionId) => {
  console.log(`API CALL: POST /menus (Go Back) for session "${sessionId}"`);
  const response = await fetch(`${API_BASE_URL}/menus`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    // Send the special "__BACK__" marker as the selection
    body: JSON.stringify({ session_id: sessionId, selection: "__BACK__" }),
  });

  if (!response.ok) {
    // Attempt to read error details from response body
    let errorData;
    try {
      errorData = await response.json();
    } catch (e) {
      // If response body is not JSON or empty
      errorData = { message: `HTTP error! Status: ${response.status}` };
    }
    console.error("API Error Response (goBack):", errorData);
    // Throw an error with message from backend if available, otherwise status text
    throw new Error(errorData?.detail?.error?.message || errorData?.message || response.statusText);
  }

  const data = await response.json();
  console.log("API Success Response (goBack):", data);
  return data; // Should return { type: "submenu", menu_items: [...] }
};
