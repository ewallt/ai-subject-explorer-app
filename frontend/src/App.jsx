import React, { useState } from 'react';
// Import the API functions (which now use real fetch)
import { startSession, selectMenuItem } from './services/api.js';
// Import the UI components
import TopicInput from './components/TopicInput.jsx';
import MenuList from './components/MenuList.jsx';
// Import CSS
import './index.css';

// Get API Base URL (needs to be accessible in this scope)
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function App() {
  // State variables (remain the same)
  const [sessionId, setSessionId] = useState(null);
  const [menuItems, setMenuItems] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [currentTopic, setCurrentTopic] = useState('');
  const [history, setHistory] = useState([]);

  // --- API Call Handlers ---
  const handleTopicSubmit = async (topic) => {
    console.log("Submitting topic:", topic);

    // --- Wake-up Call (Added) ---
    // Send a simple GET request first to wake up the free tier service
    console.log("Sending wake-up GET request to backend...");
    try {
        // We use fetch but don't necessarily need to wait or check the result closely.
        // Added a short timeout to prevent waiting too long if backend is slow/down.
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 3000); // 3 second timeout for wake-up

        await fetch(`${API_BASE_URL}/`, { signal: controller.signal }); // Hit the root endpoint

        clearTimeout(timeoutId); // Clear timeout if fetch returns quickly
        console.log("Wake-up request attempt finished.");
    } catch (wakeError) {
        // Log the error but continue anyway - the main request might still work
        // This often happens if the fetch times out or fails while server wakes
        console.warn("Wake-up request failed or timed out (server might still be starting):", wakeError);
    }
    // --- End Wake-up Call ---

    // Now proceed with the actual session request
    setIsLoading(true);
    setError(null);
    setSessionId(null); // Reset session
    setMenuItems([]);
    setHistory([]);
    setCurrentTopic(topic);

    try {
      // Call the imported function (which uses real fetch)
      const data = await startSession(topic);
      setSessionId(data.session_id);
      setMenuItems(data.menu_items);
      setHistory([`Topic: ${topic}`]);
      console.log("Real session started:", data.session_id);
    } catch (err) {
       const errorMsg = err.message || 'Failed to start session.';
       setError(errorMsg);
       console.error("Error in handleTopicSubmit calling startSession:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleMenuSelection = async (selection) => {
    // (Logic remains the same - calls selectMenuItem from api.js)
    console.log("Selecting menu item:", selection);
    if (!sessionId) {
        setError("No active session.");
        console.error("handleMenuSelection called with no sessionId");
        return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const data = await selectMenuItem(sessionId, selection);
      setMenuItems(data.menu_items);
      setHistory(prev => [...prev, `Selected: ${selection}`]);
      console.log("Menu updated via API");
    } catch (err) {
      const errorMsg = err.message || 'Failed to process selection.';
      setError(errorMsg);
      console.error("Error in handleMenuSelection calling selectMenuItem:", err);
       if (err.message && (err.message.includes("Session ID not found") || err.message.includes("404"))) {
           handleReset();
           setError("Session expired or invalid. Please start again.");
       }
    } finally {
      setIsLoading(false);
    }
  };

  // --- Reset Function (remains the same) ---
  const handleReset = () => {
      console.log("Resetting session");
      setSessionId(null);
      setMenuItems([]);
      setCurrentTopic('');
      setHistory([]);
      setError(null);
      setIsLoading(false);
  }

  // --- Render Logic (Uses imported components) ---
  return (
    <div className="container mx-auto p-4 max-w-2xl font-sans">
      <header className="text-center mb-6 border-b pb-4">
        {/* You can test deployment here too: */}
        <h1 className="text-3xl font-bold text-blue-700">AI Subject Explorer (APP)</h1>
        {sessionId && (
             <button
                onClick={handleReset}
                className="mt-2 text-sm text-gray-500 hover:text-red-600 underline"
            >
                Start Over
            </button>
        )}
      </header>

      <main>
        {isLoading && <div className="text-center p-4 text-blue-500 font-semibold">Loading...</div>}
        {error && <div className="text-center p-3 mb-4 bg-red-100 text-red-700 rounded border border-red-300">Error: {error}</div>}

        {/* Use TopicInput component */}
        {!isLoading && !error && !sessionId && (
          <TopicInput onSubmit={handleTopicSubmit} />
        )}

        {/* Use MenuList component */}
        {!isLoading && !error && sessionId && menuItems.length > 0 && (
          <div className="mt-4">
            <div className='text-sm text-gray-600 mb-3 border-b pb-2'>
                Path: {history.join(' → ')}
            </div>
            <MenuList items={menuItems} onSelect={handleMenuSelection} />
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
