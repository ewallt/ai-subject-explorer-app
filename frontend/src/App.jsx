import React, { useState, useEffect } from 'react';
// Import the API functions (add goBack)
import { startSession, selectMenuItem, goBack } from './services/api.js';
// Import the UI components
import TopicInput from './components/TopicInput.jsx';
import MenuList from './components/MenuList.jsx';
// Import a Markdown renderer (optional)
// import ReactMarkdown from 'react-markdown'; // Uncomment if installed

// Import CSS
import './index.css';

// Get API Base URL
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function App() {
  // State variables (no changes)
  const [sessionId, setSessionId] = useState(null);
  const [menuItems, setMenuItems] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [currentTopic, setCurrentTopic] = useState('');
  const [history, setHistory] = useState([]);
  const [currentContent, setCurrentContent] = useState(null);

  // --- API Call Handlers ---
  const handleTopicSubmit = async (topic) => {
    console.log("Submitting topic:", topic);
    // Wake-up call (no changes)
    console.log("Sending wake-up GET request to backend...");
    try {
      await fetch(`${API_BASE_URL}/`); // Simple GET to root
    } catch (wakeError) {
      console.warn("Wake-up request failed (backend might be starting):", wakeError);
      // Don't block the user for this, proceed with the session start
    }
    console.log("Wake-up request attempt finished.");

    // Reset state (no changes)
    setIsLoading(true);
    setError(null);
    setSessionId(null);
    setMenuItems([]);
    setHistory([]);
    setCurrentTopic(topic);
    setCurrentContent(null);

    try {
      // Start session (no changes)
      const data = await startSession(topic);
      setSessionId(data.session_id);
      setMenuItems(data.menu_items);
      setHistory([`Topic: ${topic}`]);
      console.log("Real session started:", data.session_id);
    } catch (err) {
       const errorMsg = err.message || 'Failed to start session.';
       setError(errorMsg);
       console.error("Error in handleTopicSubmit calling startSession API:", err);
    }
    finally { setIsLoading(false); }
  };

  const handleMenuSelection = async (selection) => {
    console.log("Selecting menu item:", selection);
    if (!sessionId) {
        setError("Session ID is missing. Please start over.");
        console.error("handleMenuSelection called without sessionId");
        return;
    }
    setIsLoading(true);
    setError(null);

    try {
      // Select item API call (no changes needed here)
      const data = await selectMenuItem(sessionId, selection);

      // Update state based on response type (no changes needed here)
      if (data.type === "content") {
        console.log("Received content response type.");
        setMenuItems(data.menu_items || []);
        setCurrentContent(data.content_markdown || "No content provided.");
      } else { // Assuming "submenu" is the other type
        console.log("Received submenu response type.");
        setMenuItems(data.menu_items || []);
        setCurrentContent(null); // Ensure content is cleared for submenus
      }

      // Update history (no changes needed here)
      setHistory(prev => [...prev, `Selected: ${selection}`]);
      console.log("Menu/Content updated via API");

    } catch (err) {
      const errorMsg = err.message || 'Failed to process selection.';
      setError(errorMsg);
      setMenuItems([]); // Clear menu on error
      setCurrentContent(null);
      console.error("Error in handleMenuSelection calling selectMenuItem API:", err);
      if (err.message && (err.message.includes("Session ID not found") || err.message.includes("404"))) {
        handleReset(); // Reset if session is gone
        setError("Session expired or invalid. Please start again.");
      }
    }
    finally { setIsLoading(false); }
  };

  // *** NEW Handler for Go Back button ***
  const handleGoBack = async () => {
    console.log("Going back one level...");
    if (!sessionId || history.length <= 1) {
      // Cannot go back if no session or only the initial topic is in history
      console.log("Cannot go back further.");
      return;
    }
    setIsLoading(true);
    setError(null);
    setCurrentContent(null); // Clear content when going back

    try {
      // Call the new goBack API function
      const data = await goBack(sessionId);

      // The backend should always return type="submenu" when going back
      if (data.type === "submenu") {
        setMenuItems(data.menu_items || []);
        // Remove the last item from frontend history to match backend state
        setHistory(prev => prev.slice(0, -1));
        console.log("Navigated back successfully.");
      } else {
        // Should not happen if backend is correct, but handle defensively
        console.error("Received unexpected response type after going back:", data.type);
        setError("An unexpected error occurred while navigating back.");
        setMenuItems([]); // Clear menu on unexpected error
      }

    } catch (err) {
      const errorMsg = err.message || 'Failed to navigate back.';
      setError(errorMsg);
      setMenuItems([]); // Clear menu on error
      console.error("Error in handleGoBack calling goBack API:", err);
      if (err.message && (err.message.includes("Session ID not found") || err.message.includes("404"))) {
        handleReset();
        setError("Session expired or invalid. Please start again.");
      }
    } finally {
      setIsLoading(false);
    }
  };


  // --- Reset Function ---
  const handleReset = () => {
    // (No changes needed here)
    console.log("Resetting session");
    setSessionId(null);
    setMenuItems([]);
    setError(null);
    setCurrentTopic('');
    setHistory([]);
    setCurrentContent(null);
    // Maybe add a call to a potential backend /clear_session endpoint if needed
  }

  // --- Render Logic (UPDATED to add Back button and fix headings) ---
  return (
    <div className="container mx-auto p-4 max-w-3xl font-sans">
      <header className="text-center mb-6 border-b pb-4">
        <h1 className="text-3xl font-bold text-blue-700">AI Subject Explorer (APP)</h1>
        {/* Navigation Buttons Container */}
        <div className="mt-2 flex justify-center space-x-4">
          {/* Show Go Back button only if not on the first level */}
          {sessionId && history.length > 1 && (
            <button
              onClick={handleGoBack}
              disabled={isLoading} // Disable while loading
              className="text-sm text-gray-500 hover:text-blue-600 underline disabled:text-gray-400 disabled:no-underline"
            >
              &larr; Go Back
            </button>
          )}
          {/* Start Over button */}
          {sessionId && (
            <button
              onClick={handleReset}
              disabled={isLoading} // Disable while loading
              className="text-sm text-gray-500 hover:text-red-600 underline disabled:text-gray-400 disabled:no-underline"
            >
              Start Over
            </button>
          )}
        </div>
      </header>

      <main>
        {isLoading && <div className="text-center p-4 text-blue-500 font-semibold">Loading...</div>}
        {error && <div className="text-center p-3 mb-4 bg-red-100 text-red-700 rounded border border-red-300">Error: {error}</div>}

        {/* Topic Input (no changes) */}
        {!isLoading && !error && !sessionId && (
          <TopicInput onSubmit={handleTopicSubmit} />
        )}

        {/* History, Content, and Menu Area */}
        {!isLoading && !error && sessionId && (
          <div className="mt-4">
            {/* History Path */}
            {history.length > 0 && (
              <div className='text-sm text-gray-600 mb-3 border-b pb-2 break-words'>
                 Path: {history.join(' → ')}
              </div>
            )}

            {/* Content Display */}
            {currentContent && (
              <div className="prose prose-sm sm:prose lg:prose-lg xl:prose-xl max-w-none p-4 border rounded bg-gray-50 mb-4">
                {/* Placeholder for ReactMarkdown or similar. Using <pre> for basic formatting. */}
                <pre className="whitespace-pre-wrap break-words">{currentContent}</pre>
              </div>
            )}

            {/* Menu List */}
            {menuItems.length > 0 && (
              <div>
                {/* *** FIXED HEADING *** */}
                <h2 className="text-xl font-semibold mb-2 text-gray-700">
                  {currentContent ? "Further exploration:" : (history.length <= 1 ? "Select a category:" : "Select a subtopic:")}
                </h2>
                <MenuList items={menuItems} onSelect={handleMenuSelection} />
              </div>
            )}
            {menuItems.length === 0 && currentContent && (
               <p className="mt-4 text-gray-600 italic">End of current exploration path for this branch.</p>
            )}
             {menuItems.length === 0 && !currentContent && (
               <p className="mt-4 text-gray-600 italic">No further subtopics found.</p> // Handle case where AI returns empty list?
            )}
          </div>
        )}
      </main>

       {/* Debug Footer */}
       {sessionId && (
          <footer className="mt-8 pt-4 border-t text-xs text-gray-500">
              Debug: Session: {sessionId.substring(0,8)}..., MaxDepth: {sessions[sessionId]?.max_menu_depth ?? 'N/A'}, CurrentDepth: {sessions[sessionId]?.history.length -1 ?? 'N/A'} {/* Note: This debug info relies on direct session access which isn't available in frontend. Keeping placeholders. Need backend to send this info if required for frontend debug */}
          </footer>
       )}
    </div>
  );
}

export default App;
