import os
import uuid
import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Tuple # Added Optional, Tuple
from dotenv import load_dotenv
import openai

# --- Pydantic Models ---
class TopicInput(BaseModel): topic: str
class SessionResponse(BaseModel): session_id: str; menu_items: List[str] # No change needed here yet
class MenuSelection(BaseModel): session_id: str; selection: str

# UPDATED MenuResponse Model
class MenuResponse(BaseModel):
    type: str # Added: "submenu" or "content"
    menu_items: List[str]
    content_markdown: Optional[str] = None # Added: Make content optional

# --- Configuration & Initialization ---
load_dotenv()
openai_client = None
try:
    openai_client = openai.OpenAI()
    if not openai_client.api_key:
         print("WARNING: OPENAI_API_KEY environment variable not found or empty by OpenAI client.")
         openai_client = None
    else:
         print("--- OpenAI client initialized successfully. testing ---")
except Exception as e:
    print(f"ERROR: Failed to initialize OpenAI client: {e}")
    openai_client = None

# Initialize FastAPI app
app = FastAPI(title="AI Subject Explorer Backend", version="0.1.0")

# --- CORS Middleware Configuration ---
origins = ["*"] # TODO: Restrict in production
app.add_middleware(
    CORSMiddleware, allow_origins=origins, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# --- In-Memory Session Storage ---
sessions: Dict[str, Dict[str, Any]] = {}

# --- AI Call Functions ---

# UPDATED generate_main_menu_with_ai function
def generate_main_menu_with_ai(topic: str) -> Tuple[List[str], int]:
    """
    Generates main menu categories and determines appropriate max depth using OpenAI.
    Returns a tuple: (list_of_categories, max_menu_depth).
    """
    if not openai_client:
        print("WARNING: OpenAI client not available. Returning fallback main menu and depth.")
        # Fallback now also includes a default depth
        return ([f"Introduction to {topic}", f"Key Concepts in {topic}", f"History of {topic}"], 2) # Return tuple

    print(f"--- Calling OpenAI (gpt-4.1-nano) for main menu & depth: '{topic}' ---")
    model_name = "gpt-4.1-nano"

    # Two-part prompt structure
    content_instruction = f"""You are an assistant designing a hierarchical exploration menu for the main topic '{topic}'.
Generate a list of 3 to 7 broad, relevant main categories for exploring this topic.
Also, determine a logical maximum depth (integer) for menu exploration for this topic before showing detailed content.
For testing purposes, constrain the maximum depth you return: for the topic '{topic}', please ALWAYS return a max_menu_depth of 2."""

    json_format_instruction = """Return ONLY a valid JSON object containing two keys:
1.  "categories": A list of strings representing the main menu categories.
2.  "max_menu_depth": An integer representing the determined maximum depth (which must be 2 for now).

Example response:
{
  "categories": ["Overview", "History", "Key Aspects", "Future Trends"],
  "max_menu_depth": 2
}"""

    system_prompt = f"{content_instruction}\n\n{json_format_instruction}"
    user_prompt = f"Generate menu and depth for topic: {topic}" # Simple user prompt might suffice

    try:
        completion = openai_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=250, # Increased slightly to accommodate depth
            temperature=0.5,
            response_format={"type": "json_object"}
        )
        content = completion.choices[0].message.content
        print(f"--- OpenAI Raw Main Menu/Depth Response: {content} ---")
        if not content:
            raise ValueError("OpenAI returned empty content.")

        try:
            parsed_data = json.loads(content)
            menu_items = []
            max_depth = -1 # Initialize with invalid value

            # Validate and parse "categories"
            if isinstance(parsed_data, dict) and "categories" in parsed_data and isinstance(parsed_data["categories"], list):
                menu_items = [str(item).strip() for item in parsed_data["categories"] if isinstance(item, str) and item.strip()]
                if not menu_items:
                     raise ValueError("Parsed JSON ok, but 'categories' list was empty or contained only non-strings/whitespace.")
            else:
                raise ValueError("AI response JSON structure incorrect or missing 'categories' list.")

            # Validate and parse "max_menu_depth"
            if isinstance(parsed_data, dict) and "max_menu_depth" in parsed_data and isinstance(parsed_data["max_menu_depth"], int):
                 max_depth = parsed_data["max_menu_depth"]
                 # Optional: Add check if max_depth is reasonable (e.g., > 0) if needed later
                 if max_depth != 2: # Strict check for initial testing constraint
                      print(f"WARNING: AI returned max_menu_depth={max_depth}, but was constrained to return 2. Using 2.")
                      max_depth = 2
            else:
                 # If AI failed to return the depth correctly despite prompt, fallback needed
                 print(f"WARNING: AI response JSON structure incorrect or missing valid 'max_menu_depth' integer. Defaulting to 2.")
                 # raise ValueError("AI response JSON structure incorrect or missing 'max_menu_depth' integer.") # Option: Raise error
                 max_depth = 2 # Option: Use default fallback

            print(f"--- Parsed Main Menu Items: {menu_items} ---")
            print(f"--- Parsed Max Menu Depth: {max_depth} ---")
            return (menu_items, max_depth) # Return tuple

        except json.JSONDecodeError:
            raise ValueError("AI main menu/depth response was not valid JSON.")
        except ValueError as ve: # Catch specific parsing errors
             raise ve # Re-raise the specific error
        except Exception as parse_err:
            # Catch any other unexpected parsing issues
            raise ValueError(f"Could not process AI main menu/depth response structure: {parse_err}")

    # Keep existing OpenAI API error handling
    except openai.AuthenticationError as e: raise ConnectionRefusedError(f"OpenAI authentication failed. Check API key. {e}")
    except openai.RateLimitError as e: raise ConnectionAbortedError(f"OpenAI rate limit hit. {e}")
    except openai.APIConnectionError as e: raise ConnectionError(f"Could not connect to OpenAI: {e}")
    except openai.APIError as e: raise RuntimeError(f"OpenAI returned an API error: {e}")
    except Exception as e: raise RuntimeError(f"Unexpected error during AI main menu/depth generation: {e}")


# generate_submenu_with_ai function (No changes in this step)
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

# UPDATED /sessions endpoint
@app.post("/sessions", response_model=SessionResponse, status_code=201, summary="Start a new exploration session", tags=["Session Management"])
async def create_session(topic_input: TopicInput):
    session_id = str(uuid.uuid4())
    topic = topic_input.topic
    print(f"--- Received POST /sessions request for topic: '{topic}' ---")

    if not openai_client:
        raise HTTPException(status_code=503, detail={"error": {"code": "AI_SERVICE_UNAVAILABLE", "message": "OpenAI client is not initialized. Check backend logs and API key."}})

    try:
        # Call updated function - now returns a tuple
        main_menu_items, max_menu_depth = generate_main_menu_with_ai(topic)

        if not main_menu_items: # Should be redundant if AI func raises error, but good practice
            raise ValueError("AI menu generation returned empty/invalid list")

    except (ConnectionRefusedError, ConnectionAbortedError, ConnectionError, RuntimeError, ValueError) as e:
        status_code = 503; error_code = "AI_GENERATION_FAILED" # Defaults
        if isinstance(e, ConnectionRefusedError): status_code, error_code = 401, "AI_AUTH_ERROR"
        elif isinstance(e, ConnectionAbortedError): status_code, error_code = 429, "AI_RATE_LIMIT"
        elif isinstance(e, ConnectionError): status_code, error_code = 504, "AI_CONNECTION_ERROR"
        elif isinstance(e, ValueError): status_code, error_code = 502, "AI_BAD_RESPONSE" # Catches JSON/parsing/validation errors from AI func
        elif isinstance(e, RuntimeError): status_code, error_code = 502, "AI_API_ERROR" # Catches other OpenAI API errors
        print(f"ERROR in /sessions calling AI: {e}")
        raise HTTPException(status_code=status_code, detail={"error": {"code": error_code, "message": str(e)}})
    except Exception as e:
        print(f"ERROR in /sessions unexpected: {e}")
        raise HTTPException(status_code=500, detail={"error": {"code": "SESSION_CREATION_FAILED", "message": "An unexpected error occurred creating the session."}})

    # Store session state, now including max_menu_depth
    sessions[session_id] = {
        "topic": topic,
        "history": [("topic", topic)], # History tracks user path
        "current_menu": main_menu_items,
        "max_menu_depth": max_menu_depth # Store the depth determined by AI
    }
    print(f"--- Session '{session_id}' created. Max depth={max_menu_depth}. State stored. ---")

    # Return only session_id and initial menu items to frontend
    return SessionResponse(session_id=session_id, menu_items=main_menu_items)


# /menus endpoint (No changes in this step - will be updated next)
@app.post("/menus", response_model=MenuResponse, status_code=200, summary="Process menu selection and get next items", tags=["Navigation"])
async def select_menu_item(menu_selection: MenuSelection):
    # *** THIS FUNCTION WILL BE MODIFIED IN THE NEXT STEP ***
    # *** It does NOT YET use max_menu_depth or the new MenuResponse structure ***
    session_id = menu_selection.session_id
    selection = menu_selection.selection
    print(f"--- Received POST /menus request for session '{session_id}', selection: '{selection}' ---")

    # 1. Retrieve session state
    if session_id not in sessions:
        print(f"ERROR in /menus: Session ID '{session_id}' not found.")
        raise HTTPException(status_code=404, detail={"error": {"code": "SESSION_NOT_FOUND", "message": "Session ID not found. It might have expired or is invalid."}})
    session_data = sessions[session_id]

    # 2. Validate selection
    current_menu = session_data.get("current_menu", [])
    if selection not in current_menu:
        print(f"ERROR in /menus: Selection '{selection}' not found in current menu: {current_menu}")
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_SELECTION", "message": f"Selection '{selection}' is not a valid option in the current menu."}})

    # 3. Determine current level & generate next items (OLD LOGIC - ignores max_depth)
    current_level = len(session_data.get("history", []))
    submenu_items = []

    if current_level == 1: # Only topic in history, so selection is from main menu
        print(f"--- Generating AI submenu (Level 2) for selection: '{selection}' ---")
        if not openai_client: # Check OpenAI client again
            print("ERROR in /menus: OpenAI client not available.")
            raise HTTPException(status_code=503, detail={"error": {"code": "AI_SERVICE_UNAVAILABLE", "message": "OpenAI client is not available to generate submenu."}})
        try:
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
            print(f"ERROR in /menus unexpected during AI call: {e}"); raise HTTPException(status_code=500, detail={"error": {"code": "SUBMENU_FAILED", "message": "An unexpected error occurred generating the submenu."}})
    else:
        # If history is deeper than 1, we haven't implemented the next step yet
        print(f"--- Deeper level ({current_level}) navigation not yet implemented. ---")
        # Placeholder response (will be changed)
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


    # 5. Return the new menu (USING OLD RESPONSE MODEL - will be changed)
    # This line needs to be updated in the next step to use the new MenuResponse model
    return MenuResponse(type="submenu", menu_items=submenu_items, content_markdown=None) # TEMPORARY usage of new model


# --- Uvicorn runner (for local development reference) ---
if __name__ == "__main__":
    import uvicorn
    print("--- Starting Uvicorn server (likely for local testing) ---")
    # Load port from environment variable or default to 8000
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
