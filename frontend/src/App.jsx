// *** App.jsx – complete file with working Main Menu handler ***
import React, { useState } from "react";

import {
  startSession,
  selectMenuItem,
  goBack,
  returnToMainMenu, // NEW import
} from "./services/api.js";

import TopicInput from "./components/TopicInput.jsx";
import MenuList from "./components/MenuList.jsx";

import "./index.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function App() {
  // ───────────────────────── State ─────────────────────────
  const [sessionId, setSessionId] = useState(null);
  const [menuItems, setMenuItems] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [currentTopic, setCurrentTopic] = useState("");
  const [history, setHistory] = useState([]);
  const [currentContent, setCurrentContent] = useState(null);
  const [debugCurrentDepth, setDebugCurrentDepth] = useState(null);
  const [debugMaxDepth, setDebugMaxDepth] = useState(null);
  const [debugLastGoBackMenu, setDebugLastGoBackMenu] = useState(null);

  // ──────────────────────── Handlers ───────────────────────
  const handleTopicSubmit = async (topic) => {
    setIsLoading(true);
    setError(null);
    setSessionId(null);
    setMenuItems([]);
    setHistory([]);
    setCurrentTopic(topic);
    setCurrentContent(null);
    setDebugCurrentDepth(null);
    setDebugMaxDepth(null);
    setDebugLastGoBackMenu(null);

    try {
      const data = await startSession(topic);
      setSessionId(data.session_id);
      setMenuItems(data.menu_items || []);
      setHistory([`Topic: ${topic}`]);
      setDebugCurrentDepth(data.current_depth);
      setDebugMaxDepth(data.max_menu_depth);
    } catch (err) {
      setError(err.message || "Failed to start session.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleMenuSelection = async (selection) => {
    if (!sessionId) return;
    setIsLoading(true);
    setError(null);

    try {
      const data = await selectMenuItem(sessionId, selection);
      setDebugCurrentDepth(data.current_depth);
      setDebugMaxDepth(data.max_menu_depth);
      setDebugLastGoBackMenu(null);

      if (data.type === "content") {
        setCurrentContent(data.content || "No content provided.");
        setMenuItems(data.menu_items || []);
      } else {
        setMenuItems(data.menu_items || []);
        setCurrentContent(null);
      }

      setHistory((prev) => [...prev, `Selected: ${selection}`]);
    } catch (err) {
      setError(err.message || "Failed to process selection.");
      if (err.message?.includes("Session ID not found")) handleReset();
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoBack = async () => {
    if (!sessionId || history.length <= 1) return;
    setIsLoading(true);
    setError(null);
    setCurrentContent(null);

    try {
      const data = await goBack(sessionId);
      setDebugCurrentDepth(data.current_depth);
      setDebugMaxDepth(data.max_menu_depth);

      if (data.type === "submenu") {
        setMenuItems(data.menu_items || []);
        setDebugLastGoBackMenu(data.menu_items || []);
        setHistory((prev) => prev.slice(0, -1));
      } else {
        setError("Unexpected response while going back.");
      }
    } catch (err) {
      setError(err.message || "Failed to navigate back.");
      if (err.message?.includes("Session ID not found")) handleReset();
    } finally {
      setIsLoading(false);
    }
  };

  // NEW – Main Menu handler
  const handleMainMenu = async () => {
    if (!sessionId) return;
    setIsLoading(true);
    setError(null);
    setCurrentContent(null);

    try {
      const data = await returnToMainMenu(sessionId);
      // depth reset values
      setDebugCurrentDepth(data.current_depth);
      setDebugMaxDepth(data.max_menu_depth);
      setDebugLastGoBackMenu(null);

      setMenuItems(data.menu_items || []);
      // keep only the topic in history
      setHistory((prev) => (prev.length ? [prev[0]] : []));
    } catch (err) {
      setError(err.message || "Failed to return to main menu.");
      if (err.message?.includes("Session ID not found")) handleReset();
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setSessionId(null);
    setMenuItems([]);
    setIsLoading(false);
    setError(null);
    setCurrentTopic("");
    setHistory([]);
    setCurrentContent(null);
    setDebugCurrentDepth(null);
    setDebugMaxDepth(null);
    setDebugLastGoBackMenu(null);
  };

  // ─────────────────────────── UI ───────────────────────────
  return (
    <div className="container mx-auto p-4 max-w-3xl font-sans">
      <header className="text-center mb-6 border-b pb-4">
        <h1 className="text-3xl font-bold text-blue-700">AI Subject Explorer (APP)</h1>
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
          {sessionId && debugCurrentDepth > 0 && (
            <button
              onClick={handleMainMenu}
              disabled={isLoading}
              className="text-sm text-gray-500 hover:text-blue-600 underline disabled:text-gray-400 disabled:no-underline"
            >
              Main Menu
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
        {error && (
          <div className="text-center p-3 mb-4 bg-red-100 text-red-700 rounded border border-red-300">
            Error: {error}
          </div>
        )}

        {!isLoading && !error && !sessionId && <TopicInput onSubmit={handleTopicSubmit} />}

        {!isLoading && !error && sessionId && (
          <div className="mt-4">
            {history.length > 0 && (
              <div className="text-sm text-gray-600 mb-3 border-b pb-2 break-words">
                Path: {history.join(" → ")}
              </div>
            )}

            {currentContent && (
              <div className="prose prose-sm sm:prose lg:prose-lg xl:prose-xl max-w-none bg-gray-50 p-4 rounded border mb-4">
                <pre style={{ whiteSpace: "pre-wrap", wordWrap: "break-word" }}>{currentContent}</pre>
              </div>
            )}

            {menuItems.length > 0 && (
              <div>
                <h2 className="text-lg font-semibold mb-2">
                  {currentContent ? "Further Exploration:" : "Select a category:"}
                </h2>
                <MenuList items={menuItems} onSelect={handleMenuSelection} />
              </div>
            )}

            {menuItems.length === 0 && currentContent && (
              <p className="text-center text-gray-500 mt-4">End of current exploration path.</p>
            )}
          </div>
        )}
      </main>

      {/* Debug footer */}
      <div
        style={{
          position: "fixed",
          bottom: "10px",
          left: "10px",
          background: "rgba(240,240,240,0.9)",
          padding: "5px 10px",
          border: "1px solid #ccc",
          borderRadius: "4px",
          zIndex: 1000,
          fontSize: "12px",
          color: "#333",
          maxWidth: "calc(100vw - 20px)",
        }}
      >
        <strong>Debug:</strong>
        {sessionId && <span style={{ marginLeft: "10px" }}>Session: {sessionId.slice(0, 6)}…</span>}
        {debugMaxDepth !== null && <span style={{ marginLeft: "10px" }}>MaxDepth: {debugMaxDepth}</span>}
        {debugCurrentDepth !== null && <span style={{ marginLeft: "10px" }}>CurrentDepth: {debugCurrentDepth}</span>}
        {sessionId && menuItems.length > 0 && (
          <span
            style={{ marginLeft: "10px", display: "block", marginTop: "3px", wordBreak: "break-all" }}
          >
            Current Menu: [{menuItems.join(", ")}]
          </span>
        )}
        {debugLastGoBackMenu && (
          <div style={{ marginTop: "5px", color: "green", wordBreak: "break-all", fontWeight: "bold" }}>
            Last GoBack Menu: [{debugLastGoBackMenu.join(", ")}]
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
