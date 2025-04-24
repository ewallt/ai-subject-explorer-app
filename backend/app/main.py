import os
import uuid
import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
from dotenv import load_dotenv
import openai

# --- Pydantic Models ---
# (No changes needed here)
class TopicInput(BaseModel): topic: str
class SessionResponse(BaseModel): session_id: str; menu_items: List[str]
class MenuSelection(BaseModel): session_id: str; selection: str
class MenuResponse(BaseModel): menu_items: List[str]

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
app = FastAPI(title="AI Subject Explorer Backend", version="0.1.0")

# --- CORS Middleware Configuration ---
origins = ["*"] # Restrict in production
app.add_middleware(
    CORSMiddleware, allow_origins=origins, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# --- In-Memory Session Storage ---
sessions: Dict[str, Dict[str, Any]] = {}

# --- AI Call Functions ---
def generate_main_menu_with_ai(topic: str) -> List[str]:
    # (Code from previous step - unchanged)
    if not openai_client: return [f"Introduction to {topic}", f"History of {topic}"] # Fallback
    print(f"--- Calling OpenAI (gpt-4.1-nano) for main menu: '{topic}' ---")
    model_name = "gpt-4.1-nano"
    system_prompt = """You are an assistant designing a hierarchical exploration menu. Given a topic, generate a list of 3 to 7 broad, relevant categories. Return ONLY a valid JSON object containing a single key "categories" which holds a list of strings. Example: {"categories": ["Cat1", "Cat2"]}"""
    user_prompt = f"Topic: {topic}"
    try:
        # ... (rest of the function including API call, parsing, error handling - unchanged) ...
        completion = openai_client.chat.completions.create( model=model_name, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], max_tokens=200, temperature=0.5, response_format={"type": "json_object"} )
        content = completion.choices[0].message.content; print(f"--- OpenAI Raw Main Menu Response: {content} ---")
        if not content: raise ValueError("OpenAI returned empty content.")
        try:
            parsed_data = json.loads(content); menu_items = []
            if isinstance(parsed_data, dict) and "categories" in parsed_data and isinstance(parsed_data["categories"], list): menu_items = [str(item).strip() for item in parsed_data["categories"] if isinstance(item, str) and item.strip()]
            else: raise ValueError("AI main menu response JSON structure incorrect. Expected {'categories': [...]}.")
            if not menu_items: raise ValueError("Parsed main menu JSON, but 'categories' list was empty.")
            print(f"--- Parsed Main Menu Items: {menu_items} ---"); return menu_items
        except json.JSONDecodeError: raise ValueError("AI main menu response was not valid JSON.")
        except Exception as parse_err: raise ValueError(f"Could not process AI main menu response structure: {parse_err}")
    except openai.AuthenticationError as e: raise ConnectionRefusedError(f"OpenAI authentication failed. Check API key. {e}")
    except openai.RateLimitError as e: raise ConnectionAbortedError(f"OpenAI rate limit hit. {e}")
    except openai.APIConnectionError as e: raise ConnectionError(f"Could not connect to OpenAI: {e}")
    except openai.APIError as e: raise RuntimeError(f"OpenAI returned an API error: {e}")
    except Exception as e: raise RuntimeError(f"Unexpected error during AI main menu generation: {e}")

# NEW AI function for submenus (replaces placeholder)
def generate_submenu_with_ai(topic: str, category_selection: str) -> List[str]:
    """ Generates submenu items using OpenAI API based on topic and category. """
    if not openai_client:
        print("ERROR: OpenAI client not available for submenu generation.")
        # Fallback submenu
        return [f"Subtopic 1 for {category_selection}", f"Subtopic 2 for {category_selection}"]

    print(f"--- Calling OpenAI (gpt-4.1-nano) for submenu: Topic='{topic}', Category='{category_selection}' ---")
    model_name = "gpt-4.1-nano"
    system_prompt = f"""You are an assistant designing a hierarchical exploration menu for the main topic '{topic}'.
Given the selected category, generate a list of 3 to 7 specific, relevant subtopics within that category.
Return ONLY a valid JSON object containing a single key "subtopics" which holds a list of strings. Example response:
{{
  "subtopics": ["Subtopic 1", "Subtopic 2", "Subtopic 3"]
}}"""
    user_prompt = f"Selected Category: {category_selection}"

    try:
        completion = openai_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=250, # Maybe slightly more needed for subtopics
            temperature=0.6, # Allow slightly more creativity
            response_format={"type": "json_object"}
        )
        content = completion.choices[0].message.content
        print(f"--- OpenAI Raw Submenu Response: {content} ---")
        if not content: raise ValueError("OpenAI returned empty content for submenu.")
        try:
            parsed_data = json.loads(content)
            submenu_items = []
            if isinstance(parsed_data, dict) and "subtopics" in parsed_data and isinstance(parsed_data["subtopics"], list):
                submenu_items = [str(item).strip() for item in parsed_data["subtopics"] if isinstance(item, str) and item.strip()]
            else: raise ValueError("AI submenu response JSON structure incorrect. Expected {'subtopics': [...]}.")
            if not submenu_items: raise ValueError("Parsed submenu JSON, but 'subtopics' list was empty.")
            print(f"--- Parsed Submenu Items: {submenu_items} ---")
            return submenu_items
        except json.JSONDecodeError: raise ValueError("AI submenu response was not valid JSON.")
        except Exception as parse_err: raise ValueError(f"Could not process AI submenu response structure: {parse_err}")
    # Using same exception mapping as main menu for consistency
    except openai.AuthenticationError as e: raise ConnectionRefusedError(f"OpenAI authentication failed. Check API key. {e}")
    except openai.RateLimitError as e: raise ConnectionAbortedError(f"OpenAI rate limit hit. {e}")
    except openai.APIConnectionError as e: raise ConnectionError(f"Could not connect to OpenAI: {e}")
    except openai.APIError as e: raise RuntimeError(f"OpenAI returned an API error: {e}")
    except Exception as e: raise RuntimeError(f"Unexpected error during AI submenu generation: {e}")

# --- API Endpoints ---
@app.get("/")
async def read_root():
    return {"message": "AI Subject Explorer Backend is alive!"}

@app.post("/sessions", response_model=SessionResponse, status_code=201, summary="Start...", tags=["Session Management"])
async def create_session(topic_input: TopicInput):
    # (Code remains the same - calls generate_main_menu_with_ai)
    session_id = str(uuid.uuid4())
    topic = topic_input.topic; print(f"--- Received POST /sessions request for topic: '{topic}' ---")
    if not openai_client: raise HTTPException(status_code=503, detail={"error": {"code": "AI_SERVICE_UNAVAILABLE", "message": "..."}}) # Simplified
    try:
        main_menu_items = generate_main_menu_with_ai(topic)
        if not main_menu_items: raise ValueError("AI menu generation returned empty/invalid list")
    except (ConnectionRefusedError, ConnectionAbortedError, ConnectionError, RuntimeError, ValueError) as e:
         status_code = 503; error_code = "AI_GENERATION_FAILED" # Defaults
         if isinstance(e, ConnectionRefusedError): status_code, error_code = 401, "AI_AUTH_ERROR"
         elif isinstance(e, ConnectionAbortedError): status_code, error_code = 429, "AI_RATE_LIMIT"
         elif isinstance(e, ConnectionError): status_code, error_code = 504, "AI_CONNECTION_ERROR"
         elif isinstance(e, ValueError): status_code, error_code = 502, "AI_BAD_RESPONSE"
         elif isinstance(e, RuntimeError): status_code, error_code = 502, "AI_API_ERROR"
         print(f"ERROR in /sessions calling AI: {e}"); raise HTTPException(status_code=status_code, detail={"error": {"code": error_code, "message": str(e)}})
    except Exception as e: print(f"ERROR in /sessions unexpected: {e}"); raise HTTPException(status_code=500, detail={"error": {"code": "SESSION_CREATION_FAILED", "message": "..."}}) # Simplified
    sessions[session_id] = {"history": [("topic", topic)], "current_menu": main_menu_items, "topic": topic}
    print(f"--- Session '{session_id}' created successfully using AI. State stored. ---")
    return SessionResponse(session_id=session_id, menu_items=main_menu_items)

@app.post("/menus", response_model=MenuResponse, status_code=200, summary="Process...", tags=["Navigation"])
async def select_menu_item(menu_selection: MenuSelection):
    # *** MODIFIED to call AI for first submenu level ***
    session_id = menu_selection.session_id
    selection = menu_selection.selection
    print(f"--- Received POST /menus request for session '{session_id}', selection: '{selection}' ---")

    # 1. Retrieve session state
    if session_id not in sessions:
        print(f"ERROR in /menus: Session ID '{session_id}' not found.")
        raise HTTPException(status_code=404, detail={"error": {"code": "SESSION_NOT_FOUND", "message": "..."}})
    session_data = sessions[session_id]

    # 2. Validate selection
    current_menu = session_data.get("current_menu", [])
    if selection not in current_menu:
        print(f"ERROR in /menus: Selection '{selection}' not found in current menu: {current_menu}")
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_SELECTION", "message": "..."}})

    # 3. Determine current level & generate next items
    # For now, simple logic: if history only contains the topic, we are generating the first submenu.
    # Otherwise, deeper levels are not yet implemented.
    current_level = len(session_data.get("history", []))
    submenu_items = []

    if current_level == 1: # Only topic in history, so selection is from main menu
        print(f"--- Generating AI submenu (Level 2) for selection: '{selection}' ---")
        if not openai_client: # Check OpenAI client again
             print("ERROR in /menus: OpenAI client not available.")
             raise HTTPException(status_code=503, detail={"error": {"code": "AI_SERVICE_UNAVAILABLE", "message": "..."}})
        try:
            # *** CALL REAL AI SUBMENU FUNCTION ***
            topic = session_data.get("topic", "Unknown Topic")
            submenu_items = generate_submenu_with_ai(topic, selection)
            if not submenu_items:
                raise ValueError("AI submenu generation returned empty or invalid list")
        # Catch specific errors from AI function
        except (ConnectionRefusedError, ConnectionAbortedError, ConnectionError, RuntimeError, ValueError) as e:
             status_code = 503; error_code = "AI_GENERATION_FAILED" # Defaults
             if isinstance(e, ConnectionRefusedError): status_code, error_code = 401, "AI_AUTH_ERROR"
             elif isinstance(e, ConnectionAbortedError): status_code, error_code = 429, "AI_RATE_LIMIT"
             elif isinstance(e, ConnectionError): status_code, error_code = 504, "AI_CONNECTION_ERROR"
             elif isinstance(e, ValueError): status_code, error_code = 502, "AI_BAD_RESPONSE"
             elif isinstance(e, RuntimeError): status_code, error_code = 502, "AI_API_ERROR"
             print(f"ERROR in /menus calling AI for submenu: {e}"); raise HTTPException(status_code=status_code, detail={"error": {"code": error_code, "message": str(e)}})
        except Exception as e: # Catch any other unexpected errors
            print(f"ERROR in /menus unexpected during AI call: {e}"); raise HTTPException(status_code=500, detail={"error": {"code": "SUBMENU_FAILED", "message": "..."}})
    else:
        # If history is deeper than 1, we haven't implemented the next step yet
        print(f"--- Deeper level ({current_level}) navigation not yet implemented. ---")
        # Option 1: Return error
        # raise HTTPException(status_code=501, detail={"error": {"code": "NOT_IMPLEMENTED", "message": "Navigation beyond submenu is not yet implemented."}})
        # Option 2: Return empty list or static message (less disruptive for testing)
        submenu_items = ["Navigation beyond this level not yet implemented."]


    # 4. Update session state ONLY if submenu generation was successful (or placeholder used)
    if submenu_items: # Check if we got items (either AI or placeholder/message)
        session_data["history"].append(("menu_selection", selection))
        session_data["current_menu"] = submenu_items
        sessions[session_id] = session_data
        print(f"--- Session '{session_id}' updated. New menu generated (Level {current_level+1}). ---")
    else:
         # This case should ideally be handled by exceptions, but as fallback:
         print(f"--- Session '{session_id}' not updated as submenu generation failed. ---")
         # Re-raise an error if not already handled? Or return last known good menu?
         # For now, we rely on exceptions above.

    # 5. Return the new menu
    return MenuResponse(menu_items=submenu_items)


# --- Uvicorn runner (for reference) ---
# (Keep existing block)
