import os
import uuid
import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Tuple # Ensure Optional and Tuple are imported
from dotenv import load_dotenv
import openai

# --- Pydantic Models ---

class TopicInput(BaseModel):
    """Model for receiving the initial topic from the frontend."""
    topic: str

class SessionResponse(BaseModel):
    """Model for responding when a new session is created."""
    session_id: str
    menu_items: List[str]

class MenuSelection(BaseModel):
    """Model for receiving a menu selection from the frontend."""
    session_id: str
    selection: str # Can be a menu item or "__BACK__"

class MenuResponse(BaseModel):
    """
    Model for responding to menu selections.
    Includes type to distinguish between submenu and content display.
    """
    type: str # "submenu" or "content"
    menu_items: List[str]
    content_markdown: Optional[str] = None # Markdown content (if type is "content")

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

# Initialize FastAPI application instance
app = FastAPI(
    title="AI Subject Explorer Backend",
    version="0.1.0",
    description="Backend API for the AI Subject Explorer application."
)

# --- CORS Middleware Configuration ---
origins = ["*"] # TODO: Restrict in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- In-Memory Session Storage ---
sessions: Dict[str, Dict[str, Any]] = {}

# --- AI Call Helper Functions ---

# generate_main_menu_with_ai (Unchanged from v3)
def generate_main_menu_with_ai(topic: str) -> Tuple[List[str], int]:
    """Generates main menu categories and determines max depth."""
    if not openai_client:
        print("WARNING: OpenAI client not available. Returning fallback main menu and depth.")
        return ([f"Introduction to {topic}", f"Key Concepts in {topic}", f"History of {topic}"], 2)
    print(f"--- Calling OpenAI (gpt-4.1-nano) for main menu & depth: '{topic}' ---")
    model_name = "gpt-4.1-nano"
    content_instruction = f"""You are an assistant designing a hierarchical exploration menu for the main topic '{topic}'.
Generate a list of 3 to 7 broad, relevant main categories for exploring this topic.
Also, determine a logical maximum depth (integer) for menu exploration for this topic before showing detailed content.
For testing purposes, constrain the maximum depth you return: for the topic '{topic}', please ALWAYS return a max_menu_depth of 2."""
    json_format_instruction = """Return ONLY a valid JSON object containing two keys: "categories", "max_menu_depth" (must be 2). Example: {"categories": ["Cat1", "Cat2"], "max_menu_depth": 2}"""
    system_prompt = f"{content_instruction}\n\n{json_format_instruction}"
    user_prompt = f"Generate menu and depth for topic: {topic}"
    try:
        completion = openai_client.chat.completions.create( model=model_name, messages=[ {"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt} ], max_tokens=250, temperature=0.5, response_format={"type": "json_object"} )
        content = completion.choices[0].message.content
        print(f"--- OpenAI Raw Main Menu/Depth Response: {content} ---")
        if not content: raise ValueError("OpenAI returned empty content.")
        try:
            parsed_data = json.loads(content)
            menu_items = []
            max_depth = 2 # Default/fallback
            if isinstance(parsed_data, dict) and "categories" in parsed_data and isinstance(parsed_data["categories"], list):
                menu_items = [str(item).strip() for item in parsed_data["categories"] if isinstance(item, str) and item.strip()]
                if not menu_items: raise ValueError("Parsed JSON ok, but 'categories' list was empty.")
            else: raise ValueError("AI response JSON structure incorrect or missing 'categories' list.")
            if isinstance(parsed_data, dict) and "max_menu_depth" in parsed_data and isinstance(parsed_data["max_menu_depth"], int):
                 max_depth = parsed_data["max_menu_depth"]
                 if max_depth != 2: max_depth = 2 # Enforce constraint
            else: print(f"WARNING: AI response missing valid 'max_menu_depth'. Defaulting to 2.")
            print(f"--- Parsed Main Menu Items: {menu_items} ---"); print(f"--- Parsed Max Menu Depth: {max_depth} ---")
            return (menu_items, max_depth)
        except json.JSONDecodeError: raise ValueError("AI main menu/depth response was not valid JSON.")
        except ValueError as ve: raise ve
        except Exception as parse_err: raise ValueError(f"Could not process AI main menu/depth response structure: {parse_err}")
    except openai.AuthenticationError as e: raise ConnectionRefusedError(f"OpenAI authentication failed. {e}")
    except openai.RateLimitError as e: raise ConnectionAbortedError(f"OpenAI rate limit hit. {e}")
    except openai.APIConnectionError as e: raise ConnectionError(f"Could not connect to OpenAI: {e}")
    except openai.APIError as e: raise RuntimeError(f"OpenAI returned an API error: {e}")
    except Exception as e: raise RuntimeError(f"Unexpected error during AI main menu/depth generation: {e}")

# generate_submenu_with_ai (Unchanged from v3)
def generate_submenu_with_ai(topic: str, category_selection: str) -> List[str]:
    """Generates submenu items using OpenAI."""
    if not openai_client:
        print("ERROR: OpenAI client not available for submenu generation.")
        return [f"Subtopic 1 for {category_selection}", f"Subtopic 2 for {category_selection}"]
    print(f"--- Calling OpenAI (gpt-4.1-nano) for submenu: Topic='{topic}', Category='{category_selection}' ---")
    model_name = "gpt-4.1-nano"
    system_prompt = f"""You are an assistant designing a hierarchical exploration menu for the main topic '{topic}'. Given the selected category, generate a list of 3 to 7 specific, relevant subtopics. Return ONLY a valid JSON object containing a single key "subtopics" which holds a list of strings. Example: {{"subtopics": ["Sub1", "Sub2"]}}"""
    user_prompt = f"Selected Category: {category_selection}"
    try:
        completion = openai_client.chat.completions.create( model=model_name, messages=[ {"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt} ], max_tokens=250, temperature=0.6, response_format={"type": "json_object"} )
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
    except openai.AuthenticationError as e: raise ConnectionRefusedError(f"OpenAI authentication failed. {e}")
    except openai.RateLimitError as e: raise ConnectionAbortedError(f"OpenAI rate limit hit. {e}")
    except openai.APIConnectionError as e: raise ConnectionError(f"Could not connect to OpenAI: {e}")
    except openai.APIError as e: raise RuntimeError(f"OpenAI returned an API error: {e}")
    except Exception as e: raise RuntimeError(f"Unexpected error during AI submenu generation: {e}")

# generate_content_and_further_topics (Unchanged from v3)
def generate_content_and_further_topics(topic: str, selection_path: List[str]) -> Tuple[str, List[str]]:
    """Generates markdown content and further topics."""
    if not openai_client:
        print("ERROR: OpenAI client not available for content generation.")
        selection_str = " -> ".join(selection_path)
        return (f"## Fallback Content\n\nDetails about '{selection_str}' would appear here.", ["Deeper Topic 1", "Deeper Topic 2"])
    current_selection = selection_path[-1] if selection_path else "the main topic"
    full_context_path = f"{topic} -> {' -> '.join(selection_path)}"
    print(f"--- Calling OpenAI (gpt-4.1-nano) for Content: Path='{full_context_path}' ---")
    model_name = "gpt-4.1-nano"
    content_instruction = f"""You are an assistant providing information based on a user's exploration path: '{full_context_path}'. Provide a concise, informative overview of the final selection ('{current_selection}') in Markdown format. Also, generate a list of 3 to 5 specific aspects or "dig deeper" topics related to '{current_selection}'."""
    json_format_instruction = """Return ONLY a valid JSON object containing two keys: "content_markdown" (string) and "further_topics" (list of strings). Example: {"content_markdown": "## Topic\nDetails...", "further_topics": ["Detail A", "Detail B"]}"""
    system_prompt = f"{content_instruction}\n\n{json_format_instruction}"
    user_prompt = f"Generate content and further topics for: {current_selection}"
    try:
        completion = openai_client.chat.completions.create( model=model_name, messages=[ {"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt} ], max_tokens=500, temperature=0.6, response_format={"type": "json_object"} )
        content_response = completion.choices[0].message.content
        print(f"--- OpenAI Raw Content/Further Topics Response: {content_response} ---")
        if not content_response: raise ValueError("OpenAI returned empty content for content generation.")
        try:
            parsed_data = json.loads(content_response)
            content_markdown = ""
            further_topics = []
            if isinstance(parsed_data, dict) and "content_markdown" in parsed_data and isinstance(parsed_data["content_markdown"], str):
                content_markdown = parsed_data["content_markdown"].strip()
                if not content_markdown: raise ValueError("Parsed JSON ok, but 'content_markdown' was empty.")
            else: raise ValueError("AI response JSON structure incorrect or missing 'content_markdown' string.")
            if isinstance(parsed_data, dict) and "further_topics" in parsed_data and isinstance(parsed_data["further_topics"], list):
                further_topics = [str(item).strip() for item in parsed_data["further_topics"] if isinstance(item, str) and item.strip()]
                if not further_topics: raise ValueError("Parsed JSON ok, but 'further_topics' list was empty.")
            else: raise ValueError("AI response JSON structure incorrect or missing 'further_topics' list.")
            print(f"--- Parsed Content (Markdown): {content_markdown[:100]}... ---"); print(f"--- Parsed Further Topics: {further_topics} ---")
            return (content_markdown, further_topics)
        except json.JSONDecodeError: raise ValueError("AI content/further topics response was not valid JSON.")
        except ValueError as ve: raise ve
        except Exception as parse_err: raise ValueError(f"Could not process AI content/further topics response structure: {parse_err}")
    except openai.AuthenticationError as e: raise ConnectionRefusedError(f"OpenAI authentication failed. {e}")
    except openai.RateLimitError as e: raise ConnectionAbortedError(f"OpenAI rate limit hit. {e}")
    except openai.APIConnectionError as e: raise ConnectionError(f"Could not connect to OpenAI: {e}")
    except openai.APIError as e: raise RuntimeError(f"OpenAI returned an API error: {e}")
    except Exception as e: raise RuntimeError(f"Unexpected error during AI content/further topics generation: {e}")


# --- API Endpoints ---

@app.get("/", summary="Health Check", tags=["General"])
async def read_root():
    """Provides a simple health check endpoint."""
    return {"message": "AI Subject Explorer Backend is alive!"}


@app.post("/sessions", response_model=SessionResponse, status_code=201, summary="Start a new exploration session", tags=["Session Management"])
async def create_session(topic_input: TopicInput):
    """Creates a new session, gets initial menu and depth from AI."""
    session_id = str(uuid.uuid4())
    topic = topic_input.topic
    print(f"--- Received POST /sessions request for topic: '{topic}' ---")
    if not openai_client: raise HTTPException(status_code=503, detail={"error": {"code": "AI_SERVICE_UNAVAILABLE", "message": "OpenAI client is not initialized."}})
    try:
        main_menu_items, max_menu_depth = generate_main_menu_with_ai(topic)
        if not main_menu_items: raise ValueError("AI menu generation returned empty list")
    except (ConnectionRefusedError, ConnectionAbortedError, ConnectionError, RuntimeError, ValueError) as e:
        status_code = 503; error_code = "AI_GENERATION_FAILED"
        if isinstance(e, ConnectionRefusedError): status_code, error_code = 401, "AI_AUTH_ERROR"
        elif isinstance(e, ConnectionAbortedError): status_code, error_code = 429, "AI_RATE_LIMIT"
        elif isinstance(e, ConnectionError): status_code, error_code = 504, "AI_CONNECTION_ERROR"
        elif isinstance(e, ValueError): status_code, error_code = 502, "AI_BAD_RESPONSE"
        elif isinstance(e, RuntimeError): status_code, error_code = 502, "AI_API_ERROR"
        print(f"ERROR in /sessions calling AI: {e}"); raise HTTPException(status_code=status_code, detail={"error": {"code": error_code, "message": str(e)}})
    except Exception as e: print(f"ERROR in /sessions unexpected: {e}"); raise HTTPException(status_code=500, detail={"error": {"code": "SESSION_CREATION_FAILED", "message": "Unexpected error creating session."}})
    sessions[session_id] = { "topic": topic, "history": [("topic", topic)], "current_menu": main_menu_items, "max_menu_depth": max_menu_depth }
    print(f"--- Session '{session_id}' created. Max depth={max_menu_depth}. State stored. ---")
    return SessionResponse(session_id=session_id, menu_items=main_menu_items)


# *** UPDATED /menus endpoint to handle __BACK__ ***
@app.post("/menus", response_model=MenuResponse, status_code=200, summary="Process menu selection or back navigation", tags=["Navigation"])
async def select_menu_item(menu_selection: MenuSelection):
    """
    Processes a user's menu selection OR a special '__BACK__' command.
    Determines action based on selection and current depth.
    Calls appropriate AI functions and returns the result.
    """
    session_id = menu_selection.session_id
    selection = menu_selection.selection
    print(f"--- Received POST /menus request for session '{session_id}', selection: '{selection}' ---")

    # 1. Retrieve session state
    if session_id not in sessions:
        print(f"ERROR in /menus: Session ID '{session_id}' not found.")
        raise HTTPException(status_code=404, detail={"error": {"code": "SESSION_NOT_FOUND", "message": "Session ID not found."}})
    session_data = sessions[session_id]

    # 2. Retrieve necessary info from session
    topic = session_data.get("topic", "Unknown Topic")
    current_history = session_data.get("history", [])
    max_menu_depth = session_data.get("max_menu_depth")
    if max_menu_depth is None or not isinstance(max_menu_depth, int):
         print(f"ERROR in /menus: max_menu_depth missing/invalid for session '{session_id}'.")
         raise HTTPException(status_code=500, detail={"error": {"code": "INTERNAL_SERVER_ERROR", "message": "Session state missing depth."}})

    response = None # Initialize response variable

    # --- Handle Back Navigation FIRST ---
    if selection == "__BACK__":
        print("--- Handling Go Back request ---")
        if len(current_history) <= 1:
            # Cannot go back from the initial topic/menu
            print("--- Cannot go back further (already at root). ---")
            # Return the current menu state without changing history
            return MenuResponse(type="submenu", menu_items=session_data.get("current_menu", []), content_markdown=None)

        # Remove the last step from history
        new_history = current_history[:-1]
        session_data["history"] = new_history
        new_level = len(new_history)
        previous_menu_items = []

        try:
            if new_level == 1: # Went back to the initial topic level
                print("--- Regenerating main menu (Level 1) ---")
                # Call main menu AI, but we only need the items, ignore depth
                previous_menu_items, _ = generate_main_menu_with_ai(topic)
            else: # Went back to a previous submenu level
                # Get the selection that led to the *previous* level
                previous_selection = new_history[-1][1] # Get value from last tuple in new history
                print(f"--- Regenerating submenu (Level {new_level}) for previous selection: '{previous_selection}' ---")
                previous_menu_items = generate_submenu_with_ai(topic, previous_selection)

            if not previous_menu_items:
                raise ValueError("AI generation for previous menu returned empty list")

            # Update session state with the regenerated previous menu
            session_data["current_menu"] = previous_menu_items
            sessions[session_id] = session_data
            print(f"--- Session '{session_id}' updated. Navigated back (Level {new_level}). ---")

            # Prepare response (always submenu when going back)
            response = MenuResponse(type="submenu", menu_items=previous_menu_items, content_markdown=None)

        # Handle potential AI errors during back navigation regeneration
        except (ConnectionRefusedError, ConnectionAbortedError, ConnectionError, RuntimeError, ValueError) as e:
            status_code = 503; error_code = "AI_GENERATION_FAILED"
            # Map specific errors... (same mapping as below)
            if isinstance(e, ConnectionRefusedError): status_code, error_code = 401, "AI_AUTH_ERROR"
            elif isinstance(e, ConnectionAbortedError): status_code, error_code = 429, "AI_RATE_LIMIT"
            elif isinstance(e, ConnectionError): status_code, error_code = 504, "AI_CONNECTION_ERROR"
            elif isinstance(e, ValueError): status_code, error_code = 502, "AI_BAD_RESPONSE"
            elif isinstance(e, RuntimeError): status_code, error_code = 502, "AI_API_ERROR"
            print(f"ERROR in /menus regenerating previous menu for back navigation: {e}")
            # Restore history before raising error? Or leave state potentially inconsistent? Let's leave it for now.
            # session_data["history"] = current_history # Option: Restore history
            raise HTTPException(status_code=status_code, detail={"error": {"code": error_code, "message": f"Failed to regenerate previous menu: {e}"}})
        except Exception as e:
            print(f"ERROR in /menus unexpected during back navigation: {e}")
            raise HTTPException(status_code=500, detail={"error": {"code": "BACK_NAVIGATION_FAILED", "message": "Unexpected error during back navigation."}})

    # --- Handle Regular Menu Selection ---
    else:
        # 3. Validate selection (only if not "__BACK__")
        current_menu_in_session = session_data.get("current_menu", [])
        if selection not in current_menu_in_session:
            print(f"ERROR in /menus: Selection '{selection}' not found in current menu: {current_menu_in_session}")
            raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_SELECTION", "message": f"Selection '{selection}' is not a valid option."}})

        # 4. Determine action based on level vs max_depth
        current_level = len(current_history)
        print(f"--- Current Level: {current_level}, Max Depth: {max_menu_depth} ---")

        try:
            if current_level < max_menu_depth:
                # Generate Submenu
                print(f"--- Generating AI submenu (Level {current_level + 1}) for selection: '{selection}' ---")
                if not openai_client: raise ConnectionAbortedError("OpenAI client unavailable.")

                submenu_items = generate_submenu_with_ai(topic, selection)
                if not submenu_items: raise ValueError("AI submenu generation returned empty list")

                new_history = current_history + [("menu_selection", selection)]
                session_data["history"] = new_history
                session_data["current_menu"] = submenu_items
                sessions[session_id] = session_data
                print(f"--- Session '{session_id}' updated. Submenu generated (Level {current_level+1}). ---")
                response = MenuResponse(type="submenu", menu_items=submenu_items, content_markdown=None)

            elif current_level >= max_menu_depth:
                # Generate Content
                print(f"--- Generating AI content (Level {current_level + 1}) for selection: '{selection}' ---")
                if not openai_client: raise ConnectionAbortedError("OpenAI client unavailable.")

                selection_path = [item[1] for item in current_history if item[0] == 'menu_selection'] + [selection]
                content_markdown, further_topics = generate_content_and_further_topics(topic, selection_path)
                if not content_markdown or not further_topics: raise ValueError("AI content generation returned empty content/topics")

                new_history = current_history + [("menu_selection", selection)]
                session_data["history"] = new_history
                session_data["current_menu"] = further_topics
                sessions[session_id] = session_data
                print(f"--- Session '{session_id}' updated. AI Content generated (Level {current_level+1}). ---")
                response = MenuResponse(type="content", menu_items=further_topics, content_markdown=content_markdown)

        # Handle potential AI and other errors
        except (ConnectionRefusedError, ConnectionAbortedError, ConnectionError, RuntimeError, ValueError) as e:
            status_code = 503; error_code = "AI_GENERATION_FAILED"
            # Map specific errors... (same mapping as above)
            if isinstance(e, ConnectionRefusedError): status_code, error_code = 401, "AI_AUTH_ERROR"
            elif isinstance(e, ConnectionAbortedError): status_code, error_code = 429, "AI_RATE_LIMIT"
            elif isinstance(e, ConnectionError): status_code, error_code = 504, "AI_CONNECTION_ERROR"
            elif isinstance(e, ValueError): status_code, error_code = 502, "AI_BAD_RESPONSE"
            elif isinstance(e, RuntimeError): status_code, error_code = 502, "AI_API_ERROR"
            print(f"ERROR in /menus processing selection: {e}")
            raise HTTPException(status_code=status_code, detail={"error": {"code": error_code, "message": str(e)}})
        except Exception as e:
            print(f"ERROR in /menus unexpected: {e}")
            raise HTTPException(status_code=500, detail={"error": {"code": "MENU_PROCESSING_FAILED", "message": "Unexpected server error processing selection."}})

    # 5. Return the prepared response
    if response:
         return response
    else:
         # Safeguard
         print(f"ERROR in /menus: Failed to generate response for session '{session_id}', selection '{selection}'.")
         raise HTTPException(status_code=500, detail={"error": {"code": "RESPONSE_GENERATION_FAILED", "message": "Server failed to generate response."}})


# --- Uvicorn runner (for local development) ---
if __name__ == "__main__":
    import uvicorn
    print("--- Starting Uvicorn server (likely for local testing) ---")
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)

