# Replace the existing /menus endpoint function with this one

@app.post("/menus", response_model=MenuResponse, status_code=200, summary="Process menu selection and get next items", tags=["Navigation"])
async def select_menu_item(menu_selection: MenuSelection):
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

    # --- NEW LOGIC using max_menu_depth ---
    # 3. Retrieve max_depth and calculate current level
    max_menu_depth = session_data.get("max_menu_depth")
    if max_menu_depth is None or not isinstance(max_menu_depth, int):
         # This shouldn't happen if /sessions worked correctly
         print(f"ERROR in /menus: max_menu_depth missing or invalid in session data for session '{session_id}'.")
         raise HTTPException(status_code=500, detail={"error": {"code": "INTERNAL_SERVER_ERROR", "message": "Session state is missing menu depth information."}})

    current_level = len(session_data.get("history", [])) # Level 1 = topic, Level 2 = first selection, etc.

    print(f"--- Current Level: {current_level}, Max Depth: {max_menu_depth} ---")

    response = None # Initialize response variable

    # 4. Determine action based on level vs max_depth
    if current_level < max_menu_depth:
        # Generate Submenu: We haven't reached the max depth yet
        print(f"--- Generating AI submenu (Level {current_level + 1}) for selection: '{selection}' ---")
        if not openai_client:
            print("ERROR in /menus: OpenAI client not available.")
            raise HTTPException(status_code=503, detail={"error": {"code": "AI_SERVICE_UNAVAILABLE", "message": "OpenAI client is not available to generate submenu."}})
        try:
            topic = session_data.get("topic", "Unknown Topic")
            # *** CALL AI FOR SUBMENU ***
            submenu_items = generate_submenu_with_ai(topic, selection)
            if not submenu_items:
                raise ValueError("AI submenu generation returned empty or invalid list")

            # Update session state *before* returning
            session_data["history"].append(("menu_selection", selection))
            session_data["current_menu"] = submenu_items
            sessions[session_id] = session_data
            print(f"--- Session '{session_id}' updated. Submenu generated (Level {current_level+1}). ---")

            # Prepare response
            response = MenuResponse(type="submenu", menu_items=submenu_items, content_markdown=None)

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

    elif current_level == max_menu_depth:
        # Generate Content (Placeholder): We've reached the max depth for menus
        print(f"--- Max depth reached. Generating placeholder content (Level {current_level + 1}) for selection: '{selection}' ---")

        # *** PLACEHOLDER LOGIC for Content Generation ***
        # (Later, this block would call a generate_content_and_further_topics AI function)
        placeholder_content = f"## {selection}\n\nThis is placeholder content for **{selection}** (within the topic '{session_data.get('topic')}').\n\nActual AI-generated content providing an overview would appear here based on the selection path."
        placeholder_further_topics = ["Dig Deeper: Aspect A", "Dig Deeper: Aspect B", "Related Concept"]

        # Update session state *before* returning
        session_data["history"].append(("menu_selection", selection))
        session_data["current_menu"] = placeholder_further_topics # Next menu shows "further topics"
        # Optionally store the generated content in session too if needed later?
        # session_data["last_content"] = placeholder_content
        sessions[session_id] = session_data
        print(f"--- Session '{session_id}' updated. Placeholder content generated (Level {current_level+1}). ---")

        # Prepare response
        response = MenuResponse(type="content", menu_items=placeholder_further_topics, content_markdown=placeholder_content)

    else: # current_level > max_menu_depth
        # Handle navigation beyond the intended depth
        # This might happen if user tries to interact after "content" is shown,
        # selecting a "further topic" - we haven't defined that flow yet.
        print(f"--- Navigation beyond max depth ({max_menu_depth}) attempted. Level {current_level}. ---")
        # Option 1: Raise "Not Implemented"
        raise HTTPException(status_code=501, detail={"error": {"code": "MAX_DEPTH_EXCEEDED", "message": f"Navigation beyond the maximum defined depth ({max_menu_depth}) is not implemented yet."}})
        # Option 2: Return a specific message (less disruptive for frontend?)
        # response = MenuResponse(type="error", menu_items=[], content_markdown=f"Error: Navigation beyond max depth ({max_menu_depth}) not implemented.")


    # 5. Return the prepared response (if successful)
    if response:
         return response
    else:
         # Should be unreachable if logic is correct and exceptions are raised, but as a safeguard:
         print(f"ERROR in /menus: Failed to generate a response for session '{session_id}', selection '{selection}'.")
         raise HTTPException(status_code=500, detail={"error": {"code": "RESPONSE_GENERATION_FAILED", "message": "Server failed to generate a valid response for the menu selection."}})
