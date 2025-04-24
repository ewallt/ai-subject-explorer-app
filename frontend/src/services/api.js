// MOCK API Service - Returns hardcoded data after a short delay

const MOCK_DELAY_MS = 500; // Simulate network latency (500ms)

/**
 * MOCK: Starts a new session.
 * @param {string} topic - The initial topic from the user.
 * @returns {Promise<object>} - Mock response data ({ session_id, menu_items }).
 * @throws {Error} - Can simulate errors by rejecting.
 */
export const startSession = (topic) => {
    console.log(`MOCK API: Starting session for topic "${topic}"`);
    return new Promise((resolve, reject) => {
        setTimeout(() => {
            // Simulate potential error during start (optional)
            // if (topic.toLowerCase() === 'error') {
            //   console.error("MOCK API: Simulating start error");
            //   reject(new Error("Mock API failed to start session!"));
            //   return;
            // }

            const mockResponse = {
                session_id: `mock-session-${Date.now()}`, // Generate a simple mock ID
                menu_items: [
                    `History of ${topic}`,
                    `Key Concepts in ${topic}`,
                    `Applications of ${topic}`,
                    `Future of ${topic}` // Example mock items
                ]
            };
            console.log("MOCK API: Returning mock session data", mockResponse);
            resolve(mockResponse);
        }, MOCK_DELAY_MS);
    });
};

/**
 * MOCK: Sends the user's menu selection.
 * @param {string} sessionId - The current session ID (can be checked in mock).
 * @param {string} selection - The menu item text selected by the user.
 * @returns {Promise<object>} - Mock response data ({ menu_items }).
 * @throws {Error} - Can simulate errors by rejecting.
 */
export const selectMenuItem = (sessionId, selection) => {
    console.log(`MOCK API: Processing selection "${selection}" for session "${sessionId}"`);
    return new Promise((resolve, reject) => {
        setTimeout(() => {
            // Optional: Simulate session not found if needed for testing UI
            // if (!sessionId || !sessionId.startsWith('mock-session-')) {
            //    console.error("MOCK API: Simulating session not found");
            //    const error = new Error("Session ID not found or invalid (mock)");
            //    reject(error);
            //    return;
            // }

            let mockSubmenu = [];
            // Simple logic based on selection text
            if (selection.toLowerCase().includes('history')) {
                mockSubmenu = [`Early History`, `Mid-20th Century`, `Recent Developments`];
            } else if (selection.toLowerCase().includes('concepts')) {
                mockSubmenu = [`Core Idea A`, `Core Idea B`, `Related Theories`];
            } else if (selection.toLowerCase().includes('applications')) {
                mockSubmenu = [`Practical Use Case 1`, `Industry Examples`, `Research Areas`];
            } else {
                // Default / fallback mock submenu
                mockSubmenu = [`Sub-item for ${selection} 1`, `Sub-item 2`, `Sub-item 3`];
            }

            const mockResponse = {
                menu_items: mockSubmenu
            };
            console.log("MOCK API: Returning mock submenu data", mockResponse);
            resolve(mockResponse);
        }, MOCK_DELAY_MS);
    });
};
