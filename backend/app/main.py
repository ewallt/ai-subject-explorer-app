# *** main.py ***

import os
import uuid
import json
from typing import List, Dict, Any, Optional, Tuple, Literal

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


# NEW – simple body for endpoints that need only the session ID
class SessionRequest(BaseModel):
    session_id: str


class MenuResponse(BaseModel):
    type: Literal["submenu", "content"]
    menu_items: Optional[List[str]] = None   # submenu or further-topics list
    content: Optional[str] = None            # markdown (when type == "content")
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

app = FastAPI(title="AI Subject Explorer Backend", version="0.6.1")

# CORS – keep frontend origin plus localhost for dev
origins = [
    "https://ai-subject-explorer-app-frontend.onrender.com",
    "https://ai-subject-explorer-app-frontend.onrender.com/",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # tighten later if you like
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────────────────────
# In-memory session store
# ──────────────────────────────────────────────────────────────
# session_id → {
#   topic, history, current_menu, max_menu_depth, current_depth,
#   last_content, menu_by_depth
# }
sessions: Dict[str, Dict[str, Any]] = {}

# ──────────────────────────────────────────────────────────────
# OpenAI helper functions  (unchanged from v0.5.0)
# ──────────────────────────────────────────────────────────────
def generate_main_menu_with_ai(topic: str) -> Tuple[List[str], int]:
    """
    Returns (main_menu_items, max_menu_depth).
    """
    if not openai_client:
        print("WARNING: OpenAI unavailable. Returning fallback main menu.")
        return (
            [
                f"Introduction to {topic}",
                f"Key Concepts in {topic}",
                f"History of {topic}",
            ],
            2,
        )

    print(f"→ OpenAI (main menu) for topic '{topic}'")
    model_name = "gpt-4.1-nano"
    content_instruction = (
        f"You are an assistant designing a hierarchical exploration menu for '{topic}'. "
        "Generate 3–7 broad categories and pick an appropriate maximum depth (2-4)."
    )
    json_instruction = (
        "Return ONLY JSON with keys 'categories' (list) and 'max_menu_depth' (int)."
    )

    try:
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
            max_depth = 
