from fastapi import FastAPI
import uvicorn
import os
# We'll add more imports later (openai, uuid, dotenv, etc.)

# Initialize FastAPI app
app = FastAPI(
    title="AI Subject Explorer Backend",
    description="API for the AI Subject Explorer.",
    version="0.1.0",
)

# --- Placeholder for In-Memory Session Store (Add later) ---
# sessions = {}

# --- Basic Root Endpoint (for testing if server runs) ---
@app.get("/")
async def read_root():
    """ Basic endpoint to check if the API is running. """
    return {"message": "AI Subject Explorer Backend is alive!"}

# --- API Endpoints (/sessions, /menus) will be added below here ---


# --- Uvicorn runner for local development ---
# Note: Render uses the Start Command specified in its settings, not this block.
# You would typically run from terminal: uvicorn app.main:app --reload --port 8000
if __name__ == "__main__":
    print("Attempting to run Uvicorn server for local testing...")
    # Default port for Render web services, or choose another like 8000
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
