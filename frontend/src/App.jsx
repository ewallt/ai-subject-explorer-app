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
        // Remove the last item from frontend history to match backend state
        setHistory(prev => prev.slice(0, -1));
        console.log("Navigated back successfully.");
      } else {
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
  }

  // --- Render Logic ---
  return (
    <div className="container mx-auto p-4 max-w-3xl font-sans">
      <header className="text-center mb-6 border-b pb-4">
        <h1 className="text
