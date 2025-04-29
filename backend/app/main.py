# *** main.py ***

import os, uuid, json
from typing import List, Dict, Any, Optional, Tuple, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import openai

# ────────────────────────────────────────────────────────
#  Pydantic models
# ────────────────────────────────────────────────────────
class TopicInput(BaseModel):
    topic: str


class MenuSelection(BaseModel):
    session_id: str
    selection: str


# NEW – for endpoints that only need the session ID
class SessionRequest(BaseModel):
    session_id: str


class MenuResponse(BaseModel):
    type: Literal["submenu", "content"]
    menu_items: Optional[List[str]] = None
    content: Optional[str] = None
    session_id: str
    current_depth: int
    max_menu_depth: int


# ────────────────────────────────────────────────────────
#  Init
# ────────────────────────────────────────────────────────
load_dotenv()
openai_client = None
try:
    openai_client = openai.OpenAI()
    if not openai_client.api_key:
        print("WARNING: OPENAI_API_KEY missing/blank.")
        openai_client = None
    else:
        print("✓ OpenAI client initialised.")
except Exception as e:
    print(f"ERROR initialising OpenAI: {e}")
    openai_client = None

app = FastAPI(title="AI Subject Explorer Backend", version="0.6.0")

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

# ────────────────────────────────────────────────────────
#  In-memory sessions
# ────────────────────────────────────────────────────────
sessions: Dict[str, Dict[str, Any]] = {}

# ────────────────────────────────────────────────────────
#  AI helper functions  (unchanged)
# ────────────────────────────────────────────────────────
# generate_main_menu_with_ai(...)
# generate_submenu_with_ai(...)
# generate_content_and_further_topics_with_ai(...)
# (all three functions are IDENTICAL to the version you sent me)

# ────────────────────────────────────────────────────────
#  Endpoints   (new /main_menu added)
# ────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "message": "AI Subject Explorer Backend is alive!",
        "version": app.version,
        "openai_ready": openai_client is not None,
        "active_sessions": len(sessions),
    }


@app.post("/sessions", response_model=MenuResponse, status_code=201)
async def create_session(topic_input: TopicInput):
    # … your original body unchanged …
    # (includes menu_by_depth initialisation)
    # -----------------------------------------------------
    # PASTE YOUR ORIGINAL FUNCTION BODY HERE
    # -----------------------------------------------------


@app.post("/menus", response_model=MenuResponse, status_code=200)
async def select_menu_item(menu_selection: MenuSelection):
    # … your original body unchanged …
    # -----------------------------------------------------
    # PASTE YOUR ORIGINAL FUNCTION BODY HERE
    # -----------------------------------------------------


# NEW ────────────────────────────────────────────────────
@app.post("/main_menu", response_model=MenuResponse, status_code=200)
async def return_to_main_menu(req: SessionRequest):
    """
    Reset session to depth 0 and return the root menu.
    """
    session_id = req.session_id
    print(f"→ /main_menu for session {session_id}")

    if session_id not in sessions:
        raise HTTPException(
            404,
            detail={
                "error": {
                    "code": "SESSION_NOT_FOUND",
                    "message": "Session ID not found.",
                }
            },
        )

    s = sessions[session_id]

    # root menu is always stored at depth 0
    root_menu = s.get("menu_by_depth", {}).get(0, [])
    if not root_menu:
        # graceful fallback
        root_menu = s.get("current_menu", [])
        print("⚠ root_menu missing; using current_menu fallback")

    s["current_menu"] = root_menu
    s["current_depth"] = 0
    s["last_content"] = None
    # trim history → keep only the initial topic entry
    s["history"] = [entry for entry in s.get("history", []) if entry[0] == "topic"]
    sessions[session_id] = s

    print(f"✓ session {session_id} reset to main menu.")

    return MenuResponse(
        type="submenu",
        menu_items=root_menu,
        content=None,
        session_id=session_id,
        current_depth=0,
        max_menu_depth=s["max_menu_depth"],
    )


# ────────────────────────────────────────────────────────
#  Uvicorn (unchanged)
# ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.environ.get("ENVIRONMENT", "") == "development",
    )

# *** end of main.py ***
