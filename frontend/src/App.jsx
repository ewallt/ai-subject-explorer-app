// *** App.jsx (Complete code with enhanced Go Back debug display) ***
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

  // --- NEW: State for Debugging Depths ---
  const [debugCurrentDepth, setDebugCurrentDepth] = useState(null);
  const [debugMaxDepth, setDebugMaxDepth] = useState(null);
  const [debugLastGoBackMenu, setDebugLastGoBackMenu] = useState(null); // <-- ADDED STATE

  // --- API Call Handlers ---
  const handleTopicSubmit = async (topic) => {
    console.log("Submitting topic:", topic);
    // Wake-up call (optional, keep if needed)
    // console.log("Sending wake-up GET request to backend...");
    // try { /* ... wake-up fetch ... */ } catch (wakeError) { /* ... */ }
    // console.log("Wake-up request attempt finished.");

    // Reset state
    setIsLoading(true);
    setError(null);
    setSessionId(null);
    setMenuItems([]);
    setHistory([]);
    setCurrentTopic(topic);
    setCurrentContent(null);
    // *** NEW: Reset debug state ***
    setDebugCurrentDepth(null);
    setDebugMaxDepth(null);
    setDebugLastGoBackMenu(null); // <-- RESET DEBUG STATE

    try {
      // Start session
      const data = await startSession(topic); // Expects MenuResponse structure
      setSessionId(data.session_id);
      setMenuItems(data.menu_items || []);
      setHistory([`Topic: ${topic}`]); // Initial history

      // *** NEW: Update Debug State from /sessions response ***
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

    try {
      // Select item API call
      const data = await selectMenuItem(sessionId, selection); // Expects MenuResponse

      // *** NEW: Update Debug State from /menus response ***
      setDebugCurrentDepth(data.current_depth);
      setDebugMaxDepth(data.max_menu_depth);
      setDebugLastGoBackMenu(null); // <-- RESET DEBUG STATE ON FORWARD NAV
      console.log("Received response: Type=", data.type, "Depth:", data.current_depth, "/", data.max_menu_depth);


      // Update state based on response type
      if (data.type === "content") {
        console.log("Received content response type.");
        // Content field name from backend is 'content', not 'content_markdown' in latest model
        setCurrentContent(data.content || "No content provided.");
        // menu_items now contains further exploration topics
        setMenuItems(data.menu_items || []);
      } else { // type === "submenu"
        console.log("Received submenu response type.");
        setMenuItems(data.menu_items || []);
        setCurrentContent(null); // Clear content if showing submenu
      }

      // Update history only if not going back (Go Back handles its own history)
        setHistory(prev => [...prev, `Selected: ${selection}`]);
        console.log("Menu/Content updated via API");

    } catch (err) {
        const errorMsg = err.message || 'Failed to process selection.';
        setError(errorMsg);
        console.error("Error in handleMenuSelection calling selectMenuItem:", err);
        // Consider session reset on specific errors
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
    setCurrentContent(null); // Clear content when going back

    try {
      // Call the goBack API function - Assume it returns MenuResponse
      const data = await goBack(sessionId);

      // *** NEW: Update Debug State from /go_back response ***
      // Ensure your /go_back endpoint actually returns these fields
      setDebugCurrentDepth(data.current_depth);
      setDebugMaxDepth(data.max_menu_depth);
      console.log("Received response from goBack: Type=", data.type, "Depth:", data.current_depth, "/", data.max_menu_depth);


      // The backend should always return type="submenu" when going back
      if (data.type === "submenu") {
        setMenuItems(data.menu_items || []);
        setDebugLastGoBackMenu(data.menu_items || []); // <-- STORE RETURNED MENU FOR DEBUG
        // Remove the last item from frontend history to match backend state
        setHistory(prev => prev.slice(0, -1));
        console.log("Navigated back successfully.");
      } else {
        console.error("Received unexpected response type after going back:", data.type);
        setError("An unexpected error occurred while navigating back.");
        setMenuItems([]); // Clear menu on unexpected error
        setDebugLastGoBackMenu(null); // <-- CLEAR DEBUG ON ERROR
      }

    } catch (err) {
      const errorMsg = err.message || 'Failed to navigate back.';
      setError(errorMsg);
      setMenuItems([]); // Clear menu on error
      console.error("Error in handleGoBack calling goBack API:", err);
      if (err.message && (err.message.includes("Session ID not found") || err.message.includes("404"))) {
        handleReset();
        // No need to clear debugLastGoBackMenu here, handleReset does it
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
    // *** NEW: Reset debug state ***
    setDebugCurrentDepth(null);
    setDebugMaxDepth(null);
    setDebugLastGoBackMenu(null); // <-- RESET DEBUG STATE
  }

  // --- Render Logic ---
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

        {/* Topic Input */}
        {!isLoading && !error && !sessionId && (
          <TopicInput onSubmit={handleTopicSubmit} />
        )}

        {/* History, Content, and Menu Area */}
        {!isLoading && !error && sessionId && (
          <div className="mt-4">
            {/* History Path */}
            {history.length > 0 && ( <div className='text-sm text-gray-600 mb-3 border-b pb-2 break-words'> Path: {history.join(' → ')} </div> )}

            {/* Content Display */}
            {/* Remember to uncomment and use ReactMarkdown or similar if needed */}
            {currentContent && (
              <div className="prose prose-sm sm:prose lg:prose-lg xl:prose-xl max-w-none bg-gray-50 p-4 rounded border mb-4">
                  {/* Using basic div - replace with Markdown renderer if desired */}
                  <pre style={{ whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>{currentContent}</pre>
                  {/* Example using ReactMarkdown (if installed and imported): */}
                  {/* <ReactMarkdown>{currentContent}</ReactMarkdown> */}
                </div>
            )}

            {/* Menu List */}
            {menuItems.length > 0 && (
              <div>
                <h2 className="text-lg font-semibold mb-2">{currentContent ? "Further Exploration:" : "Select a category:"}</h2>
                <MenuList items={menuItems} onSelect={handleMenuSelection} />
              </div>
            )}
            {/* Message when content is shown but no further topics */}
            {menuItems.length === 0 && currentContent && (
                 <p className="text-center text-gray-500 mt-4">End of current exploration path.</p>
            )}
          </div>
        )}
      </main>

      {/* --- Debug Display --- */}
      {/* Positioned fixed at bottom-left */}
      <div style={{
          position: 'fixed',
          bottom: '10px',
          left: '10px',
          background: 'rgba(240, 240, 240, 0.9)',
          padding: '5px 10px',
          border: '1px solid #ccc',
          borderRadius: '4px',
          zIndex: 1000,
          fontSize: '12px',
          color: '#333',
          maxWidth: 'calc(100vw - 20px)' // Prevent excessive width
      }}>
        <strong>Debug:</strong>
        {sessionId && <span style={{ marginLeft: '10px' }}>Session: {sessionId.substring(0, 6)}..</span>}
        {debugMaxDepth !== null && <span style={{ marginLeft: '10px' }}>MaxDepth: {debugMaxDepth}</span>}
        {debugCurrentDepth !== null && <span style={{ marginLeft: '10px' }}>CurrentDepth: {debugCurrentDepth}</span>}

        {/* Display Current Menu, allowing wrapping */}
        {sessionId && menuItems.length > 0 && (
          <span
            title={`[${menuItems.join(', ')}]`} // Hover tooltip (may or may not work reliably)
            style={{
              marginLeft: '10px',
              display: 'block', // Put it on a new line within the box
              marginTop: '3px',
              // Original truncation styles removed to allow wrapping like the GoBack menu
              wordBreak: 'break-all', // Allow wrapping
            }}>
            Current Menu: [{menuItems.join(', ')}]
          </span>
        )}
        {/* --- Display Last Go Back Menu --- */}
        {debugLastGoBackMenu && (
          <div style={{ marginTop: '5px', color: 'green', wordBreak: 'break-all', fontSize: '12px', fontWeight: 'bold' }}> {/* Enhanced styling */}
            Last GoBack Menu: [{debugLastGoBackMenu.join(', ')}]
          </div>
        )}
        {/* --- END OF Go Back Menu Display --- */}

      </div>
      {/* --- END Debug Display --- */}

    </div>
  );
}

export default App;
// *** End of App.jsx ***
