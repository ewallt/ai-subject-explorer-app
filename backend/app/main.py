import os
import uuid
import json # <-- Import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from dotenv import load_dotenv # <-- Import dotenv
import openai # <-- Import openai

# --- Pydantic Models ---
# (Keep existing models: TopicInput, SessionResponse, MenuSelection, MenuResponse)
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
load_dotenv() # Load .env file if present (for local dev)

# Initialize OpenAI Client
# Reads OPENAI_API_KEY from environment variables automatically
openai_client = None # Initialize as None
try:
    # This automatically looks for the OPENAI_API_KEY environment variable
    openai_client = openai.OpenAI()
    # Verify if the key was actually found by the client library
    if not openai_client.api_key:
         print("WARNING: OPENAI_API_KEY environment variable not found or empty by OpenAI client.")
         openai_client = None
    else:
        print("--- OpenAI client initialized successfully. ---")
except Exception as e:
    # Catch potential errors during client instantiation
    print(f"ERROR: Failed to initialize OpenAI client: {e}")
    openai_client = None


# Initialize FastAPI app
app = FastAPI(
    title="AI Subject Explorer Backend",
    description="API for the AI Subject Explorer.",
    version="0.1.0",
)

# --- In-Memory Session Storage ---
sessions: Dict[str, Dict[str, Any]] = {}

# --- AI Call Function (Replaces Placeholder) ---
def generate_main_menu_with_ai(topic: str) -> List[str]:
    """ Generates the main menu using OpenAI API, expecting JSON list output. """
    if not openai_client:
        print("ERROR: OpenAI client not available. Returning fallback menu.")
        # Fallback menu if OpenAI isn't configured
        return [f"Introduction to {topic}", f"History of {topic}"]

    print(f"--- Calling OpenAI (gpt-4.1-nano) to generate main menu for topic: '{topic}' ---")
    model_name = "gpt-4.1-nano" # Using the specified model
    system_prompt = """You are an assistant designing a hierarchical exploration menu.
Given a topic, generate a list of 3 to 7 broad, relevant categories for exploration.
Return ONLY a valid JSON object containing a single key "categories" which holds a list of strings. Example response:
{
  "categories": ["Category 1", "Category 2", "Category 3"]
}"""
    user_prompt = f"Topic: {topic}"

    try:
        completion = openai_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=200,
            temperature=0.5,
            response_format={"type": "json_object"} # Request JSON output
        )

        content = completion.choices[0].message.content
        print(f"--- OpenAI Raw Response Content: {content} ---")

        if not content:
            raise ValueError("OpenAI returned empty content.")

        # Attempt to parse the JSON response
        try:
            parsed_data = json.loads(content)
            menu_items = []
            # Expecting structure like {"categories": [...]}
            if isinstance(parsed_data, dict) and "categories" in parsed_data and isinstance(parsed_data["categories"], list):
                 menu_items = [str(item).strip() for item in parsed_data["categories"] if isinstance(item, str) and item.strip()]
            else:
                 # If the expected structure isn't found, raise an error
                 print(f"ERROR: Unexpected JSON structure received: {parsed_data}")
                 raise ValueError("AI response JSON structure incorrect. Expected {'categories': [...]}.")

            if not menu_items:
                 raise ValueError("Parsed JSON, but 'categories' list was empty or invalid.")

            print(f"--- Parsed Menu Items: {menu_items} ---")
            return menu_items

        except json.JSONDecodeError:
            print(f"ERROR: OpenAI response was not valid JSON: {content}")
            raise ValueError("AI response was not valid JSON.")
        except Exception as parse_err:
             print(f"ERROR: Failed to parse or validate OpenAI JSON response: {parse_err}")
             raise ValueError(f"Could not process AI response structure: {parse_err}")

    # Handle specific OpenAI errors
    except openai.AuthenticationError as e:
        print(f"ERROR: OpenAI Authentication Failed: {e}")
        # Raise error that will be caught by endpoint handler
        raise ConnectionRefusedError("OpenAI authentication failed. Check API key.")
    except openai.RateLimitError as e:
        print(f"ERROR: OpenAI Rate Limit Exceeded: {e}")
        raise ConnectionAbortedError("OpenAI rate limit hit. Please try again later.")
    except openai.APIConnectionError as e:
        print(f"ERROR: OpenAI Connection Error: {e}")
        raise ConnectionError(f"Could not connect to OpenAI: {e}")
    except openai.APIError as e:
        print(f"ERROR: OpenAI API Error: {e}")
        raise RuntimeError(f"OpenAI returned an API error: {e}")
    except Exception as e:
        print(f"ERROR: Unexpected error during OpenAI call: {e}")
        raise RuntimeError(f"An unexpected error occurred with AI generation: {e}")


# --- Placeholder function for submenus (KEEPING THIS FOR NOW) ---
def get_submenu_placeholder(session_data: Dict[str, Any], selection: str) -> List[str]:
    """ Placeholder function to generate a submenu based on selection. """
    print(f"--- MOCK BACKEND: Generating submenu for selection: '{selection}' (Using Placeholder) ---") # Clarified log
    topic = session_data.get("topic", "Unknown Topic")
    # Using simple placeholder logic, removing "Test 1:" marker now
    if "history" in selection.lower():
        return [f"Early {topic} History", f"Mid-Century {topic}", f"Recent {topic}"]
    elif "introduction" in selection.lower():
         return [f"Core Concept A for {topic}", f"Core Concept B", f"Related Terms for {topic}"]
    elif "applications" in selection.lower():
        return [f"Use Case 1 ({topic})", f"Use Case 2", f"Industry Examples ({topic})"]
    else:
        return [f"Sub-Item 1 for {selection}", f"Sub-Item 2 ({topic})", f"Sub-Item 3"]


# --- API Endpoints ---

@app.get("/")
# ... (keep existing code) ...
async def read_root():
    return {"message": "AI Subject Explorer Backend is alive!"}


@app.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=201,
    summary="Start a new exploration session",
    tags=["Session Management"]
)
async def create_session(topic_input: TopicInput):
    """ Creates a new session and returns the first menu generated by AI. """
    session_id = str(uuid.uuid4())
    topic = topic_input.topic
    print(f"--- Received POST /sessions request for topic: '{topic}' ---")

    if not openai_client: # Check if client failed to initialize
         print("ERROR in /sessions: OpenAI client not available.")
         raise HTTPException(status_code=503, detail={"error": {"code": "AI_SERVICE_UNAVAILABLE", "message": "OpenAI client not configured or key missing."}})

    try:
        # *** CALL REAL AI FUNCTION ***
        main_menu_items = generate_main_menu_with_ai(topic)
        if not main_menu_items:
             raise ValueError("AI menu generation returned empty or invalid list")

    # Catch specific errors defined in the AI function for better status codes
    except (ConnectionRefusedError, ConnectionAbortedError, ConnectionError, RuntimeError, ValueError) as e:
         status_code = 503 # Service Unavailable or Bad Gateway default
         error_code = "AI_GENERATION_FAILED"
         if isinstance(e, ConnectionRefusedError): status_code, error_code = 401, "AI_AUTH_ERROR"
         elif isinstance(e, ConnectionAbortedError): status_code, error_code = 429, "AI_RATE_LIMIT"
         elif isinstance(e, ConnectionError): status_code, error_code = 504, "AI_CONNECTION_ERROR"
         elif isinstance(e, ValueError): status_code, error_code = 502, "AI_BAD_RESPONSE"
         elif isinstance(e, RuntimeError): status_code = 502, "AI_API_ERROR"

         print(f"ERROR in /sessions calling AI: {e}")
         raise HTTPException(
            status_code=status_code,
            detail={"error": {"code": error_code, "message": str(e)}}
         )
    except Exception as e: # Catch any other unexpected errors
        print(f"ERROR in /sessions unexpected: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "SESSION_CREATION_FAILED", "message": "An unexpected error occurred creating the session."}}
        )

    # Store the initial state
    sessions[session_id] = {
        "history": [("topic", topic)],
        "current_menu": main_menu_items,
        "topic": topic
    }
    print(f"--- Session '{session_id}' created successfully using AI. State stored. ---")

    # Return the response
    return SessionResponse(session_id=session_id, menu_items=main_menu_items)


@app.post(
    "/menus",
    response_model=MenuResponse,
    status_code=200,
    summary="Process menu selection and get next menu",
    tags=["Navigation"]
)
async def select_menu_item(menu_selection: MenuSelection):
    """
    Takes a session ID and user selection, retrieves session state,
    validates selection, generates the next menu (using placeholder FOR NOW),
    updates state, and returns the new menu.
    """
    # --- KEEPING OLD LOGIC using submenu placeholder for now ---
    # (Code remains exactly the same as previous version for this endpoint)
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
        # STILL using placeholder here
        submenu_items = get_submenu_placeholder(session_data, selection)
        if not submenu_items:
             raise ValueError("Placeholder submenu generation returned empty list")
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
