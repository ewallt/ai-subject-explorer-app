import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'    // We'll create App.jsx next
import './index.css'      // Import the CSS file with Tailwind directives

// This finds the <div id="root"> in your index.html and renders the App component into it
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
