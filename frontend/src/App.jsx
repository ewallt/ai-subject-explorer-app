// *** App.jsx ***

import React, { useState } from 'react';
import {
  startSession,
  selectMenuItem,
  goBack,
  returnToMainMenu    // NEW
} from './services/api.js';

import TopicInput from './components/TopicInput.jsx';
import MenuList from './components/MenuList.jsx';
import './index.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function App() {
  const [sessionId, setSessionId] = useState(null);
  const [menuItems, setMenuItems]  = useState([]);
  const [isLoading, setIsLoading]  = useState(false);
  const [error,      setError]     = useState(null);
  const [currentTopic, setCurrentTopic] = useState('');
  const [history,    setHistory]   = useState([]);
  const [currentContent, setCurrentContent] = useState(null);
  const [debugCurrentDepth, setDebugCurrentDepth] = useState(null);
  const [debugMaxDepth,     setDebugMaxDepth]     = useState(null);

  // ── Start session ─────────────────────────────────────────────────────────
  const handleTopicSubmit = async (topic) => {
    try {
      setIsLoading(true); setError(null);
      const data = await startSession(topic);
      setSessionId(data.session_id);
      setMenuItems(data.menu_items);
      setCurrentTopic(topic);
      setHistory([`Topic: ${topic}`]);
      setCurrentContent(null);
      setDebugCurrentDepth(data.current_depth);
      setDebugMaxDepth(data.max_menu_depth);
    } catch (err) {
      setError(err.message);
    } finally { setIsLoading(false); }
  };

  // ── Select menu item ──────────────────────────────────────────────────────
  const handleMenuSelection = async (selection) => {
    if (!sessionId) return;
    try {
      setIsLoading(true); setError(null);
      const data = await selectMenuItem(sessionId, selection);
      setDebugCurrentDepth(data.current_depth);
      setDebugMaxDepth(data.max_menu_depth);

      if (data.type === "content") {
        setCurrentContent(data.content);
        setMenuItems(data.menu_items);
      } else {
        setCurrentContent(null);
        setMenuItems(data.menu_items);
      }
      setHistory(prev => [...prev, `Selected: ${selection}`]);
    } catch (err) {
      setError(err.message);
    } finally { setIsLoading(false); }
  };

  // ── Go Back ───────────────────────────────────────────────────────────────
  const handleGoBack = async () => {
    if (!sessionId) return;
    try {
      setIsLoading(true); setError(null); setCurrentContent(null);
      const data = await goBack(sessionId);
      setMenuItems(data.menu_items);
      setDebugCurrentDepth(data.current_depth);
      setHistory(prev => prev.slice(0, -1));
    } catch (err) {
      setError(err.message);
    } finally { setIsLoading(false); }
  };

  // ── NEW: Return to Main Menu ──────────────────────────────────────────────
  const handleReturnToMain = async () => {
    if (!sessionId) return;
    try {
      setIsLoading(true); setError(null); setCurrentContent(null);
      const data = await returnToMainMenu(sessionId);
      setMenuItems(data.menu_items);
      setDebugCurrentDepth(0);
      setHistory([`Topic: ${currentTopic}`]);
    } catch (err) {
      setError(err.message);
    } finally { setIsLoading(false); }
  };

  // ── Reset whole session ───────────────────────────────────────────────────
  const handleReset = () => {
    setSessionId(null); setMenuItems([]);
    setIsLoading(false); setError(null); setCurrentTopic('');
    setHistory([]); setCurrentContent(null);
    setDebugCurrentDepth(null); setDebugMaxDepth(null);
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="container mx-auto p-4 max-w-3xl font-sans">
      <header className="text-center mb-6 border-b pb-4">
        <h1 className="text-3xl font-bold text-blue-700">AI Subject Explorer (APP)</h1>

        <div className="mt-2 flex justify-center space-x-4">
          {sessionId && debugCurrentDepth > 0 && (
            <button
              onClick={handleGoBack}
              disabled={isLoading}
              className="text-sm text-gray-500 hover:text-blue-600 underline disabled:text-gray-400"
            >
              ← Go Back
            </button>
          )}

          {sessionId && debugCurrentDepth > 0 && (
            <button
              onClick={handleReturnToMain}
              disabled={isLoading}
              className="text-sm text-gray-500 hover:text-green-600 underline disabled:text-gray-400"
            >
              ⇱ Main Menu
            </button>
          )}

          {sessionId && (
            <button
              onClick={handleReset}
              disabled={isLoading}
              className="text-sm text-gray-500 hover:text-red-600 underline disabled:text-gray-400"
            >
              Start Over
            </button>
          )}
        </div>
      </header>

      <main>
        {isLoading && <div className="text-center text-blue-500">Loading…</div>}
        {error && <div className="text-center text-red-600 mb-2">{error}</div>}

        {!isLoading && !sessionId && (
          <TopicInput onSubmit={handleTopicSubmit} />
        )}

        {!isLoading && sessionId && (
          <div className="mt-4">
            {history.length > 0 && (
              <div className="text-sm text-gray-600 mb-3 border-b pb-2 break-words">
                Path: {history.join(' → ')}
              </div>
            )}

            {currentContent && (
              <div className="prose bg-gray-50 p-4 rounded border mb-4 max-w-none">
                <pre style={{whiteSpace:'pre-wrap'}}>{currentContent}</pre>
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
              <p className="text-center text-gray-500 mt-4">
                End of current exploration path.
              </p>
            )}
          </div>
        )}
      </main>

      {/* Debug footer */}
      {sessionId && (
        <div className="fixed bottom-2 left-2 bg-white/90 border px-3 py-1 text-xs rounded shadow">
          Depth {debugCurrentDepth}/{debugMaxDepth}
        </div>
      )}
    </div>
  );
}

export default App;
