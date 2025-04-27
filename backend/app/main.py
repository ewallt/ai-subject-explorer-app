import os
import uuid
import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field # Added Field
from typing import List, Dict, Any, Optional, Tuple, Literal # Added Optional, Tuple, Literal
from dotenv import load_dotenv
import openai

# --- Pydantic Models ---

class TopicInput(BaseModel):
    topic: str

# Removed old SessionResponse model as /sessions now returns MenuResponse

class MenuSelection(BaseModel):
    session_id: str
    selection: str

# --- NEW/REVISED MenuResponse Model (incorporates SessionResponse info and depth) ---
# Sticking with List[str] for menu_items for now to match existing code style.
class MenuResponse(BaseModel):
    type: Literal["submenu", "content"]
    menu_items: Optional[List[str]] = None # Items for submenu, or further exploration topics for content
    content: Optional[str] = None # Markdown content (only when type is "content")
    session_id: str # Always include session_id
    current_depth: int # Depth of the *current* response (0 for initial menu, 1 for first submenu/content, etc.)
    max_menu_depth: int # Max depth allowed for this session

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
        # print("--- BACKEND CODE VERSION: DYNAMIC_DEPTH_V3 ---") # Example marker
except Exception as e:
    print(f"ERROR: Failed to initialize OpenAI client: {e}")
    openai_client = None

# Initialize FastAPI app
app = FastAPI(title="AI Subject Explorer Backend", version="0.2.0") # Version bump

# --- CORS Middleware Configuration ---
origins = ["*"] # TODO: Restrict in production
app.add_middleware(
    CORSMiddleware, allow_origins=origins, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# --- In-Memory Session Storage ---
# Structure: session_id -> { topic, history, current_menu, max_menu_depth, current_depth }
sessions: Dict[str, Dict[str, Any]] = {}

# --- AI Call Functions ---

# generate_main_menu_with_ai function (Seems mostly OK, returns tuple (menu_items, max_depth))
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
A depth of 1 means content is shown after the first click. A depth of 2 means content is shown after the second click, etc.
The depth should generally be between 2 and 4 depending on topic breadth.
For testing purposes, constrain the maximum depth you return: for the topic '{topic}', please ALWAYS return a max_menu_depth of 2.""" # Kept constraint for now

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
            max_tokens=250,
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
                 if max_depth != 2: # Strict check for initial testing constraint
                     print(f"WARNING: AI returned max_menu_depth={max_depth}, but was constrained to return 2. Using 2.")
                     max_depth = 2
            else:
                 print(f"WARNING: AI response JSON structure incorrect or missing valid 'max_menu_depth' integer. Defaulting to 2.")
                 max_depth = 2 # Use default fallback

            print(f"--- Parsed Main Menu Items: {menu_items} ---")
            print(f"--- Parsed Max Menu Depth: {max_depth} ---")
            return (menu_items, max_depth) # Return tuple

        except json.JSONDecodeError:
            raise ValueError("AI main menu/depth response was not valid JSON.")
        except ValueError as ve:
             raise ve
        except Exception as parse_err:
            raise ValueError(f"Could not process AI main menu/depth response structure: {parse_err}")

    except openai.AuthenticationError as e: raise ConnectionRefusedError(f"OpenAI authentication failed. Check API key. {e}")
    except openai.RateLimitError as e: raise ConnectionAbortedError(f"OpenAI rate limit hit. {e}")
    except openai.APIConnectionError as e: raise ConnectionError(f"Could not connect to OpenAI: {e}")
    except openai.APIError as e: raise RuntimeError(f"OpenAI returned an API error: {e}")
    except Exception as e: raise RuntimeError(f"Unexpected error during AI main menu/depth generation: {e}")


# generate_submenu_with_ai function (Unchanged - generates List[str])
def generate_submenu_with_ai(topic: str, category_selection: str) -> List[str]:
    """ Generates submenu items using OpenAI API based on topic and category. """
    if not openai_client:
        print("ERROR: OpenAI client not available for submenu generation.")
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
            max_tokens=250,
            temperature=0.6,
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
    except openai.AuthenticationError as e: raise ConnectionRefusedError(f"OpenAI authentication failed. Check API key. {e}")
    except openai.RateLimitError as e: raise ConnectionAbortedError(f"OpenAI rate limit hit. {e}")
    except openai.APIConnectionError as e: raise ConnectionError(f"Could not connect to OpenAI: {e}")
    except openai.APIError as e: raise RuntimeError(f"OpenAI returned an API error: {e}")
    except Exception as e: raise RuntimeError(f"Unexpected error during AI submenu generation: {e}")


# --- API Endpoints ---
# Endpoint order: / , /sessions, /menus

@app.get("/")
async def read_root():
    return {"message": "AI Subject Explorer Backend is alive!"}

# --- UPDATED /sessions endpoint ---
@app.post("/sessions", response_model=MenuResponse, status_code=201, summary="Start a new exploration session", tags=["Session Management"])
async def create_session(topic_input: TopicInput):
    session_id = str(uuid.uuid4())
    topic = topic_input.topic
    print(f"--- Received POST /sessions request for topic: '{topic}' ---")

    if not openai_client:
        raise HTTPException(status_code=503, detail={"error": {"code": "AI_SERVICE_UNAVAILABLE", "message": "OpenAI client is not initialized. Check backend logs and API key."}})

    try:
        main_menu_items, max_menu_depth = generate_main_menu_with_ai(topic)
        if not main_menu_items:
            raise ValueError("AI menu generation returned empty/invalid list")

    except (ConnectionRefusedError, ConnectionAbortedError, ConnectionError, RuntimeError, ValueError) as e:
        status_code = 503; error_code = "AI_GENERATION_FAILED"
        if isinstance(e, ConnectionRefusedError): status_code, error_code = 401, "AI_AUTH_ERROR"
        elif isinstance(e, ConnectionAbortedError): status_code, error_code = 429, "AI_RATE_LIMIT"
        elif isinstance(e, ConnectionError): status_code, error_code = 504, "AI_CONNECTION_ERROR"
        elif isinstance(e, ValueError): status_code, error_code = 502, "AI_BAD_RESPONSE"
        # Allow RuntimeError to be caught by generic handler below if needed
        print(f"ERROR in /sessions calling AI: {e}")
        raise HTTPException(status_code=status_code, detail={"error": {"code": error_code, "message": str(e)}})
    except Exception as e:
        print(f"ERROR in /sessions unexpected: {e}")
        raise HTTPException(status_code=500, detail={"error": {"code": "SESSION_CREATION_FAILED", "message": "An unexpected error occurred creating the session."}})

    # Define initial session state including depth
    initial_depth = 0
    sessions[session_id] = {
        "topic": topic,
        "history": [("topic", topic)], # History starts with the main topic entry
        "current_menu": main_menu_items,
        "max_menu_depth": max_menu_depth,
        "current_depth": initial_depth # Store initial depth
    }
    print(f"--- Session '{session_id}' created. Max depth={max_menu_depth}. Current Depth={initial_depth}. State stored. ---")

    # Return the new MenuResponse structure
    return MenuResponse(
        type="submenu",
        menu_items=main_menu_items,
        content=None, # No content for initial menu
        session_id=session_id,
        current_depth=initial_depth,
        max_menu_depth=max_menu_depth
    )

# --- UPDATED /menus endpoint ---
@app.post("/menus", response_model=MenuResponse, status_code=200, summary="Process menu selection and get next items/content", tags=["Navigation"])
async def select_menu_item(menu_selection: MenuSelection):
    session_id = menu_selection.session_id
    selection = menu_selection.selection
    print(f"--- Received POST /menus request for session '{session_id}', selection: '{selection}' ---")

    # 1. Retrieve session state
    if session_id not in sessions:
        print(f"ERROR in /menus: Session ID '{session_id}' not found.")
        raise HTTPException(status_code=404, detail={"error": {"code": "SESSION_NOT_FOUND", "message": "Session ID not found. It might have expired or is invalid."}})
    session_data = sessions[session_id]

    # 2. Validate selection (using current_menu from session)
    current_menu = session_data.get("current_menu", [])
    if selection not in current_menu:
        print(f"ERROR in /menus: Selection '{selection}' not found in current menu: {current_menu}")
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_SELECTION", "message": f"Selection '{selection}' is not a valid option in the current menu."}})

    # 3. Retrieve depth info and calculate next depth
    max_menu_depth = session_data.get("max_menu_depth")
    # Use stored current_depth + 1 for the *next* depth level this selection leads to
    current_depth = session_data.get("current_depth", -1) # Get the depth *before* this selection
    next_depth = current_depth + 1

    if max_menu_depth is None or not isinstance(max_menu_depth, int) or current_depth == -1:
         print(f"ERROR in /menus: Depth information missing or invalid in session data for session '{session_id}'. MaxDepth: {max_menu_depth}, CurrentDepth: {current_depth}")
         raise HTTPException(status_code=500, detail={"error": {"code": "INTERNAL_SERVER_ERROR", "message": "Session state is missing menu depth information."}})

    print(f"--- Request is for transition from depth {current_depth} to {next_depth}. Max Depth: {max_menu_depth} ---")

    response = None # Initialize response variable

    # 4. Determine action based on the *next* depth level vs max_depth
    if next_depth < max_menu_depth:
        # Generate Submenu: We haven't reached the max depth yet
        print(f"--- Generating AI submenu (Target Depth {next_depth}) for selection: '{selection}' ---")
        if not openai_client:
            print("ERROR in /menus: OpenAI client not available.")
            raise HTTPException(status_code=503, detail={"error": {"code": "AI_SERVICE_UNAVAILABLE", "message": "OpenAI client is not available to generate submenu."}})
        try:
            topic = session_data.get("topic", "Unknown Topic")
            submenu_items = generate_submenu_with_ai(topic, selection)
            if not submenu_items:
                raise ValueError("AI submenu generation returned empty or invalid list")

            # Update session state AFTER successful generation
            session_data["history"].append(("menu_selection", selection))
            session_data["current_menu"] = submenu_items
            session_data["current_depth"] = next_depth # Update depth in session
            sessions[session_id] = session_data
            print(f"--- Session '{session_id}' updated. Submenu generated (Reached Depth {next_depth}). ---")

            # Construct the response
            response = MenuResponse(
                type="submenu",
                menu_items=submenu_items,
                content=None,
                session_id=session_id,
                current_depth=next_depth,
                max_menu_depth=max_menu_depth
            )

        except (ConnectionRefusedError, ConnectionAbortedError, ConnectionError, RuntimeError, ValueError) as e:
            status_code = 503; error_code = "AI_GENERATION_FAILED"
            if isinstance(e, ConnectionRefusedError): status_code, error_code = 401, "AI_AUTH_ERROR"
            elif isinstance(e, ConnectionAbortedError): status_code, error_code = 429, "AI_RATE_LIMIT"
            elif isinstance(e, ConnectionError): status_code, error_code = 504, "AI_CONNECTION_ERROR"
            elif isinstance(e, ValueError): status_code, error_code = 502, "AI_BAD_RESPONSE"
            # Allow RuntimeError to be caught by generic handler below if needed
            print(f"ERROR in /menus calling AI for submenu: {e}"); raise HTTPException(status_code=status_code, detail={"error": {"code": error_code, "message": str(e)}})
        except Exception as e:
            print(f"ERROR in /menus unexpected during AI call: {e}"); raise HTTPException(status_code=500, detail={"error": {"code": "SUBMENU_FAILED", "message": "An unexpected error occurred generating the submenu."}})

    elif next_depth == max_menu_depth:
        # Generate Content (Placeholder): We've reached the max depth
        print(f"--- Max depth reached. Generating placeholder content (Target Depth {next_depth}) for selection: '{selection}' ---")

        # --- TODO: Replace placeholder logic with actual AI call for content ---
        placeholder_content = f"## {selection}\n\nThis is placeholder content for **{selection}** (within the topic '{session_data.get('topic')}').\n\nActual AI-generated content providing an overview would appear here based on the selection path: {' -> '.join([item[1] for item in session_data['history']])} -> {selection}"
        placeholder_further_topics = ["Further Topic 1", "Further Topic 2", "Further Topic 3"] # TODO: Generate via AI?

        # Update session state AFTER successful generation
        session_data["history"].append(("menu_selection", selection))
        session_data["current_menu"] = placeholder_further_topics # Next menu is the "further topics"
        session_data["current_depth"] = next_depth # Update depth in session
        # session_data["last_content"] = placeholder_content # Optional: store last generated content
        sessions[session_id] = session_data
        print(f"--- Session '{session_id}' updated. Placeholder content generated (Reached Depth {next_depth}). ---")

        # Construct the response
        response = MenuResponse(
            type="content",
            menu_items=placeholder_further_topics, # Menu items are now the further exploration topics
            content=placeholder_content,
            session_id=session_id,
            current_depth=next_depth,
            max_menu_depth=max_menu_depth
        )

    else: # next_depth > max_menu_depth
        # This case handles selecting from the "further exploration topics" menu after content is shown
        # TODO: Implement behavior for selecting a "further exploration" topic.
        #       Should it start a new exploration? Go back? Show different content?
        #       For now, maybe just return the same content again or an error.
        print(f"--- Navigation beyond max depth ({max_menu_depth}) attempted from depth {current_depth}. Selection: {selection} ---")
        # Option 1: Return error
        # raise HTTPException(status_code=501, detail={"error": {"code": "MAX_DEPTH_NAVIGATION_NOT_IMPLEMENTED", "message": f"Selecting items after reaching maximum depth ({max_menu_depth}) is not yet implemented."}})
        # Option 2: Return previous content again (simple placeholder behavior)
        print(f"--- Returning previous content/further topics as >max_depth navigation not implemented ---")
        response = MenuResponse(
            type="content",
            menu_items=session_data.get("current_menu", []), # Return the existing further topics
            content=session_data.get("last_content", "Content was already displayed."), # Maybe retrieve stored content?
            session_id=session_id,
            current_depth=current_depth, # Return the previous depth state
            max_menu_depth=max_menu_depth
        )
        # For Option 2, we might need to store the 'last_content' in the session state when it's first generated.


    # 5. Return the prepared response (if successful)
    if response:
         return response
    else:
         # This case should ideally not be reached if logic above is sound
         print(f"ERROR in /menus: Failed to generate a response for session '{session_id}', selection '{selection}'.")
         raise HTTPException(status_code=500, detail={"error": {"code": "RESPONSE_GENERATION_FAILED", "message": "Server failed to generate a valid response for the menu selection."}})


# --- Uvicorn runner (for local development reference) ---
if __name__ == "__main__":
    import uvicorn
    print("--- Starting Uvicorn server (likely for local testing) ---")
    port = int(os.environ.get("PORT", 8000))
    # Use the string "main:app" to refer to the app instance
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
