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
    selection: str

class MenuResponse(BaseModel):
    """
    Model for responding to menu selections.
    Includes type to distinguish between submenu and content display.
    """
    type: str # "submenu" or "content"
    menu_items: List[str]
    content_markdown: Optional[str] = None # Markdown content (if type is "content")

# --- Configuration & Initialization ---

load_dotenv() # Load environment variables from .env file (like OPENAI_API_KEY)
openai_client = None
try:
    # Initialize the OpenAI client using the API key from environment variables
    openai_client = openai.OpenAI()
    if not openai_client.api_key:
         print("WARNING: OPENAI_API_KEY environment variable not found or empty by OpenAI client.")
         openai_client = None # Ensure client is None if key is missing
    else:
         print("--- OpenAI client initialized successfully. ---")
except Exception as e:
    # Catch potential errors during client initialization
    print(f"ERROR: Failed to initialize OpenAI client: {e}")
    openai_client = None

# Initialize FastAPI application instance
app = FastAPI(
    title="AI Subject Explorer Backend",
    version="0.1.0",
    description="Backend API for the AI Subject Explorer application."
)

# --- CORS Middleware Configuration ---

# Define allowed origins for Cross-Origin Resource Sharing (CORS)
# Use "*" for development, but restrict this in production for security.
origins = ["*"] # TODO: Restrict in production to your frontend URL

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # Allow origins specified above
    allow_credentials=True, # Allow cookies to be included in requests
    allow_methods=["*"], # Allow all standard HTTP methods
    allow_headers=["*"], # Allow all headers
)

# --- In-Memory Session Storage ---

# Simple dictionary to store session data in memory.
# Data will be lost if the backend restarts.
# Key: session_id (str)
# Value: Dictionary containing session state (topic, history, current_menu, max_menu_depth)
sessions: Dict[str, Dict[str, Any]] = {}

# --- AI Call Helper Functions ---

def generate_main_menu_with_ai(topic: str) -> Tuple[List[str], int]:
    """
    Generates main menu categories and determines appropriate max depth using OpenAI.
    Returns a tuple: (list_of_categories, max_menu_depth).
    """
    if not openai_client:
        print("WARNING: OpenAI client not available. Returning fallback main menu and depth.")
        return ([f"Introduction to {topic}", f"Key Concepts in {topic}", f"History of {topic}"], 2)

    print(f"--- Calling OpenAI (gpt-4.1-nano) for main menu & depth: '{topic}' ---")
    model_name = "gpt-4.1-nano"

    # Define instructions for the AI (content + format)
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
    user_prompt = f"Generate menu and depth for topic: {topic}"

    try:
        # Make the API call to OpenAI
        completion = openai_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=250,
            temperature=0.5,
            response_format={"type": "json_object"} # Request JSON output
        )
        content = completion.choices[0].message.content
        print(f"--- OpenAI Raw Main Menu/Depth Response: {content} ---")
        if not content:
            raise ValueError("OpenAI returned empty content.")

        # Parse and validate the JSON response
        try:
            parsed_data = json.loads(content)
            menu_items = []
            max_depth = -1

            # Parse categories
            if isinstance(parsed_data, dict) and "categories" in parsed_data and isinstance(parsed_data["categories"], list):
                menu_items = [str(item).strip() for item in parsed_data["categories"] if isinstance(item, str) and item.strip()]
                if not menu_items:
                     raise ValueError("Parsed JSON ok, but 'categories' list was empty or invalid.")
            else:
                raise ValueError("AI response JSON structure incorrect or missing 'categories' list.")

            # Parse max_menu_depth
            if isinstance(parsed_data, dict) and "max_menu_depth" in parsed_data and isinstance(parsed_data["max_menu_depth"], int):
                 max_depth = parsed_data["max_menu_depth"]
                 if max_depth != 2: # Enforce constraint for testing
                      print(f"WARNING: AI returned max_menu_depth={max_depth}, but was constrained to return 2. Using 2.")
                      max_depth = 2
            else:
                 print(f"WARNING: AI response JSON structure incorrect or missing valid 'max_menu_depth' integer. Defaulting to 2.")
                 max_depth = 2 # Fallback depth

            print(f"--- Parsed Main Menu Items: {menu_items} ---")
            print(f"--- Parsed Max Menu Depth: {max_depth} ---")
            return (menu_items, max_depth)

        except json.JSONDecodeError:
            raise ValueError("AI main menu/depth response was not valid JSON.")
        except ValueError as ve:
             raise ve # Re-raise specific validation errors
        except Exception as parse_err:
            raise ValueError(f"Could not process AI main menu/depth response structure: {parse_err}")

    # Handle specific OpenAI API errors
    except openai.AuthenticationError as e: raise ConnectionRefusedError(f"OpenAI authentication failed. Check API key. {e}")
    except openai.RateLimitError as e: raise ConnectionAbortedError(f"OpenAI rate limit hit. {e}")
    except openai.APIConnectionError as e: raise ConnectionError(f"Could not connect to OpenAI: {e}")
    except openai.APIError as e: raise RuntimeError(f"OpenAI returned an API error: {e}")
    except Exception as e: raise RuntimeError(f"Unexpected error during AI main menu/depth generation: {e}")


def generate_submenu_with_ai(topic: str, category_selection: str) -> List[str]:
    """
    Generates submenu items using OpenAI API based on topic and category.
    """
    if not openai_client:
        print("ERROR: OpenAI client not available for submenu generation.")
        return [f"Subtopic 1 for {category_selection}", f"Subtopic 2 for {category_selection}"]

    print(f"--- Calling OpenAI (gpt-4.1-nano) for submenu: Topic='{topic}', Category='{category_selection}' ---")
    model_name = "gpt-4.1-nano"

    # Define instructions for the AI (content + format)
    system_prompt = f"""You are an assistant designing a hierarchical exploration menu for the main topic '{topic}'.
Given the selected category, generate a list of 3 to 7 specific, relevant subtopics within that category.
Return ONLY a valid JSON object containing a single key "subtopics" which holds a list of strings. Example response:
{{
  "subtopics": ["Subtopic 1", "Subtopic 2", "Subtopic 3"]
}}"""
    user_prompt = f"Selected Category: {category_selection}"

    try:
        # Make the API call
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

        # Parse and validate the JSON response
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

    # Handle specific OpenAI API errors
    except openai.AuthenticationError as e: raise ConnectionRefusedError(f"OpenAI authentication failed. Check API key. {e}")
    except openai.RateLimitError as e: raise ConnectionAbortedError(f"OpenAI rate limit hit. {e}")
    except openai.APIConnectionError as e: raise ConnectionError(f"Could not connect to OpenAI: {e}")
    except openai.APIError as e: raise RuntimeError(f"OpenAI returned an API error: {e}")
    except Exception as e: raise RuntimeError(f"Unexpected error during AI submenu generation: {e}")


def generate_content_and_further_topics(topic: str, selection_path: List[str]) -> Tuple[str, List[str]]:
    """
    Generates markdown content and further exploration topics using OpenAI.
    Args:
        topic: The original main topic.
        selection_path: List of user's selections leading to this point.
    Returns:
        A tuple: (content_markdown, further_topics_list).
    """
    if not openai_client:
        print("ERROR: OpenAI client not available for content generation.")
        selection_str = " -> ".join(selection_path)
        return (f"## Fallback Content\n\nDetails about '{selection_str}' would appear here.", ["Deeper Topic 1", "Deeper Topic 2"])

    # Construct context for the prompt
    current_selection = selection_path[-1] if selection_path else "the main topic"
    full_context_path = f"{topic} -> {' -> '.join(selection_path)}"

    print(f"--- Calling OpenAI (gpt-4.1-nano) for Content: Path='{full_context_path}' ---")
    model_name = "gpt-4.1-nano"

    # Define instructions for the AI (content + format)
    content_instruction = f"""You are an assistant providing information based on a user's exploration path.
The user started with the topic '{topic}' and navigated through: '{full_context_path}'.
Provide a concise, informative overview of the final selection ('{current_selection}') in Markdown format. Focus on key information.
Also, generate a list of 3 to 5 specific aspects, related concepts, or "dig deeper" topics directly related to '{current_selection}' for further exploration."""

    json_format_instruction = """Return ONLY a valid JSON object containing two keys:
1.  "content_markdown": A string containing the informative overview in Markdown format.
2.  "further_topics": A list of strings representing the specific aspects or deeper dive topics.

Example response:
{
  "content_markdown": "## Subtopic X\n\nSubtopic X is characterized by...\n\n- Point 1\n- Point 2",
  "further_topics": ["Specific Detail of X", "Historical Context of X", "Related Concept Y"]
}"""

    system_prompt = f"{content_instruction}\n\n{json_format_instruction}"
    user_prompt = f"Generate content and further topics for the selection: {current_selection}"

    try:
        # Make the API call
        completion = openai_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=500, # Allow more tokens for content
            temperature=0.6,
            response_format={"type": "json_object"}
        )
        content_response = completion.choices[0].message.content
        print(f"--- OpenAI Raw Content/Further Topics Response: {content_response} ---")
        if not content_response:
            raise ValueError("OpenAI returned empty content for content generation.")

        # Parse and validate the JSON response
        try:
            parsed_data = json.loads(content_response)
            content_markdown = ""
            further_topics = []

            # Parse content_markdown
            if isinstance(parsed_data, dict) and "content_markdown" in parsed_data and isinstance(parsed_data["content_markdown"], str):
                content_markdown = parsed_data["content_markdown"].strip()
                if not content_markdown:
                     raise ValueError("Parsed JSON ok, but 'content_markdown' was empty.")
            else:
                raise ValueError("AI response JSON structure incorrect or missing 'content_markdown' string.")

            # Parse further_topics
            if isinstance(parsed_data, dict) and "further_topics" in parsed_data and isinstance(parsed_data["further_topics"], list):
                further_topics = [str(item).strip() for item in parsed_data["further_topics"] if isinstance(item, str) and item.strip()]
                if not further_topics:
                     raise ValueError("Parsed JSON ok, but 'further_topics' list was empty or invalid.")
            else:
                raise ValueError("AI response JSON structure incorrect or missing 'further_topics' list.")

            print(f"--- Parsed Content (Markdown): {content_markdown[:100]}... ---")
            print(f"--- Parsed Further Topics: {further_topics} ---")
            return (content_markdown, further_topics)

        except json.JSONDecodeError:
            raise ValueError("AI content/further topics response was not valid JSON.")
        except ValueError as ve:
             raise ve # Re-raise specific validation errors
        except Exception as parse_err:
            raise ValueError(f"Could not process AI content/further topics response structure: {parse_err}")

    # Handle specific OpenAI API errors
    except openai.AuthenticationError as e: raise ConnectionRefusedError(f"OpenAI authentication failed. Check API key. {e}")
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
    """
    Creates a new exploration session for the given topic.
    Calls AI to generate the initial menu and determine max depth.
    Stores session state and returns session ID and menu items.
    """
    session_id = str(uuid.uuid4())
    topic = topic_input.topic
    print(f"--- Received POST /sessions request for topic: '{topic}' ---")

    if not openai_client:
        raise HTTPException(status_code=503, detail={"error": {"code": "AI_SERVICE_UNAVAILABLE", "message": "OpenAI client is not initialized. Check backend logs and API key."}})

    try:
        # Get initial menu and depth from AI
        main_menu_items, max_menu_depth = generate_main_menu_with_ai(topic)
        if not main_menu_items:
            raise ValueError("AI menu generation returned empty/invalid list")

    # Handle potential errors from the AI call
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
        raise HTTPException(status_code=500, detail={"error": {"code": "SESSION_CREATION_FAILED", "message": "An unexpected error occurred creating the session."}})

    # Store the initial session state
    sessions[session_id] = {
        "topic": topic,
        "history": [("topic", topic)], # History starts with the topic
        "current_menu": main_menu_items,
        "max_menu_depth": max_menu_depth # Store the depth
    }
    print(f"--- Session '{session_id}' created. Max depth={max_menu_depth}. State stored. ---")

    # Return the session ID and initial menu to the frontend
    return SessionResponse(session_id=session_id, menu_items=main_menu_items)


@app.post("/menus", response_model=MenuResponse, status_code=200, summary="Process menu selection and get next items", tags=["Navigation"])
async def select_menu_item(menu_selection: MenuSelection):
    """
    Processes a user's menu selection for a given session.
    Determines whether to fetch a submenu or content based on the current depth.
    Calls the appropriate AI function and returns the result.
    """
    session_id = menu_selection.session_id
    selection = menu_selection.selection
    print(f"--- Received POST /menus request for session '{session_id}', selection: '{selection}' ---")

    # 1. Retrieve session state
    if session_id not in sessions:
        print(f"ERROR in /menus: Session ID '{session_id}' not found.")
        raise HTTPException(status_code=404, detail={"error": {"code": "SESSION_NOT_FOUND", "message": "Session ID not found. It might have expired or is invalid."}})
    session_data = sessions[session_id]

    # 2. Validate selection against the current menu stored in the session
    current_menu_in_session = session_data.get("current_menu", [])
    if selection not in current_menu_in_session:
        print(f"ERROR in /menus: Selection '{selection}' not found in current menu: {current_menu_in_session}")
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_SELECTION", "message": f"Selection '{selection}' is not a valid option in the current menu."}})

    # 3. Retrieve necessary info from session
    max_menu_depth = session_data.get("max_menu_depth")
    topic = session_data.get("topic", "Unknown Topic")
    current_history = session_data.get("history", [])

    # Validate max_menu_depth exists
    if max_menu_depth is None or not isinstance(max_menu_depth, int):
         print(f"ERROR in /menus: max_menu_depth missing or invalid in session data for session '{session_id}'.")
         raise HTTPException(status_code=500, detail={"error": {"code": "INTERNAL_SERVER_ERROR", "message": "Session state is missing menu depth information."}})

    # Calculate current level based on history length
    current_level = len(current_history) # Level 1 = topic only, Level 2 = first selection done, etc.
    print(f"--- Current Level: {current_level}, Max Depth: {max_menu_depth} ---")

    response = None # Initialize response variable

    # 4. Determine action based on level vs max_depth
    try:
        if current_level < max_menu_depth:
            # Generate Submenu: We haven't reached the max depth yet
            print(f"--- Generating AI submenu (Level {current_level + 1}) for selection: '{selection}' ---")
            if not openai_client: raise ConnectionAbortedError("OpenAI client not available for submenu.") # Raise specific error

            # Call AI for submenu items
            submenu_items = generate_submenu_with_ai(topic, selection)
            if not submenu_items: raise ValueError("AI submenu generation returned empty list")

            # Update session state
            new_history = current_history + [("menu_selection", selection)]
            session_data["history"] = new_history
            session_data["current_menu"] = submenu_items
            sessions[session_id] = session_data
            print(f"--- Session '{session_id}' updated. Submenu generated (Level {current_level+1}). ---")

            # Prepare response
            response = MenuResponse(type="submenu", menu_items=submenu_items, content_markdown=None)

        elif current_level >= max_menu_depth:
            # Generate Content: Reached or exceeded max depth for menus.
            print(f"--- Generating AI content (Level {current_level + 1}) for selection: '{selection}' ---")
            if not openai_client: raise ConnectionAbortedError("OpenAI client not available for content.") # Raise specific error

            # Construct the path of *selections only* for context
            selection_path = [item[1] for item in current_history if item[0] == 'menu_selection'] + [selection]

            # Call AI for content and further topics
            content_markdown, further_topics = generate_content_and_further_topics(topic, selection_path)
            if not content_markdown or not further_topics:
                 raise ValueError("AI content generation returned empty content or further topics")

            # Update session state
            new_history = current_history + [("menu_selection", selection)] # Append current selection
            session_data["history"] = new_history
            session_data["current_menu"] = further_topics # Next menu shows further topics
            sessions[session_id] = session_data
            print(f"--- Session '{session_id}' updated. AI Content generated (Level {current_level+1}). ---")

            # Prepare response
            response = MenuResponse(type="content", menu_items=further_topics, content_markdown=content_markdown)

    # Handle potential AI and other errors from the try block
    except (ConnectionRefusedError, ConnectionAbortedError, ConnectionError, RuntimeError, ValueError) as e:
        status_code = 503; error_code = "AI_GENERATION_FAILED"
        # Map specific errors to appropriate HTTP status codes
        if isinstance(e, ConnectionRefusedError): status_code, error_code = 401, "AI_AUTH_ERROR"
        elif isinstance(e, ConnectionAbortedError): status_code, error_code = 429, "AI_RATE_LIMIT" # Could be client unavailable too
        elif isinstance(e, ConnectionError): status_code, error_code = 504, "AI_CONNECTION_ERROR"
        elif isinstance(e, ValueError): status_code, error_code = 502, "AI_BAD_RESPONSE" # Includes JSON/parsing/validation errors
        elif isinstance(e, RuntimeError): status_code, error_code = 502, "AI_API_ERROR" # Includes other OpenAI API errors
        print(f"ERROR in /menus processing selection: {e}")
        raise HTTPException(status_code=status_code, detail={"error": {"code": error_code, "message": str(e)}})
    except Exception as e:
        # Catch any other unexpected errors during processing
        print(f"ERROR in /menus unexpected: {e}")
        raise HTTPException(status_code=500, detail={"error": {"code": "MENU_PROCESSING_FAILED", "message": "An unexpected server error occurred processing the menu selection."}})


    # 5. Return the prepared response if successful
    if response:
         return response
    else:
         # Safeguard: This should ideally not be reached if logic/exceptions are correct
         print(f"ERROR in /menus: Failed to generate a response for session '{session_id}', selection '{selection}'. Logic fell through.")
         raise HTTPException(status_code=500, detail={"error": {"code": "RESPONSE_GENERATION_FAILED", "message": "Server failed to generate a valid response for the menu selection."}})


# --- Uvicorn runner (for local development) ---
if __name__ == "__main__":
    # This block allows running the server directly using `python main.py`
    # Useful for local testing. Render uses the Procfile or Start Command instead.
    import uvicorn
    print("--- Starting Uvicorn server (likely for local testing) ---")
    # Load port from environment variable (e.g., set by Render) or default to 8000
    port = int(os.environ.get("PORT", 8000))
    # Run the FastAPI app using Uvicorn
    # reload=True automatically restarts the server when code changes (for development)
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)

