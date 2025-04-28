# *** main.py ***

import os, uuid, json
from typing import List, Dict, Any, Tuple, Optional, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai

# ───────────────────────────────
#  Models
# ───────────────────────────────
class TopicInput(BaseModel):
    topic: str


class MenuSelection(BaseModel):
    session_id: str
    selection: str


class MenuResponse(BaseModel):
    type: Literal["submenu", "content"]
    menu_items: Optional[List[str]] = None
    content: Optional[str] = None
    session_id: str
    current_depth: int
    max_menu_depth: int


# NEW – for /go_back and /main_menu
class GoBackRequest(BaseModel):
    session_id: str


class ReturnToMainRequest(BaseModel):
    session_id: str


# ───────────────────────────────
#  Initialisation
# ───────────────────────────────
load_dotenv()
openai_client = None
try:
    openai_client = openai.OpenAI()
    if not openai_client.api_key:
        print("WARNING: OPENAI_API_KEY not set")
        openai_client = None
    else:
        print("--- OpenAI client ready ---")
except Exception as e:
    print(f"OpenAI init error: {e}")
    openai_client = None

app = FastAPI(title="AI Subject Explorer Backend", version="0.7.0")

origins = ["https://ai-subject-explorer-app-frontend.onrender.com"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ───────────────────────────────
#  Session store
# ───────────────────────────────
sessions: Dict[str, Dict[str, Any]] = {}

# ───────────────────────────────
#  OpenAI helper functions
# ───────────────────────────────
# (unchanged – same as before; omitted here for brevity)
# generate_main_menu_with_ai
# generate_submenu_with_ai
# generate_content_and_further_topics_with_ai
# Keep your existing definitions!

# ───────────────────────────────
#  Endpoints
# ───────────────────────────────
@app.get("/")
async def root():
    return {"message": "AI Subject Explorer Backend is alive!"}


@app.post("/sessions", response_model=MenuResponse, status_code=201)
async def create_session(topic_input: TopicInput):
    session_id = str(uuid.uuid4())
    topic = topic_input.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic cannot be empty.")

    menu, max_depth = generate_main_menu_with_ai(topic)

    sessions[session_id] = {
        "topic": topic,
        "history": [("topic", topic)],
        "current_menu": menu,
        "current_depth": 0,
        "max_menu_depth": max_depth,
        "last_content": None,
        "menu_by_depth": {0: menu},
    }

    return MenuResponse(
        type="submenu",
        menu_items=menu,
        content=None,
        session_id=session_id,
        current_depth=0,
        max_menu_depth=max_depth,
    )


@app.post("/menus", response_model=MenuResponse)
async def select_menu_item(sel: MenuSelection):
    if sel.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session ID not found.")

    sd = sessions[sel.session_id]
    selection = sel.selection
    cur_depth = sd["current_depth"]
    next_depth = cur_depth + 1
    max_depth = sd["max_menu_depth"]

    if selection not in sd["current_menu"]:
        raise HTTPException(status_code=400, detail="Invalid selection.")

    topic = sd["topic"]

    if next_depth < max_depth:
        submenu = generate_submenu_with_ai(topic, selection)
        sd["history"].append(("menu_selection", selection))
        sd.update(
            current_menu=submenu,
            current_depth=next_depth,
            last_content=None,
        )
        sd["menu_by_depth"][next_depth] = submenu
        return MenuResponse(
            type="submenu",
            menu_items=submenu,
            content=None,
            session_id=sel.session_id,
            current_depth=next_depth,
            max_menu_depth=max_depth,
        )

    content_md, further = generate_content_and_further_topics_with_ai(
        topic, sd["history"], selection
    )
    sd["history"].append(("menu_selection", selection))
    sd.update(
        current_menu=further,
        current_depth=next_depth,
        last_content=content_md,
    )
    sd["menu_by_depth"][next_depth] = further
    return MenuResponse(
        type="content",
        menu_items=further,
        content=content_md,
        session_id=sel.session_id,
        current_depth=next_depth,
        max_menu_depth=max_depth,
    )


@app.post("/go_back", response_model=MenuResponse)
async def go_back(req: GoBackRequest):
    if req.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session ID not found.")

    sd = sessions[req.session_id]
    if sd["current_depth"] == 0:
        raise HTTPException(status_code=400, detail="Already at top level.")

    prev_depth = sd["current_depth"] - 1
    menu_by_depth = sd["menu_by_depth"]
    if prev_depth not in menu_by_depth:
        raise HTTPException(status_code=500, detail="Previous menu missing.")

    hist = sd["history"]
    if hist and hist[-1][0] == "menu_selection":
        hist.pop()

    sd.update(
        current_depth=prev_depth,
        current_menu=menu_by_depth[prev_depth],
        last_content=None,
        history=hist,
    )

    return MenuResponse(
        type="submenu",
        menu_items=menu_by_depth[prev_depth],
        content=None,
        session_id=req.session_id,
        current_depth=prev_depth,
        max_menu_depth=sd["max_menu_depth"],
    )


# NEW – Return to the original main menu
@app.post("/main_menu", response_model=MenuResponse)
async def return_to_main(req: ReturnToMainRequest):
    if req.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session ID not found.")

    sd = sessions[req.session_id]
    top_menu = sd["menu_by_depth"][0]

    sd.update(
        current_depth=0,
        current_menu=top_menu,
        last_content=None,
        history=[("topic", sd["topic"])],
    )

    return MenuResponse(
        type="submenu",
        menu_items=top_menu,
        content=None,
        session_id=req.session_id,
        current_depth=0,
        max_menu_depth=sd["max_menu_depth"],
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
