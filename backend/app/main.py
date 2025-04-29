# *** main.py ***

import os
import uuid
import json
from typing import List, Dict, Any, Tuple, Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import openai

# ──────────────────────────────────────────────────────────────
# Pydantic models
# ──────────────────────────────────────────────────────────────
class TopicInput(BaseModel):
    topic: str


class MenuSelection(BaseModel):
    session_id: str
    selection: str


class SessionRequest(BaseModel):        # for /main_menu and /go_back
    session_id: str


class MenuResponse(BaseModel):
    type: Literal["submenu", "content"]
    menu_items: Optional[List[str]] = None
    content: Optional[str] = None
    session_id: str
    current_depth: int
    max_menu_depth: int


# ──────────────────────────────────────────────────────────────
# Initialisation
# ──────────────────────────────────────────────────────────────
load_dotenv()
openai_client = None
try:
    openai_client = openai.OpenAI()
    if not openai_client.api_key:
        print("WARNING: OPENAI_API_KEY env var missing or blank.")
        openai_client = None
    else:
        print("✓ OpenAI client initialised.")
except Exception as e:
    print(f"ERROR initialising OpenAI client: {e}")
    openai_client = None

app = FastAPI(title="AI Subject Explorer Backend", version="0.6.2")

origins = [
    "https://ai-subject-explorer-app-frontend.onrender.com",
    "https://ai-subject-explorer-app-frontend.onrender.com/",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────────────────────
# In-memory sessions
# ──────────────────────────────────────────────────────────────
sessions: Dict[str, Dict[str, Any]] = {}

# ──────────────────────────────────────────────────────────────
# OpenAI helper functions (unchanged)
# ──────────────────────────────────────────────────────────────
def generate_main_menu_with_ai(topic: str) -> Tuple[List[str], int]:
    if not openai_client:
        return (
            [f"Introduction to {topic}", f"Key Concepts in {topic}", f"History of {topic}"],
            2,
        )

    model_name = "gpt-4.1-nano"
    content_instruction = (
        f"You are an assistant designing a hierarchical exploration menu for '{topic}'. "
        "Generate 3–7 broad categories and choose an appropriate maximum depth (2-4)."
    )
    json_instruction = (
        "Return ONLY JSON with keys 'categories' (list) and 'max_menu_depth' (int)."
    )

    completion = openai_client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": content_instruction},
            {"role": "user", "content": json_instruction},
        ],
        max_tokens=250,
        temperature=0.5,
        response_format={"type": "json_object"},
    )
    parsed = json.loads(completion.choices[0].message.content)
    menu_items = [str(i).strip() for i in parsed["categories"] if str(i).strip()]
    max_depth = int(parsed["max_menu_depth"])
    if max_depth < 2 or max_depth > 4:
        max_depth = 2
    return menu_items, max_depth


def generate_submenu_with_ai(topic: str, category: str) -> List[str]:
    if not openai_client:
        return [f"Subtopic 1 of {category}", f"Subtopic 2 of {category}"]

    model_name = "gpt-4.1-nano"
    sys_msg = (
        f"Generate 3-7 subtopics inside '{category}' (main topic '{topic}'). "
        "Return ONLY JSON {'subtopics':[...]}."
    )
    completion = openai_client.chat.completions.create(
        model=model_name,
        messages=[{"role": "system", "content": sys_msg}],
        max_tokens=250,
        temperature=0.6,
        response_format={"type": "json_object"},
    )
    parsed = json.loads(completion.choices[0].message.content)
    return [str(i).strip() for i in parsed["subtopics"] if str(i).strip()]


def generate_content_and_further_topics_with_ai(
    topic: str, history: List[Tuple[str, str]], selection: str
) -> Tuple[str, List[str]]:
    if not openai_client:
        fallback_md = (
            f"## {selection}\n\n*(fallback – OpenAI unavailable)*\n\n"
            f"Details about **{selection}** within **{topic}**."
        )
        return fallback_md, ["Related Topic A", "Related Topic B", "Go Deeper"]

    path_list = [h[1] for h in history if h[0] == "menu_selection"] + [selection]
    nav_path = " -> ".join([topic] + path_list)
    model_name = "gpt-4.1-nano"
    sys_msg = (
        "Generate a 2-4 paragraph markdown summary and 3-5 further-topic suggestions.\n"
        f"User navigation path: {nav_path}\n"
        "Return ONLY JSON {content_markdown:str, further_topics:list}."
    )
    completion = openai_client.chat.completions.create(
        model=model_name,
        messages=[{"role": "system", "content": sys_msg}],
        max_tokens=500,
        temperature=0.7,
        response_format={"type": "json_object"},
    )
    parsed = json.loads(completion.choices[0].message.content)
    md = str(parsed["content_markdown"]).strip()
    ft = [str(i).strip() for i in parsed["further_topics"] if str(i).strip()]
    return md, ft


# ──────────────────────────────────────────────────────────────
# API endpoints
# ──────────────────────────────────────────────────────────────
@app.get("/")
async def read_root():
    return {
        "message": "AI Subject Explorer Backend is alive!",
        "version": app.version,
        "openai_ready": openai_client is not None,
        "active_sessions": len(sessions),
    }


@app.post("/sessions", response_model=MenuResponse, status_code=201)
async def create_session(topic_input: TopicInput):
    topic = topic_input.topic
    session_id = str(uuid.uuid4())
    main_menu, max_depth = generate_main_menu_with_ai(topic)

    sessions[session_id] = {
        "topic": topic,
        "history": [("topic", topic)],
        "current_menu": main_menu,
        "max_menu_depth": max_depth,
        "current_depth": 0,
        "last_content": None,
        "menu_by_depth": {0: main_menu},
    }

    return MenuResponse(
        type="submenu",
        menu_items=main_menu,
        content=None,
        session_id=session_id,
        current_depth=0,
        max_menu_depth=max_depth,
    )


@app.post("/menus", response_model=MenuResponse, status_code=200)
async def select_menu_item(menu_selection: MenuSelection):
    session_id = menu_selection.session_id
    selection = menu_selection.selection
    if session_id not in sessions:
        raise HTTPException(404, "Session ID not found.")

    s = sessions[session_id]
    topic = s["topic"]
    curr_depth = s["current_depth"]
    max_depth = s["max_menu_depth"]
    next_depth = curr_depth + 1

    if selection not in s["current_menu"]:
        raise HTTPException(400, f"Selection '{selection}' not in current menu.")

    # Sub-menu mode
    if next_depth < max_depth:
        submenu = generate_submenu_with_ai(topic, selection)
        s["history"].append(("menu_selection", selection))
        s["current_menu"] = submenu
        s["current_depth"] = next_depth
        s["last_content"] = None
        s["menu_by_depth"][next_depth] = submenu
        sessions[session_id] = s
        return MenuResponse(
            type="submenu",
            menu_items=submenu,
            content=None,
            session_id=session_id,
            current_depth=next_depth,
            max_menu_depth=max_depth,
        )

    # Content mode
    md, further = generate_content_and_further_topics_with_ai(
        topic, s["history"], selection
    )
    s["history"].append(("menu_selection", selection))
    s["current_menu"] = further
    s["current_depth"] = next_depth
    s["last_content"] = md
    s["menu_by_depth"][next_depth] = further
    sessions[session_id] = s
    return MenuResponse(
        type="content",
        menu_items=further,
        content=md,
        session_id=session_id,
        current_depth=next_depth,
        max_menu_depth=max_depth,
    )


@app.post("/main_menu", response_model=MenuResponse, status_code=200)
async def return_to_main_menu(req: SessionRequest):
    session_id = req.session_id
    if session_id not in sessions:
        raise HTTPException(404, "Session ID not found.")

    s = sessions[session_id]
    root_menu = s["menu_by_depth"].get(0, s["current_menu"])
    s["current_menu"] = root_menu
    s["current_depth"] = 0
    s["last_content"] = None
    s["history"] = [h for h in s["history"] if h[0] == "topic"]
    sessions[session_id] = s

    return MenuResponse(
        type="submenu",
        menu_items=root_menu,
        content=None,
        session_id=session_id,
        current_depth=0,
        max_menu_depth=s["max_menu_depth"],
    )


# ─────────── NEW /go_back endpoint ───────────
@app.post("/go_back", response_model=MenuResponse, status_code=200)
async def go_back_one_level(req: SessionRequest):
    """
    Step back one depth level. Returns the previous menu.
    If already at depth 0, returns the same root menu.
    """
    session_id = req.session_id
    if session_id not in sessions:
        raise HTTPException(404, "Session ID not found.")

    s = sessions[session_id]
    current_depth = s["current_depth"]

    if current_depth == 0:
        # Already at root – just echo the root menu
        root_menu = s["menu_by_depth"][0]
        return MenuResponse(
            type="submenu",
            menu_items=root_menu,
            content=None,
            session_id=session_id,
            current_depth=0,
            max_menu_depth=s["max_menu_depth"],
        )

    prev_depth = current_depth - 1
    prev_menu = s["menu_by_depth"][prev_depth]

    # Trim history and reset state
    if s["history"] and s["history"][-1][0] == "menu_selection":
        s["history"].pop()  # remove last selection
    s["current_menu"] = prev_menu
    s["current_depth"] = prev_depth
    s["last_content"] = None
    sessions[session_id] = s

    return MenuResponse(
        type="submenu",
        menu_items=prev_menu,
        content=None,
        session_id=session_id,
        current_depth=prev_depth,
        max_menu_depth=s["max_menu_depth"],
    )


# ──────────────────────────────────────────────────────────────
# Uvicorn runner (local dev only)
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.environ.get("ENVIRONMENT", "") == "development",
    )

# *** End of main.py ***
