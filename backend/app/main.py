# *** main.py ***

import os
import uuid
import json
from typing import List, Dict, Any, Optional, Tuple, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import openai

# ────────────────────────────────────────────────────────────────────────────────
# Pydantic Models
# ────────────────────────────────────────────────────────────────────────────────

class TopicInput(BaseModel):
    topic: str


class MenuSelection(BaseModel):
    session_id: str
    selection: str


# NEW – simple body for endpoints that just need a session ID
class SessionRequest(BaseModel):
    session_id: str


class MenuResponse(BaseModel):
    type: Literal["submenu", "content"]
    menu_items: Optional[List[str]] = None  # submenu or further-topics list
    content: Optional[str] = None           # markdown (only for “content”)
    session_id: str
    current_depth: int
    max_menu_depth: int


# ────────────────────────────────────────────────────────────────────────────────
# Configuration & Initialization
# ────────────────────────────────────────────────────────────────────────────────

load_dotenv()
openai_client = None
try:
    openai_client = openai.OpenAI()
    if not openai_client.api_key:
        print("WARNING: OPENAI_API_KEY environment variable missing.")
        openai_client = None
    else:
        print("--- OpenAI client initialized successfully. ---")
except Exception as e:
    print(f"ERROR: Failed to initialize OpenAI client: {e}")
    openai_client = None

app = FastAPI(title="AI Subject Explorer Backend", version="0.6.0")

# ────────────────────────────────────────────────────────────────────────────────
# CORS
# ────────────────────────────────────────────────────────────────────────────────

origins = [
    "https://ai-subject-explorer-app-frontend.onrender.com",
    # "http://localhost:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ────────────────────────────────────────────────────────────────────────────────
# In-Memory Session Storage
# ────────────────────────────────────────────────────────────────────────────────

# session_id → {
#   topic, history, current_menu, max_menu_depth, current_depth,
#   last_content, menu_by_depth
# }
sessions: Dict[str, Dict[str, Any]] = {}

# ────────────────────────────────────────────────────────────────────────────────
# AI helper functions (unchanged)
# ────────────────────────────────────────────────────────────────────────────────
# ... generate_main_menu_with_ai
# ... generate_submenu_with_ai
# ... generate_content_and_further_topics_with_ai
# (functions omitted here for brevity – they are identical to your current copy)
# ────────────────────────────────────────────────────────────────────────────────

# ────────────────────────────────────────────────────────────────────────────────
# API Endpoints
# ────────────────────────────────────────────────────────────────────────────────

@app.get("/")
async def read_root():
    return {"message": "AI Subject Explorer Backend is alive!"}


# ─────────── Session start (unchanged) ───────────
@app.post(
    "/sessions",
    response_model=MenuResponse,
    status_code=201,
    summary="Start a new exploration session",
    tags=["Session Management"],
)
async def create_session(topic_input: TopicInput):
    # (body identical to your previous version, including menu_by_depth init)
    # ...


# ─────────── Menu navigation (unchanged) ───────────
@app.post(
    "/menus",
    response_model=MenuResponse,
    status_code=200,
    summary="Process menu selection",
    tags=["Navigation"],
)
async def select_menu_item(menu_selection: MenuSelection):
    # (body identical to your previous version)
    # ...


# ────────────────────────────────────────────────────────────────────────────────
# NEW – Return to Main Menu
# ────────────────────────────────────────────────────────────────────────────────
@app.post(
    "/main_menu",
    response_model=MenuResponse,
    status_code=200,
    summary="Return to top-level menu",
    tags=["Navigation"],
)
async def return_to_main_menu(req: SessionRequest):
    """
    Reset the session to depth 0 and return the original root menu.
    """
    session_id = req.session_id
    print(f"--- POST /main_menu for session '{session_id}' ---")

    # Validate session
    if session_id not in sessions:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "SESSION_NOT_FOUND", "message": "Session ID not found."}},
        )
    session_data = sessions[session_id]

    # Recover root menu
    root_menu = session_data.get("menu_by_depth", {}).get(0, [])
    if not root_menu:
        root_menu = session_data.get("current_menu", [])
        print("WARNING: root menu missing; using current_menu fallback.")

    # Reset depth / history
    session_data["current_menu"] = root_menu
    session_data["current_depth"] = 0
    session_data["last_content"] = None
    session_data["history"] = [entry for entry in session_data.get("history", []) if entry[0] == "topic"]
    sessions[session_id] = session_data

    max_menu_depth = session_data.get("max_menu_depth", 2)
    print(f"--- Session '{session_id}' reset to main menu (0/{max_menu_depth}). ---")

    return MenuResponse(
        type="submenu",
        menu_items=root_menu,
        content=None,
        session_id=session_id,
        current_depth=0,
        max_menu_depth=max_menu_depth,
    )


# ────────────────────────────────────────────────────────────────────────────────
# Uvicorn runner (unchanged)
# ────────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    is_local_dev = os.environ.get("ENVIRONMENT", "production") == "development"
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=is_local_dev)

# *** End of main.py ***
