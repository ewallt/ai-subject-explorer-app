import React, { useState, useEffect } from 'react';
// Import the API functions
import { startSession, selectMenuItem } from './services/api.js';
// Import the UI components
import TopicInput from './components/TopicInput.jsx';
import MenuList from './components/MenuList.jsx';
// Import a Markdown renderer (optional but recommended for better display)
// You might need to install it: npm install react-markdown
// If you don't want to install it now, we can render raw markdown temporarily.
// import ReactMarkdown from 'react-markdown'; // Uncomment if installed

// Import CSS
import './index.css';

// Get API Base URL
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function App() {
  // State variables
  const [sessionId, setSessionId] = useState(null);
  const [menuItems, setMenuItems] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [currentTopic, setCurrentTopic] = useState('');
  const [history, setHistory] = useState([]);
  // *** NEW state variable for markdown content ***
  const [currentContent, setCurrentContent] = useState(null);

  // --- API Call Handlers ---
  const handleTopicSubmit = async (topic) => {
    console.log("Submitting topic:", topic);

    // --- Wake-up Call ---
    console.log("Sending wake-up GET request to backend...");
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3000);
      await fetch(`${API_BASE_URL}/`, { signal: controller.signal });
      clearTimeout(timeoutId);
      console.log("Wake-up request attempt finished.");
    } catch (wakeError) {
      console.warn("Wake-up request failed or timed out:", wakeError);
    }
    // --- End Wake-up Call ---

    setIsLoading(true);
    setError(null);
    setSessionId(null);
    setMenuItems([]);
    setHistory([]);
    setCurrentTopic(topic);
    setCurrentContent(null); // Reset content on new topic

    try {
      const data = await startSession(topic);
      setSessionId(data.session_id);
      setMenuItems(data.menu_items);
      setHistory([`Topic: ${topic}`]); // Initialize history
      console.log("Real session started:", data.session_id);
    } catch (err) {
      const errorMsg = err.message || 'Failed to start session.';
      setError(errorMsg);
      console.error("Error in handleTopicSubmit calling startSession:", err);
    } finally {
      setIsLoading(false);
    }
  };

  // *** UPDATED handleMenuSelection to handle 'content' type ***
  const handleMenuSelection = async (selection) => {
    console.log("Selecting menu item:", selection);
    if (!sessionId) {
      setError("No active session.");
      console.error("handleMenuSelection called with no sessionId");
      return;
    }
    setIsLoading(true);
    setError(null);
    // Keep existing content visible while loading new content/menu
    // setCurrentContent(null); // Optional: Clear content immediately? Or wait for response? Let's wait.

    try {
      // Call the API (this now returns { type, menu_items, content_markdown })
      const data = await selectMenuItem(sessionId, selection);

      // Update state based on the response type
      if (data.type === "content") {
        console.log("Received content response type.");
        setMenuItems(data.menu_items || []); // Display "further topics" as the menu
        setCurrentContent(data.content_markdown || "No content provided."); // Set the markdown content
      } else { // Default to "submenu" or handle other types if added later
        console.log("Received submenu response type.");
        setMenuItems(data.menu_items || []);
        setCurrentContent(null); // Clear content if navigating to a submenu
      }

      // Update history regardless of type
      setHistory(prev => [...prev, `Selected: ${selection}`]);
      console.log("Menu/Content updated via API");

    } catch (err) {
      const errorMsg = err.message || 'Failed to process selection.';
      setError(errorMsg);
      setCurrentContent(null); // Clear content on error
      setMenuItems([]); // Clear menu on error? Or keep last good menu? Let's clear for now.
      console.error("Error in handleMenuSelection calling selectMenuItem:", err);
      if (err.message && (err.message.includes("Session ID not found") || err.message.includes("404"))) {
        handleReset(); // Reset fully if session is gone
        setError("Session expired or invalid. Please start again.");
      }
       if (err.message && (err.message.includes("501") || err.message.includes("MAX_DEPTH_EXCEEDED"))) {
         // Handle the specific 501 error if we re-introduce it later
         setError("Navigation beyond the implemented depth is not yet supported.");
       }
    } finally {
      setIsLoading(false);
    }
  };

  // --- Reset Function ---
  const handleReset = () => {
    console.log("Resetting session");
    setSessionId(null);
    setMenuItems([]);
    setCurrentTopic('');
    setHistory([]);
    setError(null);
    setIsLoading(false);
    setCurrentContent(null); // Reset content
  }

  // --- Render Logic (UPDATED to show content) ---
  return (
    <div className="container mx-auto p-4 max-w-3xl font-sans"> {/* Increased max-width slightly */}
      <header className="text-center mb-6 border-b pb-4">
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

        {/* Show Topic Input only when no session active */}
        {!isLoading && !error && !sessionId && (
          <TopicInput onSubmit={handleTopicSubmit} />
        )}

        {/* Show History, Content, and Menu when session is active */}
        {!isLoading && !error && sessionId && (
          <div className="mt-4">
            {/* Display History Path */}
            {history.length > 0 && (
               <div className='text-sm text-gray-600 mb-3 border-b pb-2 break-words'> {/* Added break-words */}
                 Path: {history.join(' → ')}
               </div>
            )}

            {/* *** Conditionally Display Content *** */}
            {currentContent && (
              <div className="prose prose-sm sm:prose lg:prose-lg xl:prose-xl max-w-none p-4 mb-4 border rounded bg-gray-50">
                {/* Option 1: Render raw markdown (simple) */}
                <pre className="whitespace-pre-wrap font-sans">{currentContent}</pre>

                {/* Option 2: Use react-markdown (nicer formatting) */}
                {/* Make sure to uncomment the import above and install the package */}
                {/* <ReactMarkdown>{currentContent}</ReactMarkdown> */}
              </div>
            )}

            {/* Display Menu List (Submenu or Further Topics) */}
            {menuItems.length > 0 && (
               <div>
                 <h2 className="text-lg font-semibold mb-2">{currentContent ? "Further Exploration:" : "Select an option:"}</h2>
                 <MenuList items={menuItems} onSelect={handleMenuSelection} />
               </div>
            )}
             {/* Handle case where menu items might be empty (e.g., end of path?) */}
             {menuItems.length === 0 && currentContent && (
                <p className="text-center text-gray-500 mt-4">End of current exploration path.</p>
             )}
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
