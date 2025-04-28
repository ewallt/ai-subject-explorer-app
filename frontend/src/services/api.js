# *** main.py ***

import os
import uuid
import json
from typing import List, Dict, Any, Optional, Tuple, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import openai


# --------------------------------------------------------------------------- #
#                           Pydantic Models                                   #
# --------------------------------------------------------------------------- #

class TopicInput(BaseModel):
    topic: str


class MenuSelection(BaseModel):
    session_id: str
    selection: str


class MenuResponse(BaseModel):
    type: Literal["submenu", "content"]
    menu_items: Optional[List[str]] = None  # Items for submenu or further topics
    content: Optional[str] = None           # Markdown (only when type == "content")
    session_id: str
    current_depth: int
    max_menu_depth: int


class GoBackRequest(BaseModel):
    """Payload for navigating one level up."""
    session_id: str


# --------------------------------------------------------------------------- #
#                         Configuration & Init                                #
# --------------------------------------------------------------------------- #

load_dotenv()
openai_client = None
try:
    openai_client = openai.OpenAI()
    if not openai_client.api_key:
        print("WARNING: OPENAI_API_KEY not found or empty.")
        openai_client = None
    else:
        print("--- OpenAI client initialized successfully. ---")
except Exception as e:
    print(f"ERROR: Failed to initialize OpenAI client: {e}")
    openai_client = None

app = FastAPI(title="AI Subject Explorer Backend", version="0.6.0")

origins = [
    "https://ai-subject-explorer-app-frontend.onrender.com",
    # add dev origins as needed
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------------- #
#                        In-Memory Session Store                              #
# --------------------------------------------------------------------------- #
# session_id -> {
#   topic, history, current_menu, max_menu_depth,
#   current_depth, last_content, menu_by_depth
# }
sessions: Dict[str, Dict[str, Any]] = {}


# --------------------------------------------------------------------------- #
#                      OpenAI Helper Functions                                #
#   (generate_main_menu_with_ai, generate_submenu_with_ai,                    #
#    generate_content_and_further_topics_with_ai) – unchanged                 #
# --------------------------------------------------------------------------- #

# ...  (Functions unchanged – omitted here for brevity.  Keep exactly as in your
#       current repo.) ...


# --------------------------------------------------------------------------- #
#                               Endpoints                                     #
# --------------------------------------------------------------------------- #

@app.get("/")
async def read_root():
    return {"message": "AI Subject Explorer Backend is alive!"}


# -----------------------------  /sessions  ---------------------------------- #
@app.post(
    "/sessions",
    response_model=MenuResponse,
    status_code=201,
    summary="Start a new exploration session",
    tags=["Session Management"],
)
async def create_session(topic_input: TopicInput):
    # (Body identical to the version you supplied – no changes)
    # ...


# ------------------------------  /menus  ------------------------------------ #
@app.post(
    "/menus",
    response_model=MenuResponse,
    status_code=200,
    summary="Process menu selection and get next items/content",
    tags=["Navigation"],
)
async def select_menu_item(menu_selection: MenuSelection):
    # (Body identical to the version you supplied – no changes)
    # ...


# -----------------------------  /go_back  ----------------------------------- #
@app.post(
    "/go_back",
    response_model=MenuResponse,
    status_code=200,
    summary="Navigate back one level in the exploration menu",
    tags=["Navigation"],
)
async def go_back(go_back_req: GoBackRequest):
    session_id = go_back_req.session_id
    print(f"--- Received POST /go_back for session '{session_id}' ---")

    if session_id not in sessions:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "SESSION_NOT_FOUND",
                              "message": "Session ID not found."}},
        )

    sd = sessions[session_id]
    cur_depth = sd.get("current_depth", 0)
    max_depth = sd.get("max_menu_depth", 0)

    if cur_depth == 0:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "AT_ROOT_LEVEL",
                              "message": "Already at top level; cannot go back."}},
        )

    prev_depth = cur_depth - 1
    menu_by_depth: Dict[int, List[str]] = sd.get("menu_by_depth", {})

    if prev_depth not in menu_by_depth:
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "STATE_INCONSISTENT",
                              "message": "Previous menu missing."}},
        )

    # Trim last history item if it is a menu selection
    hist = sd.get("history", [])
    if hist and hist[-1][0] == "menu_selection":
        hist.pop()

    # Restore previous menu
    sd.update(
        {
            "current_depth": prev_depth,
            "current_menu": menu_by_depth[prev_depth],
            "history": hist,
            "last_content": None,
        }
    )
    sessions[session_id] = sd

    print(
        f"--- Session '{session_id}' back to depth {prev_depth} "
        f"(menu items: {len(menu_by_depth[prev_depth])}) ---"
    )

    return MenuResponse(
        type="submenu",
        menu_items=menu_by_depth[prev_depth],
        content=None,
        session_id=session_id,
        current_depth=prev_depth,
        max_menu_depth=max_depth,
    )


# ------------------------------  runner  ------------------------------------ #
if __name__ == "__main__":
    import uvicorn
    print("--- Starting Uvicorn (local) ---")
    port = int(os.environ.get("PORT", 8000))
    is_local_dev = os.environ.get("ENVIRONMENT", "production") == "development"
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=is_local_dev)

# *** End of main.py ***
