import os
import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

# --- Pydantic Models ---
class TopicInput(BaseModel):
    topic: str

class SessionResponse(BaseModel):
    session_id: str
    menu_items: List[str]

class MenuSelection(BaseModel):
    session_id: str
    selection: str

class MenuResponse(BaseModel):
    menu_items: List[str]

# --- FastAPI App Initialization ---
app = FastAPI(
    title="AI Subject Explorer Backend Test1",
    description="API for the AI Subject Explorer.",
    version="0.1.0",
)

# --- In-Memory Session Storage ---
sessions: Dict[str, Dict[str, Any]] = {}

# --- Mock/Placeholder AI Calls ---
def get_main_menu_placeholder(topic: str) -> List[str]:
    """ Placeholder function to generate a basic main menu. """
    print(f"--- MOCK BACKEND: Generating main menu for topic: '{topic}' ---")
    return [
        f"Introduction to {topic}",
        f"History of {topic}",
        f"Applications of {topic}",
        f"Future of {topic}"
    ]

# MODIFIED Placeholder function for submenus
def get_submenu_placeholder(session_data: Dict[str, Any], selection: str) -> List[str]:
    """ Placeholder function to generate a submenu based on selection. """
    print(f"--- MOCK BACKEND: Generating submenu for selection: '{selection}' (With Test Marker)---") # Added marker to log
    topic = session_data.get("topic", "Unknown Topic")
    submenu_items = [] # Initialize empty list

    if "history" in selection.lower():
        # Added "Test 1: " prefix to the first item
        submenu_items = [f"Test 1: Early {topic} History", f"Mid-Century {topic}", f"Recent {topic}"]
    elif "introduction" in selection.lower():
        # Added "Test 1: " prefix to the first item
         submenu_items = [f"Test 1: Core Concept A for {topic}", f"Core Concept B", f"Related Terms for {topic}"]
    elif "applications" in selection.lower():
        # Added "Test 1: " prefix to the first item
        submenu_items = [f"Test 1: Use Case 1 ({topic})", f"Use Case 2", f"Industry Examples ({topic})"]
    else:
        # Default fallback submenu - Added "Test 1: " prefix
        submenu_items = [f"Test 1: Sub-Item 1 for {selection}", f"Sub-Item 2 ({topic})", f"Sub-Item 3"]

    # Ensure we always return a list, adding marker if list was empty
    if not submenu_items:
        submenu_items = [f"Test 1: Default item for {selection}"]

    return submenu_items

# --- API Endpoints ---
# (Keep the / and /sessions endpoints exactly as they were in the previous code block)
@app.get("/")
async def read_root():
    """ Basic health check endpoint. """
    return {"message": "AI Subject Explorer Backend is alive!"}

@app.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=201,
    summary="Start a new exploration session",
    tags=["Session Management"]
)
async def create_session(topic_input: TopicInput):
    """ Creates a new session and returns the first menu. """
    session_id = str(uuid.uuid4())
    topic = topic_input.topic
    print(f"--- Received POST /sessions request for topic: '{topic}' ---")
    try:
        main_menu_items = get_main_menu_placeholder(topic)
        if not main_menu_items:
             raise ValueError("Placeholder menu generation returned empty list")
    except Exception as e:
        print(f"ERROR in /sessions generating placeholder menu: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "MENU_GENERATION_FAILED", "message": str(e)}}
        )
    sessions[session_id] = {
        "history": [("topic", topic)],
        "current_menu": main_menu_items,
        "topic": topic
    }
    print(f"--- Session '{session_id}' created successfully. State stored. ---")
    return SessionResponse(session_id=session_id, menu_items=main_menu_items)


@app.post(
    "/menus",
    response_model=MenuResponse,
    status_code=200,
    summary="Process menu selection and get next menu",
    tags=["Navigation"]
)
async def select_menu_item(menu_selection: MenuSelection):
    """
    Takes a session ID and user selection, retrieves session state,
    validates selection, generates the next menu (using placeholder),
    updates state, and returns the new menu.
    """
    session_id = menu_selection.session_id
    selection = menu_selection.selection
    print(f"--- Received POST /menus request for session '{session_id}', selection: '{selection}' ---")

    # 1. Retrieve session state
    if session_id not in sessions:
        print(f"ERROR in /menus: Session ID '{session_id}' not found.")
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "SESSION_NOT_FOUND", "message": "Session ID not found or expired"}}
        )
    session_data = sessions[session_id]

    # 2. Validate selection
    current_menu = session_data.get("current_menu", [])
    if selection not in current_menu:
        print(f"ERROR in /menus: Selection '{selection}' not found in current menu for session '{session_id}'. Current menu: {current_menu}")
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_SELECTION", "message": f"Selection '{selection}' is not a valid option in the current menu."}}
        )

    # 3. Generate next menu items (using placeholder)
    try:
        # Calls the MODIFIED placeholder function
        submenu_items = get_submenu_placeholder(session_data, selection)
        if not submenu_items:
             raise ValueError("Placeholder submenu generation returned empty list")
    except Exception as e:
        print(f"ERROR in /menus generating placeholder submenu: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "SUBMENU_GENERATION_FAILED", "message": str(e)}}
        )

    # 4. Update session state
    session_data["history"].append(("menu_selection", selection))
    session_data["current_menu"] = submenu_items
    sessions[session_id] = session_data
    print(f"--- Session '{session_id}' updated. New menu generated. ---")

    # 5. Return the new menu
    return MenuResponse(menu_items=submenu_items)

# --- Uvicorn runner (for reference) ---
# (Keep existing block)
# if __name__ == "__main__":
# ...
