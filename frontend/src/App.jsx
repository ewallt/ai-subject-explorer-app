// *** App.jsx (Simpler debug label + lower-right position) ***
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

// Get API Base URL - Make sure api.js uses this or equivalent if needed
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function App() {
  // State variables
  const [sessionId, setSessionId] = useState(null);
  const [menuItems, setMenuItems] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [currentTopic, setCurrentTopic] = useState('');
  const [history, setHistory] = useState([]);
  const [currentContent, setCurrentContent] = useState(null);

  // --- State for Debugging ---
  const [debugCurrentDepth, setDebugCurrentDepth] = useState(null);
  const [debugMaxDepth, setDebugMaxDepth] = useState(null);
  // NEW State to track if last action was Go Back (for debug label)
  const [isDebugShowingGoBackResult, setIsDebugShowingGoBackResult] = useState(false);

  // --- API Call Handlers ---
  const handleTopicSubmit = async (topic) => {
    console.log("Submitting topic:", topic);
    // Reset state
    setIsLoading(true);
    setError(null);
    setSessionId(null);
    setMenuItems([]);
    setHistory([]);
    setCurrentTopic(topic);
    setCurrentContent(null);
    // Reset debug state
    setDebugCurrentDepth(null);
    setDebugMaxDepth(null);
    setIsDebugShowingGoBackResult(false); // <-- Reset debug flag

    try {
      // Start session
      const data = await startSession(topic); // Expects MenuResponse structure
      setSessionId(data.session_id);
      setMenuItems(data.menu_items || []);
      setHistory([`Topic: ${topic}`]); // Initial history
      // Update Debug State from /sessions response
      setDebugCurrentDepth(data.current_depth);
      setDebugMaxDepth(data.max_menu_depth);

      console.log("Real session started:", data.session_id, "Depth:", data.current_depth, "/", data.max_menu_depth);
    } catch (err) {
        const errorMsg = err.message || 'Failed to start session.';
        setError(errorMsg);
        console.error("Error in handleTopicSubmit calling startSession:", err);
    }
    finally { setIsLoading(false); }
  };

  const handleMenuSelection = async (selection) => {
    console.log("Selecting menu item:", selection);
    if (!sessionId) { console.error("No session ID available for menu selection"); return; }
    setIsLoading(true);
    setError(null);
    setIsDebugShowingGoBackResult(false); // <-- Reset debug flag

    try {
      // Select item API call
      const data = await selectMenuItem(sessionId, selection); // Expects MenuResponse

      // Update Debug State from /menus response
      setDebugCurrentDepth(data.current_depth);
      setDebugMaxDepth(data.max_menu_depth);
      console.log("Received response: Type=", data.type, "Depth:", data.current_depth, "/", data.max_menu_depth);

      // Update state based on response type
      if (data.type === "content") {
        setCurrentContent(data.content || "No content provided.");
        setMenuItems(data.menu_items || []);
      } else { // type === "submenu"
        setMenuItems(data.menu_items || []);
        setCurrentContent(null);
      }
       setHistory(prev => [...prev, `Selected: ${selection}`]);
       console.log("Menu/Content updated via API");

    } catch (err) {
       const errorMsg = err.message || 'Failed to process selection.';
       setError(errorMsg);
       console.error("Error in handleMenuSelection calling selectMenuItem:", err);
       if (err.message && (err.message.includes("Session ID not found") || err.message.includes("404"))) {
         handleReset();
         setError("Session expired or invalid. Please start again.");
       }
    }
    finally { setIsLoading(false); }
  };


  const handleGoBack = async () => {
    console.log("Going back one level...");
    if (!sessionId || history.length <= 1) {
      console.log("Cannot go back further.");
      return;
    }
    setIsLoading(true);
    setError(null);
    setCurrentContent(null);

    try {
      const data = await goBack(sessionId);

      // Update Debug State from /go_back response
      setDebugCurrentDepth(data.current_depth);
      setDebugMaxDepth(data.max_menu_depth);
      console.log("Received response from goBack: Type=", data.type, "Depth:", data.current_depth, "/", data.max_menu_depth);

      if (data.type === "submenu") {
        setMenuItems(data.menu_items || []); // <-- Updates main menu state
        setIsDebugShowingGoBackResult(true); // <-- SET debug flag
        setHistory(prev => prev.slice(0, -1));
        console.log("Navigated back successfully.");
      } else {
        console.error("Received unexpected response type after going back:", data.type);
        setError("An unexpected error occurred while navigating back.");
        setMenuItems([]);
        setIsDebugShowingGoBackResult(false); // <-- Reset debug flag on error
      }

    } catch (err) {
      const errorMsg = err.message || 'Failed to navigate back.';
      setError(errorMsg);
      setMenuItems([]);
      setIsDebugShowingGoBackResult(false); // <-- Reset debug flag on error
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
    console.log("Resetting session");
    setSessionId(null);
    setMenuItems([]);
    setIsLoading(false);
    setError(null);
    setCurrentTopic('');
    setHistory([]);
    setCurrentContent(null);
    // Reset debug state
    setDebugCurrentDepth(null);
    setDebugMaxDepth(null);
    setIsDebugShowingGoBackResult(false); // <-- Reset debug flag
  }

  // --- Render Logic ---
  return (
    <div className="container mx-auto p-4 max-w-3xl font-sans">
      <header className="text-center mb-6 border-b pb-4">
        <h1 className="text-3xl font-bold text-blue-700">AI Subject Explorer (APP)</h1>
        {/* Navigation Buttons Container */}
        <div className="mt-2 flex justify-center space-x-4">
          {sessionId && history.length > 1 && (
            <button
              onClick={handleGoBack}
              disabled={isLoading}
              className="text-sm text-gray-500 hover:text-blue-600 underline disabled:text-gray-400 disabled:no-underline"
            >
              &larr; Go Back
            </button>
          )}
          {sessionId && (
            <button
              onClick={handleReset}
              disabled={isLoading}
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

        {!isLoading && !error && !sessionId && (
          <TopicInput onSubmit={handleTopicSubmit} />
        )}

        {!isLoading && !error && sessionId && (
          <div className="mt-4">
            {history.length > 0 && ( <div className='text-sm text-gray-600 mb-3 border-b pb-2 break-words'> Path: {history.join(' → ')} </div> )}

            {currentContent && (
              <div className="prose prose-sm sm:prose lg:prose-lg xl:prose-xl max-w-none bg-gray-50 p-4 rounded border mb-4">
                 <pre style={{ whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>{currentContent}</pre>
                 {/* <ReactMarkdown>{currentContent}</ReactMarkdown> */}
               </div>
            )}

            {menuItems.length > 0 && (
              <div>
                <h2 className="text-lg font-semibold mb-2">{currentContent ? "Further Exploration:" : "Select a category:"}</h2>
                <MenuList items={menuItems} onSelect={handleMenuSelection} />
              </div>
            )}
            {menuItems.length === 0 && currentContent && (
                 <p className="text-center text-gray-500 mt-4">End of current exploration path.</p>
            )}
          </div>
        )}
      </main>

      {/* --- Debug Display (Lower Right) --- */}
      <div style={{
          // *** MOVED TO LOWER RIGHT ***
          position: 'fixed',
          bottom: '10px',
          right: '10px', // Changed from left
          // *** END OF POSITION CHANGE ***
          background: 'rgba(240, 240, 240, 0.9)',
          padding: '5px 10px',
          border: '1px solid #ccc',
          borderRadius: '4px',
          zIndex: 1000,
          fontSize: '12px',
          color: '#333',
          maxWidth: 'calc(100vw - 20px)'
      }}>
        <strong>Debug:</strong>
        {sessionId && <span style={{ marginLeft: '10px' }}>Session: {sessionId.substring(0, 6)}..</span>}
        {debugMaxDepth !== null && <span style={{ marginLeft: '10px' }}>MaxDepth: {debugMaxDepth}</span>}
        {debugCurrentDepth !== null && <span style={{ marginLeft: '10px' }}>CurrentDepth: {debugCurrentDepth}</span>}

        {/* Display Menu Items with dynamic label */}
        {sessionId && menuItems.length > 0 && (
          <span
            title={`[${menuItems.join(', ')}]`}
            style={{
              marginLeft: '10px',
              display: 'block',
              marginTop: '3px',
              maxWidth: '300px',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap'
            }}>
            {/* *** CONDITIONAL LABEL *** */}
            {isDebugShowingGoBackResult ? 'Prev. Menu (Loaded):' : 'Current Menu:'}
            {/* *** END CONDITIONAL LABEL *** */}
             [{menuItems.join(', ')}]
          </span>
        )}
         {/* Removed the separate "Last GoBack Menu" display block */}
      </div>
      {/* --- END Debug Display --- */}

    </div>
  );
}

export default App;
// *** End of App.jsx ***
