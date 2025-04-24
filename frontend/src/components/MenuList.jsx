import React from 'react';

// Receives the 'items' (array of strings) and 'onSelect' function as props
function MenuList({ items, onSelect }) {
  // Handle case where items might be null or empty initially
  if (!items || items.length === 0) {
    return <p className="text-gray-500 mt-4">No menu options available at this time.</p>;
  }

  return (
    <div className="mt-4"> {/* Added margin top */}
      <h2 className="text-xl font-semibold mb-3 text-gray-800">Select an option:</h2>
      <div className="space-y-2">
        {items.map((item, index) => (
          <button
            // Using index as key is okay if list is stable per render
            key={index}
            onClick={() => onSelect(item)} // Call the onSelect function passed from App.jsx
            className="block w-full text-left p-3 bg-gray-100 hover:bg-blue-100 rounded border border-gray-200 transition duration-150 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus-visible:ring-blue-500" // Added focus-visible
            aria-label={`Select option: ${item}`} // Accessibility
          >
            {item} {/* Display the menu item text */}
          </button>
        ))}
      </div>
    </div>
  );
}

export default MenuList;
