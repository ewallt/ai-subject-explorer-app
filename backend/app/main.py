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

class MenuSelection(BaseModel):
    session_id: str
    selection: str

class MenuResponse(BaseModel):
    type: Literal["submenu", "content"]
    menu_items: Optional[List[str]] = None # Items for submenu, or further exploration topics for content
    content: Optional[str] = None # Markdown content (only when type is "content")
    session_id: str # Always include session_id
    current_depth: int # Depth of the *current* response (0 for initial menu, 1 for first submenu/content, etc.)
    max_menu_depth: int # Max depth threshold for *initial* menu->content transition

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
        # print("--- BACKEND CODE VERSION: FURTHER_EXPLORE_V1 ---") # Example marker
except Exception as e:
    print(f"ERROR: Failed to initialize OpenAI client: {e}")
    openai_client = None

# Initialize FastAPI app
app = FastAPI(title="AI Subject Explorer Backend", version="0.4.0") # Version bump

# --- CORS Middleware Configuration ---
origins = [
    "https://ai-subject-explorer-app-frontend.onrender.com",
    # Add local dev URLs if needed
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,      # Use the specific list
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- In-Memory Session Storage ---
# Structure: session_id -> { topic, history, current_menu, max_menu_depth, current_depth, last_content }
sessions: Dict[str, Dict[str, Any]] = {}

# --- AI Call Functions ---

# generate_main_menu_with_ai function (Already updated for dynamic depth)
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
Choose a depth between 2 and 4 (inclusive) that seems appropriate for the complexity of the topic '{topic}'.""" # Removed the "ALWAYS return 2" constraint

    json_format_instruction = """Return ONLY a valid JSON object containing two keys:
1.  "categories": A list of strings representing the main menu categories.
2.  "max_menu_depth": An integer representing the determined maximum depth (must be between 2 and 4).

Example response:
{
  "categories": ["Overview", "History", "Key Aspects", "Future Trends"],
  "max_menu_depth": 3
}""" # Updated example depth

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
                # Optional: Add check for reasonable range (e.g., 1 to 5) if desired
                if max_depth < 1: # Ensure it's at least 1 (or 2 based on prompt)
                    print(f"WARNING: AI returned invalid max_menu_depth={max_depth}. Defaulting to 2.")
                    max_depth = 2
            # Removed the strict check/warning that forced depth to 2
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

# generate_submenu_with_ai function (Unchanged)
def generate_submenu_with_ai(topic: str, category_selection: str) -> List[str]:
    """ Generates submenu items using OpenAI API based on topic and category. """
    if not openai_client:
        print("ERROR: OpenAI client not available for submenu generation.")
        return [f"Subtopic 1 for {category_selection}", f"Subtopic 2 for {category_selection}"]

    print(f"--- Calling OpenAI (gpt-4.1-nano) for submenu: Topic='{topic}', Category='{category_selection}' ---")
    model_name = "gpt-4.1-nano"
    system_prompt = f"""You are an assistant designing a hierarchical exploration menu for the main topic '{topic}'.
Given the selected category '{category_selection}', generate a list of 3 to 7 specific, relevant subtopics within that category.
Return ONLY a valid JSON object containing a single key "subtopics" which holds a list of strings. Example response:
{{
  "subtopics": ["Subtopic 1", "Subtopic 2", "Subtopic 3"]
}}"""
    user_prompt = f"Generate subtopics for Category: {category_selection}" # Adjusted user prompt slightly

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

# --- AI Content Generation Function ---
def generate_content_and_further_topics_with_ai(topic: str, history: List[Tuple[str, str]], selection: str) -> Tuple[str, List[str]]:
    """
    Generates Markdown content and further exploration topics using OpenAI
    based on the full navigation path.
    Returns a tuple: (markdown_content, list_of_further_topics).
    """
    if not openai_client:
        print("ERROR: OpenAI client not available for content generation.")
        fallback_content = f"## {selection}\n\n(Fallback Content due to OpenAI client issue)\n\nDetails about {selection} within the context of {topic} would appear here."
        fallback_topics = ["Related Topic A", "Related Topic B", "Go Deeper"]
        return (fallback_content, fallback_topics)

    # Construct the navigation path string for context
    path_list = [item[1] for item in history if item[0] == 'menu_selection'] + [selection]
    navigation_path = f"{topic} -> " + " -> ".join(path_list)

    print(f"--- Calling OpenAI (gpt-4.1-nano) for content: Path='{navigation_path}' ---")
    model_name = "gpt-4.1-nano"

    system_prompt = f"""You are an expert assistant providing concise information based on a user's exploration path.
The user started exploring the main topic '{topic}' and navigated through the following path: '{navigation_path}'.

Your tasks are:
1. Generate a brief (2-4 paragraphs) **Markdown summary** about the final item: '{selection}'. This summary should be relevant to its context within the navigation path provided. Use standard Markdown formatting (headings, lists, bold, italics where appropriate).
2. Generate a list of 3-5 distinct and relevant **"further exploration" topic suggestions** related to '{selection}' and its context. These should entice the user to learn more or explore related concepts.

Return ONLY a valid JSON object containing two keys:
1.  "content_markdown": A string containing the generated Markdown summary.
2.  "further_topics": A list of strings representing the further exploration topic suggestions.

Example JSON response format:
{{
  "content_markdown": "## {selection}\\n\\nThis section provides an overview of {selection}...",
  "further_topics": ["Related Concept X", "Deeper Dive into Y", "Historical Context of Z"]
}}"""

    user_prompt = f"Generate content and further topics for the final selection '{selection}' based on the path: {navigation_path}"

    try:
        completion = openai_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=500, # Allow more tokens for content generation
            temperature=0.7, # Slightly higher temperature for more creative content/topics
            response_format={"type": "json_object"}
        )
        content_raw = completion.choices[0].message.content
        print(f"--- OpenAI Raw Content/Further Topics Response: {content_raw} ---")
        if not content_raw: raise ValueError("OpenAI returned empty content for content/further topics.")

        try:
            parsed_data = json.loads(content_raw)
            generated_content = ""
            further_topics = []

            # Validate and parse "content_markdown"
            # Renaming key in code to match Pydantic model 'content'
            if isinstance(parsed_data, dict) and "content_markdown" in parsed_data and isinstance(parsed_data["content_markdown"], str) and parsed_data["content_markdown"].strip():
                generated_content = parsed_data["content_markdown"].strip()
            else: raise ValueError("AI response JSON structure incorrect or missing valid 'content_markdown' string.")

            # Validate and parse "further_topics"
            if isinstance(parsed_data, dict) and "further_topics" in parsed_data and isinstance(parsed_data["further_topics"], list):
                further_topics = [str(item).strip() for item in parsed_data["further_topics"] if isinstance(item, str) and item.strip()]
                if not further_topics: raise ValueError("Parsed JSON ok, but 'further_topics' list was empty or invalid.")
            else: raise ValueError("AI response JSON structure incorrect or missing 'further_topics' list.")

            print(f"--- Parsed Content (Markdown): {generated_content[:100]}... ---") # Log snippet
            print(f"--- Parsed Further Topics: {further_topics} ---")
            return (generated_content, further_topics) # Return name 'generated_content' aligns with pydantic model 'content'

        except json.JSONDecodeError: raise ValueError("AI content/further topics response was not valid JSON.")
        except ValueError as ve: raise ve
        except Exception as parse_err: raise ValueError(f"Could not process AI content/further topics response structure: {parse_err}")

    except openai.AuthenticationError as e: raise ConnectionRefusedError(f"OpenAI authentication failed. Check API key. {e}")
    except openai.RateLimitError as e: raise ConnectionAbortedError(f"OpenAI rate limit hit. {e}")
    except openai.APIConnectionError as e: raise ConnectionError(f"Could not connect to OpenAI: {e}")
    except openai.APIError as e: raise RuntimeError(f"OpenAI returned an API error: {e}")
    except Exception as e: raise RuntimeError(f"Unexpected error during AI content/further topics generation: {e}")

# --- API Endpoints ---

@app.get("/")
async def read_root():
    return {"message": "AI Subject Explorer Backend is alive!"}

# /sessions endpoint (Unchanged logic, returns updated MenuResponse)
@app.post("/sessions", response_model=MenuResponse, status_code=201, summary="Start a new exploration session", tags=["Session Management"])
async def create_session(topic_input: TopicInput):
    session_id = str(uuid.uuid4())
    topic = topic_input.topic
    print(f"--- Received POST /sessions request for topic: '{topic}' ---")

    if not openai_client:
        raise HTTPException(status_code=503, detail={"error": {"code": "AI_SERVICE_UNAVAILABLE", "message": "OpenAI client is not initialized."}})

    try:
        main_menu_items, max_menu_depth = generate_main_menu_with_ai(topic)
        if not main_menu_items: raise ValueError("AI menu generation returned empty/invalid list")
    except (ConnectionRefusedError, ConnectionAbortedError, ConnectionError, RuntimeError, ValueError) as e:
        status_code = 503; error_code = "AI_GENERATION_FAILED"; msg=str(e)
        if isinstance(e, ConnectionRefusedError): status_code, error_code = 401, "AI_AUTH_ERROR"
        elif isinstance(e, ConnectionAbortedError): status_code, error_code = 429, "AI_RATE_LIMIT"
        elif isinstance(e, ConnectionError): status_code, error_code = 504, "AI_CONNECTION_ERROR"
        elif isinstance(e, ValueError): status_code, error_code = 502, "AI_BAD_RESPONSE"
        print(f"ERROR in /sessions calling AI: {msg}")
        raise HTTPException(status_code=status_code, detail={"error": {"code": error_code, "message": msg}})
    except Exception as e:
        print(f"ERROR in /sessions unexpected: {e}")
        raise HTTPException(status_code=500, detail={"error": {"code": "SESSION_CREATION_FAILED", "message": "An unexpected error occurred."}})

    initial_depth = 0
    sessions[session_id] = {
        "topic": topic,
        "history": [("topic", topic)],
        "current_menu": main_menu_items,
        "max_menu_depth": max_menu_depth,
        "current_depth": initial_depth,
        "last_content": None # Initialize last_content
    }
    print(f"--- Session '{session_id}' created. Max depth={max_menu_depth}. Current Depth={initial_depth}. State stored. ---")

    # Return updated MenuResponse model
    return MenuResponse(
        type="submenu", menu_items=main_menu_items, content=None,
        session_id=session_id, current_depth=initial_depth, max_menu_depth=max_menu_depth
    )

# --- MODIFIED /menus endpoint ---
@app.post("/menus", response_model=MenuResponse, status_code=200, summary="Process menu selection and get next items/content", tags=["Navigation"])
async def select_menu_item(menu_selection: MenuSelection):
    session_id = menu_selection.session_id
    selection = menu_selection.selection
    print(f"--- Received POST /menus request for session '{session_id}', selection: '{selection}' ---")

    if session_id not in sessions:
        print(f"ERROR in /menus: Session ID '{session_id}' not found.")
        raise HTTPException(status_code=404, detail={"error": {"code": "SESSION_NOT_FOUND", "message": "Session ID not found."}})
    session_data = sessions[session_id]

    current_menu = session_data.get("current_menu", [])
    if selection not in current_menu:
        # Allow retrying last selection if menu is empty but content exists (edge case?)
        if not current_menu and session_data.get("last_content"):
             print(f"WARNING in /menus: Selection '{selection}' not in empty menu, but content exists. Allowing proceed.")
        else:
             print(f"ERROR in /menus: Selection '{selection}' not found in current menu: {current_menu}")
             raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_SELECTION", "message": f"Selection '{selection}' is not valid."}})

    max_menu_depth = session_data.get("max_menu_depth")
    current_depth = session_data.get("current_depth", -1)
    next_depth = current_depth + 1

    if max_menu_depth is None or current_depth == -1:
         print(f"ERROR in /menus: Depth info missing/invalid. MaxDepth: {max_menu_depth}, CurrentDepth: {current_depth}")
         raise HTTPException(status_code=500, detail={"error": {"code": "INTERNAL_SERVER_ERROR", "message": "Session state missing depth info."}})

    print(f"--- Request transition from depth {current_depth} to {next_depth}. Max Depth Threshold: {max_menu_depth} ---")

    response = None
    topic = session_data.get("topic", "Unknown Topic")
    history = session_data.get("history", []) # Get history *before* potentially adding current selection

    try: # Wrap primary logic in try block to catch AI errors uniformly
        if next_depth < max_menu_depth:
            # Generate Submenu
            print(f"--- Generating AI submenu (Target Depth {next_depth}) for selection: '{selection}' ---")
            submenu_items = generate_submenu_with_ai(topic, selection) # Can raise exceptions

            session_data["history"].append(("menu_selection", selection))
            session_data["current_menu"] = submenu_items
            session_data["current_depth"] = next_depth
            session_data["last_content"] = None # Clear content when showing submenu
            sessions[session_id] = session_data # Update session
            print(f"--- Session '{session_id}' updated. Submenu generated (Reached Depth {next_depth}). ---")

            response = MenuResponse(
                type="submenu", menu_items=submenu_items, content=None,
                session_id=session_id, current_depth=next_depth, max_menu_depth=max_menu_depth
            )

        elif next_depth == max_menu_depth:
            # Generate Initial Content
            print(f"--- Max depth threshold reached. Generating AI content (Target Depth {next_depth}) for selection: '{selection}' ---")
            generated_content, further_topics = generate_content_and_further_topics_with_ai(topic, history, selection) # Can raise exceptions

            session_data["history"].append(("menu_selection", selection))
            session_data["current_menu"] = further_topics # Next menu shows further topics
            session_data["current_depth"] = next_depth
            session_data["last_content"] = generated_content # Store the generated content
            sessions[session_id] = session_data # Update session
            print(f"--- Session '{session_id}' updated. AI content generated (Reached Depth {next_depth}). ---")

            response = MenuResponse(
                type="content", menu_items=further_topics, content=generated_content,
                session_id=session_id, current_depth=next_depth, max_menu_depth=max_menu_depth
            )

        else: # next_depth > max_menu_depth
            # *** MODIFIED BLOCK: Generate Further Content ***
            print(f"--- Generating AI content for further exploration (Target Depth {next_depth}) for selection: '{selection}' ---")
            # Call the same content generation function again
            generated_content, further_topics = generate_content_and_further_topics_with_ai(topic, history, selection) # Can raise exceptions

            session_data["history"].append(("menu_selection", selection))
            session_data["current_menu"] = further_topics # Next menu shows *new* further topics
            session_data["current_depth"] = next_depth # Update depth
            session_data["last_content"] = generated_content # Store the new content
            sessions[session_id] = session_data # Update session
            print(f"--- Session '{session_id}' updated. Further AI content generated (Reached Depth {next_depth}). ---")

            response = MenuResponse(
                type="content", # Still content type
                menu_items=further_topics,
                content=generated_content,
                session_id=session_id,
                current_depth=next_depth, # Return the new depth
                max_menu_depth=max_menu_depth # Max depth threshold remains the same
            )
            # *** END MODIFIED BLOCK ***

    # Centralized Error Handling for AI calls within /menus
    except (ConnectionRefusedError, ConnectionAbortedError, ConnectionError, RuntimeError, ValueError) as e:
        status_code = 503; error_code = "AI_GENERATION_FAILED"; msg = str(e)
        if isinstance(e, ConnectionRefusedError): status_code, error_code = 401, "AI_AUTH_ERROR"
        elif isinstance(e, ConnectionAbortedError): status_code, error_code = 429, "AI_RATE_LIMIT"
        elif isinstance(e, ConnectionError): status_code, error_code = 504, "AI_CONNECTION_ERROR"
        elif isinstance(e, ValueError): status_code, error_code = 502, "AI_BAD_RESPONSE"
        print(f"ERROR in /menus calling AI: {msg}");
        raise HTTPException(status_code=status_code, detail={"error": {"code": error_code, "message": msg}})
    except Exception as e:
        print(f"ERROR in /menus unexpected during generation: {e}");
        raise HTTPException(status_code=500, detail={"error": {"code": "RESPONSE_GENERATION_FAILED", "message": "An unexpected server error occurred."}})

    # Return the prepared response if successful
    if response:
         return response
    else:
         # Should not happen if logic is correct, but safeguard
         print(f"ERROR in /menus: Failed to generate response logic path for session '{session_id}', selection '{selection}'.")
         raise HTTPException(status_code=500, detail={"error": {"code": "RESPONSE_LOGIC_ERROR", "message": "Server logic failed to produce a response."}})


# --- Uvicorn runner ---
if __name__ == "__main__":
    import uvicorn
    print("--- Starting Uvicorn server (likely for local testing) ---")
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
