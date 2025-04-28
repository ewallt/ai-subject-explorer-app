# *** main.py ***

import os
import uuid
import json
from typing import List, Dict, Any, Tuple, Optional, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai


# ───────────────────────────────
#  Pydantic Models
# ───────────────────────────────

class TopicInput(BaseModel):
    topic: str


class MenuSelection(BaseModel):
    session_id: str
    selection: str


class MenuResponse(BaseModel):
    type: Literal["submenu", "content"]
    menu_items: Optional[List[str]] = None   # submenu items OR further topics
    content: Optional[str] = None            # markdown (when type == "content")
    session_id: str
    current_depth: int
    max_menu_depth: int


# NEW – payload for the /go_back route
class GoBackRequest(BaseModel):
    session_id: str


# ───────────────────────────────
#  Configuration & Initialization
# ───────────────────────────────
load_dotenv()

openai_client = None
try:
    openai_client = openai.OpenAI()
    if not openai_client.api_key:
        print("WARNING: OPENAI_API_KEY not set or empty")
        openai_client = None
    else:
        print("--- OpenAI client initialised ---")
except Exception as e:
    print(f"ERROR creating OpenAI client: {e}")
    openai_client = None


app = FastAPI(title="AI Subject Explorer Backend", version="0.6.0")

origins = [
    "https://ai-subject-explorer-app-frontend.onrender.com",
    # add dev origins like "http://localhost:5173" if needed
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ───────────────────────────────
#  In-memory Session Store
# ───────────────────────────────
# session_id -> {
#   topic, history,
#   current_menu, current_depth, max_menu_depth,
#   last_content,
#   menu_by_depth {depth: menu_items}
# }
sessions: Dict[str, Dict[str, Any]] = {}


# ───────────────────────────────
#  OpenAI helper functions
# ───────────────────────────────
#
#  (All logic unchanged – same as your existing file)
#  generate_main_menu_with_ai
#  generate_submenu_with_ai
#  generate_content_and_further_topics_with_ai
#
#  ↓ KEEP YOUR EXISTING IMPLEMENTATIONS ↓
# ---------------------------------------------------------------------------

# generate_main_menu_with_ai function (Unchanged)
def generate_main_menu_with_ai(topic: str) -> Tuple[List[str], int]:
    """
    Generates main menu categories and determines appropriate max depth.
    Returns (list_of_categories, max_menu_depth).
    """
    if not openai_client:
        print("WARNING: OpenAI client unavailable; returning fallback menu.")
        return ([f"Introduction to {topic}",
                 f"Key Concepts in {topic}",
                 f"History of {topic}"],
                2)

    print(f"--- Calling OpenAI for main menu & depth: '{topic}' ---")
    model_name = "gpt-4.1-nano"

    system_prompt = (
        f"You are an assistant designing a hierarchical exploration menu for "
        f"the main topic '{topic}'.\n\n"
        "Generate a list of 3-7 broad categories for exploring this topic and "
        "choose a logical maximum depth (2-4).\n\n"
        "Return ONLY valid JSON:\n"
        '{ "categories": [...], "max_menu_depth": 3 }'
    )
    user_prompt = f"Generate menu and depth for topic: {topic}"

    try:
        completion = openai_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens=250,
            temperature=0.5,
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content
        parsed = json.loads(content)

        categories = [str(c).strip() for c in parsed["categories"] if str(c).strip()]
        depth = int(parsed["max_menu_depth"])
        if depth < 2 or depth > 4:
            depth = 2
        return categories, depth
    except Exception as e:
        print(f"OpenAI error (main menu): {e}")
        return ([f"Overview of {topic}", f"Details of {topic}"], 2)


# generate_submenu_with_ai function (Unchanged)
def generate_submenu_with_ai(topic: str, category: str) -> List[str]:
    """
    Generates submenu items for a category.
    """
    if not openai_client:
        print("OpenAI unavailable; fallback submenu.")
        return [f"Sub 1 for {category}", f"Sub 2 for {category}"]

    model_name = "gpt-4.1-nano"
    system_prompt = (
        f"You are an assistant creating submenu items for '{topic}' / '{category}'.\n"
        "Return ONLY JSON: { \"subtopics\": [ ... ] } (3-7 items)"
    )
    user_prompt = f"Generate subtopics for {category}"

    try:
        completion = openai_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens=250,
            temperature=0.6,
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content
        parsed = json.loads(content)
        return [str(s).strip() for s in parsed["subtopics"] if str(s).strip()]
    except Exception as e:
        print(f"OpenAI error (submenu): {e}")
        return [f"Sub 1 for {category}", f"Sub 2 for {category}"]


# generate_content_and_further_topics_with_ai function (Unchanged)
def generate_content_and_further_topics_with_ai(
    topic: str,
    history: List[Tuple[str, str]],
    selection: str
) -> Tuple[str, List[str]]:
    """
    Generates markdown content and 3-5 “further exploration” topics.
    """
    if not openai_client:
        print("OpenAI unavailable; fallback content.")
        fallback_md = (
            f"## {selection}\n\n"
            f"(Fallback content for {selection} in {topic}.)"
        )
        return fallback_md, ["Related A", "Related B", "Related C"]

    model_name = "gpt-4.1-nano"
    path = " -> ".join([sel for typ, sel in history if typ == "menu_selection"] + [selection])

    system_prompt = (
        f"You are writing a concise markdown summary for the path '{path}' "
        f"within the main topic '{topic}'. Also suggest 3-5 further topics.\n\n"
        "Return ONLY JSON:\n"
        '{ "content_markdown": "...", "further_topics": ["...", ...] }'
    )
    user_prompt = f"Generate summary and further topics for '{selection}'."

    try:
        completion = openai_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens=500,
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content
        parsed = json.loads(content)
        md = parsed["content_markdown"].strip()
        topics = [str(t).strip() for t in parsed["further_topics"] if str(t).strip()]
        return md, topics
    except Exception as e:
        print(f"OpenAI error (content): {e}")
        fallback_md = f"## {selection}\n\n(Fallback content.)"
        return fallback_md, ["More A", "More B"]


# ───────────────────────────────
#  Endpoints
# ───────────────────────────────

@app.get("/")
async def root():
    return {"message": "AI Subject Explorer Backend is alive!"}


# ----------  /sessions  ------------------------------------------------------
@app.post(
    "/sessions",
    response_model=MenuResponse,
    status_code=201,
    summary="Start a new exploration session",
    tags=["Session Management"],
)
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


# ----------  /menus  ---------------------------------------------------------
@app.post(
    "/menus",
    response_model=MenuResponse,
    status_code=200,
    summary="Process a menu selection",
    tags=["Navigation"],
)
async def select_menu_item(sel: MenuSelection):
    if sel.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session ID not found.")

    sd = sessions[sel.session_id]
    selection = sel.selection
    cur_depth = sd["current_depth"]
    next_depth = cur_depth + 1
    max_depth = sd["max_menu_depth"]

    # Validate selection exists in current menu
    if selection not in sd["current_menu"]:
        raise HTTPException(status_code=400, detail="Invalid selection.")

    topic = sd["topic"]

    # Decide whether to create submenu or content
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

    # next_depth >= max_depth -> generate content
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


# ----------  /go_back  -------------------------------------------------------
@app.post(
    "/go_back",
    response_model=MenuResponse,
    status_code=200,
    summary="Navigate back one level",
    tags=["Navigation"],
)
async def go_back(req: GoBackRequest):
    if req.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session ID not found.")

    sd = sessions[req.session_id]
    cur_depth = sd["current_depth"]
    if cur_depth == 0:
        raise HTTPException(status_code=400, detail="Already at top level.")

    prev_depth = cur_depth - 1
    menu_by_depth: Dict[int, List[str]] = sd["menu_by_depth"]
    if prev_depth not in menu_by_depth:
        raise HTTPException(status_code=500, detail="Previous menu missing.")

    # Trim last history entry if it’s a menu click
    hist = sd["history"]
    if hist and hist[-1][0] == "menu_selection":
        hist.pop()

    # Restore previous menu
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


# ───────────────────────────────
#  Uvicorn runner (local only)
# ───────────────────────────────
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    is_dev = os.environ.get("ENVIRONMENT", "production") == "development"
    print("--- Starting Uvicorn ---")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=is_dev)

# *** End of main.py ***
