import React, { useState } from 'react';

// Receives the onSubmit function as a prop from App.jsx
function TopicInput({ onSubmit }) {
  const [topic, setTopic] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault(); // Prevent default form submission page reload
    if (topic.trim()) {
      onSubmit(topic.trim()); // Call the function passed from App.jsx
      // Decide whether to clear the input after submission
      // setTopic('');
    }
  };

  return (
    <div className="mt-4"> {/* Added margin top for spacing */}
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="Enter a topic to explore (e.g., Artificial Intelligence)" // More descriptive placeholder
          className="flex-grow p-2 border border-gray-300 rounded shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500" // Added border color, shadow
          required // Make input required
          aria-label="Topic to explore" // Accessibility
        />
        <button
          type="submit"
          className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded transition duration-150 ease-in-out shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500" // Added focus styles
        >
          Explore
        </button>
      </form>
    </div>
  );
}

export default TopicInput;
