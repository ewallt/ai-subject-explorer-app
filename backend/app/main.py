import os
import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

# --- Pydantic Models (Data Shapes for API) ---
# Defines the expected structure for request and response bodies.

class TopicInput(BaseModel):
    """ Expected input for starting a session. """
    topic: str

class SessionResponse(BaseModel):
    """ Expected output when a session is created. """
    session_id: str
    menu_items: List[str]

# --- FastAPI App Initialization ---
app = FastAPI(
    title="AI Subject Explorer Backend",
    description="API for the AI Subject Explorer.",
    version="0.1.0",
)

# --- In-Memory Session Storage ---
# A simple Python dictionary to store session data while the server is running.
# Data will be lost on server restart (as per our "Simplicity First" decision).
# Structure: { "session_id": {"history": List[Any], "current_menu": List[str], "topic": str}, ... }
sessions: Dict[str, Dict[str, Any]] = {}

# --- Mock/Placeholder AI Call ---
# We'll replace this later with actual calls to the OpenAI API.
def get_main_menu_placeholder(topic: str) -> List[str]:
    """ Placeholder function to generate a basic main menu. """
    print(f"--- MOCK BACKEND: Generating main menu for topic: '{topic}' ---")
    # Return a simple list based on the topic for now
    return [
        f"Introduction to {topic}",
        f"History of {topic}",
        f"Applications of {topic}",
        f"Future of {topic}"
    ]

# --- API Endpoints ---

@app.get("/")
async def read_root():
    """ Basic health check endpoint. """
    return {"message": "AI Subject Explorer Backend is alive!"}

@app.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=201, # HTTP status code for resource creation
    summary="Start a new exploration session",
    tags=["Session Management"] # Optional tag for grouping in /docs
)
async def create_session(topic_input: TopicInput):
    """
    Receives a topic, generates a unique session ID, gets the initial
    main menu items (using a placeholder for now), stores the initial state,
    and returns the session ID and menu items.
    """
    session_id = str(uuid.uuid4()) # Generate a unique ID
    topic = topic_input.topic
    print(f"--- Received POST /sessions request for topic: '{topic}' ---")

    try:
        # Use the placeholder function for initial implementation
        main_menu_items = get_main_menu_placeholder(topic)
        if not main_menu_items: # Should not happen with placeholder, but good check
            raise ValueError("Placeholder menu generation returned empty list")

    except Exception as e:
        print(f"ERROR in /sessions generating placeholder menu: {e}")
        # Return a standard HTTP error response
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "MENU_GENERATION_FAILED", "message": str(e)}}
        )

    # Store the initial state for this session in our in-memory dictionary
    sessions[session_id] = {
        "history": [("topic", topic)], # Keep track of the path
        "current_menu": main_menu_items, # What options are currently shown
        "topic": topic # Store original topic for context
    }
    print(f"--- Session '{session_id}' created successfully. State stored. ---")
    # Useful for debugging, but avoid logging entire state in production
    # print(f"--- Current sessions count: {len(sessions)} ---")

    # Return the response defined by the SessionResponse model
    return SessionResponse(session_id=session_id, menu_items=main_menu_items)

# --- Add POST /menus endpoint here later ---


# --- Uvicorn runner (for local testing reference) ---
if __name__ == "__main__":
    # This block is generally not used by Render's deployment process.
    # Render uses the Start Command from settings (e.g., uvicorn app.main:app ...)
    print("Reminder: Run using 'uvicorn app.main:app --reload --port 8000 --app-dir backend' from terminal for local dev.")
    # Optionally run directly (might have import issues depending on cwd):
    # import uvicorn
    # port = int(os.environ.get("PORT", 8000))
    # uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
