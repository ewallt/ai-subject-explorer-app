import os
import uuid
import json
from fastapi import FastAPI, HTTPException, Request # Added Request just in case
from fastapi.middleware.cors import CORSMiddleware # <-- Import CORS
from pydantic import BaseModel
from typing import List, Dict, Any
from dotenv import load_dotenv
import openai

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

# --- Configuration & Initialization ---
load_dotenv()

openai_client = None
try:
    openai_client = openai.OpenAI()
    if not openai_client.api_key:
         print("WARNING: OPENAI_API_KEY environment variable not found or empty by OpenAI client.")
         openai_client = None
    else:
        print("--- OpenAI client initialized successfully. ---")
except Exception as e:
    print(f"ERROR: Failed to initialize OpenAI client: {e}")
    openai_client = None

# Initialize FastAPI app
app = FastAPI(
    title="AI Subject Explorer Backend",
    description="API for the AI Subject Explorer.",
    version="0.1.0",
)

# --- CORS Middleware Configuration --- <<< ADDED THIS BLOCK
# Define allowed origins
# IMPORTANT: For production, replace "*" with your specific frontend URL
# e.g., "https://ai-subject-explorer-app-frontend.onrender.com"
origins = [
    "*", # Allows all origins - simple for testing, less secure for prod
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],    # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],    # Allows all headers
)
# --- End CORS Middleware ---


# --- In-Memory Session Storage ---
sessions: Dict[str, Dict[str, Any]] = {}

# --- AI Call Functions ---
def generate_main_menu_with_ai(topic: str) -> List[str]:
    """ Generates the main menu using OpenAI API, expecting JSON list output. """
    if not openai_client:
        print("ERROR: OpenAI client not available. Returning fallback menu.")
        return [f"Introduction to {topic}", f"History of {topic}"] # Fallback

    print(f"--- Calling OpenAI (gpt-4.1-nano) to generate main menu for topic: '{topic}' ---")
    model_name = "gpt-4.1-nano"
    system_prompt = """You are an assistant designing a hierarchical exploration menu.
Given a topic, generate a list of 3 to 7 broad, relevant categories for exploration.
Return ONLY a valid JSON object containing a single key "categories" which holds a list of strings. Example response:
{
  "categories": ["Category 1", "Category 2", "Category 3"]
}"""
    user_prompt = f"Topic: {topic}"
    try:
        completion = openai_client.chat.completions.create(
            model=model_name, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            max_tokens=200, temperature=0.5, response_format={"type": "json_object"}
        )
        content = completion.choices[0].message.content
        print(f"--- OpenAI Raw Response Content: {content} ---")
        if not content: raise ValueError("OpenAI returned empty content.")
        try:
            parsed_data = json.loads(content)
            menu_items = []
            if isinstance(parsed_data, dict) and "categories" in parsed_data and isinstance(parsed_data["categories"], list):
                 menu_items = [str(item).strip() for item in parsed_data["categories"] if isinstance(item, str) and item.strip()]
            else: raise ValueError("AI response JSON structure incorrect. Expected {'categories': [...]}.")
            if not menu_items: raise ValueError("Parsed JSON, but 'categories' list was empty or invalid.")
            print(f"--- Parsed Menu Items: {menu_items} ---")
            return menu_items
        except json.JSONDecodeError: raise ValueError("AI response was not valid JSON.")
        except Exception as parse_err: raise ValueError(f"Could not process AI response structure: {parse_err}")
    except openai.AuthenticationError as e: raise ConnectionRefusedError(f"OpenAI authentication failed. Check API key. {e}")
    except openai.RateLimitError as e: raise ConnectionAbortedError(f"OpenAI rate limit hit. Please try again later. {e}")
    except openai.APIConnectionError as e: raise ConnectionError(f"Could not connect to OpenAI: {e}")
    except openai.APIError as e: raise RuntimeError(f"OpenAI returned an API error: {e}")
    except Exception as e: raise RuntimeError(f"An unexpected error occurred with AI generation: {e}")

def get_submenu_placeholder(session_data: Dict[str, Any], selection: str) -> List[str]:
    """ Placeholder function to generate a submenu based on selection. """
    print(f"--- MOCK BACKEND: Generating submenu for selection: '{selection}' (Using Placeholder) ---")
    topic = session_data.get("topic", "Unknown Topic")
    if "history" in selection.lower(): return [f"Early {topic} History", f"Mid-Century {topic}", f"Recent {topic}"]
    elif "introduction" in selection.lower(): return [f"Core Concept A for {topic}", f"Core Concept B", f"Related Terms for {topic}"]
    elif "applications" in selection.lower(): return [f"Use Case 1 ({topic})", f"Use Case 2", f"Industry Examples ({topic})"]
    else: return [f"Sub-Item 1 for {selection}", f"Sub-Item 2 ({topic})", f"Sub-Item 3"]

# --- API Endpoints ---
@app.get("/")
async def read_root():
    return {"message": "AI Subject Explorer Backend is alive!"}

@app.post("/sessions", response_model=SessionResponse, status_code=201, summary="Start...", tags=["Session Management"])
async def create_session(topic_input: TopicInput):
    session_id = str(uuid.uuid4())
    topic = topic_input.topic
    print(f"--- Received POST /sessions request for topic: '{topic}' ---")
    if not openai_client:
         print("ERROR in /sessions: OpenAI client not available.")
         raise HTTPException(status_code=503, detail={"error": {"code": "AI_SERVICE_UNAVAILABLE", "message": "OpenAI client not configured or key missing."}})
    try:
        main_menu_items = generate_main_menu_with_ai(topic)
        if not main_menu_items: raise ValueError("AI menu generation returned empty or invalid list")
    except (ConnectionRefusedError, ConnectionAbortedError, ConnectionError, RuntimeError, ValueError) as e:
         status_code = 503; error_code = "AI_GENERATION_FAILED"
         if isinstance(e, ConnectionRefusedError): status_code, error_code = 401, "AI_AUTH_ERROR"
         elif isinstance(e, ConnectionAbortedError): status_code, error_code = 429, "AI_RATE_LIMIT"
         elif isinstance(e, ConnectionError): status_code, error_code = 504, "AI_CONNECTION_ERROR"
         elif isinstance(e, ValueError): status_code, error_code = 502, "AI_BAD_RESPONSE"
         elif isinstance(e, RuntimeError): status_code, error_code = 502, "AI_API_ERROR"
         print(f"ERROR in /sessions calling AI: {e}")
         raise HTTPException(status_code=status_code, detail={"error": {"code": error_code, "message": str(e)}})
    except Exception as e:
        print(f"ERROR in /sessions unexpected: {e}")
        raise HTTPException(status_code=500, detail={"error": {"code": "SESSION_CREATION_FAILED", "message": "An unexpected error occurred."}})
    sessions[session_id] = {"history": [("topic", topic)], "current_menu": main_menu_items, "topic": topic}
    print(f"--- Session '{session_id}' created successfully using AI. State stored. ---")
    return SessionResponse(session_id=session_id, menu_items=main_menu_items)

@app.post("/menus", response_model=MenuResponse, status_code=200, summary="Process...", tags=["Navigation"])
async def select_menu_item(menu_selection: MenuSelection):
    # (Code remains the same - still uses placeholder)
    session_id = menu_selection.session_id
    selection = menu_selection.selection
    print(f"--- Received POST /menus request for session '{session_id}', selection: '{selection}' ---")
    if session_id not in sessions:
        print(f"ERROR in /menus: Session ID '{session_id}' not found.")
        raise HTTPException( status_code=404, detail={"error": {"code": "SESSION_NOT_FOUND", "message": "Session ID not found or expired"}} )
    session_data = sessions[session_id]
    current_menu = session_data.get("current_menu", [])
    if selection not in current_menu:
        print(f"ERROR in /menus: Selection '{selection}' not found in current menu for session '{session_id}'. Current menu: {current_menu}")
        raise HTTPException( status_code=400, detail={"error": {"code": "INVALID_SELECTION", "message": f"Selection '{selection}' is not a valid option in the current menu."}} )
    try:
        submenu_items = get_submenu_placeholder(session_data, selection)
        if not submenu_items: raise ValueError("Placeholder submenu generation returned empty list")
    except Exception as e:
        print(f"ERROR in /menus generating placeholder submenu: {e}")
        raise HTTPException( status_code=500, detail={"error": {"code": "SUBMENU_GENERATION_FAILED", "message": str(e)}} )
    session_data["history"].append(("menu_selection", selection))
    session_data["current_menu"] = submenu_items
    sessions[session_id] = session_data
    print(f"--- Session '{session_id}' updated. Placeholder submenu generated. ---")
    return MenuResponse(menu_items=submenu_items)

# --- Uvicorn runner (for reference) ---
# (Keep existing block)
# if __name__ == "__main__":
# ...
