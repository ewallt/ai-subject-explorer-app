import React, { useState } from 'react';
// Import the mock API functions
import { startSession, selectMenuItem } from './services/api';
// Import the UI components
import TopicInput from './components/TopicInput.jsx';
import MenuList from './components/MenuList.jsx';
// Import CSS
import './index.css';

function App() {
  // State variables (remain the same)
  const [sessionId, setSessionId] = useState(null);
  const [menuItems, setMenuItems] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [currentTopic, setCurrentTopic] = useState('');
  const [history, setHistory] = useState([]); // Simple history tracking

  // --- API Call Handlers (Now use imported mock functions) ---
  const handleTopicSubmit = async (topic) => {
    console.log("Submitting topic:", topic);
    setIsLoading(true);
    setError(null);
    setSessionId(null); // Reset session
    setMenuItems([]);
    setHistory([]);
    setCurrentTopic(topic);

    try {
      // Call the imported mock function
      const data = await startSession(topic);
      setSessionId(data.session_id);
      setMenuItems(data.menu_items);
      setHistory([`Topic: ${topic}`]); // Start history
      console.log("Mock session started:", data.session_id);
    } catch (err) {
       const errorMsg = err.message || 'Failed to start session.';
       setError(errorMsg);
       console.error("Error in handleTopicSubmit:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleMenuSelection = async (selection) => {
    console.log("Selecting menu item:", selection);
    if (!sessionId) {
        setError("No active session.");
        console.error("handleMenuSelection called with no sessionId");
        return;
    }
    setIsLoading(true);
    setError(null);

    try {
       // Call the imported mock function
      const data = await selectMenuItem(sessionId, selection);
      setMenuItems(data.menu_items);
      setHistory(prev => [...prev, `Selected: ${selection}`]); // Update history
      console.log("Mock menu updated");
    } catch (err) {
      const errorMsg = err.message || 'Failed to process selection.';
      setError(errorMsg);
      console.error("Error in handleMenuSelection:", err);
       // If session expired or invalid based on mock error (if implemented)
       if (err.message && err.message.toLowerCase().includes("session id not found")) {
           handleReset(); // Reset the UI
           setError("Session expired or invalid. Please start again."); // Keep specific error
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

  // --- Render Logic (Now uses imported components) ---
  return (
    <div className="container mx-auto p-4 max-w-2xl font-sans">
      <header className="text-center mb-6 border-b pb-4">
        <h1 className="text-3xl font-bold text-blue-700">AI Subject Explorer Template</h1>
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

        {/* Use TopicInput component when no session */}
        {!isLoading && !error && !sessionId && (
          <TopicInput onSubmit={handleTopicSubmit} />
        )}

        {/* Use MenuList component when session and menu items exist */}
        {!isLoading && !error && sessionId && menuItems.length > 0 && (
          <div className="mt-4">
            {/* Display history path */}
            <div className='text-sm text-gray-600 mb-3 border-b pb-2'>
                Path: {history.join(' → ')}
            </div>
            {/* Pass items and handler to MenuList component */}
            <MenuList items={menuItems} onSelect={handleMenuSelection} />
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
