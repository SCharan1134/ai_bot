import os
import sys
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

# --- Add parent directories to sys.path ---
# This allows the script to find the 'graph' module
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    sys.path.append(current_dir)
    sys.path.append(parent_dir)
except NameError:
    # __file__ is not defined in some environments (e.g., interactive notebooks)
    # We'll assume the script is run from the correct directory.
    current_dir = os.getcwd()
    sys.path.append(current_dir)
    sys.path.append(os.path.dirname(current_dir))


# --- Import LangChain and Graph components ---
try:
    from langchain_core.messages import HumanMessage
    from graph.main_graph import supervisor_prebuilt
    print("✅ Successfully imported supervisor and LangChain components.")
except ImportError as e:
    print(f"❌ Error importing supervisor: {e}")
    print("Please ensure the 'graph/main_graph.py' file exists and all dependencies are installed.")
    sys.exit(1)


# --- FastAPI App Initialization ---
app = FastAPI(
    title="Multi-Agent Technical Support Assistant API",
    description="An API to interact with a LangChain multi-agent supervisor for technical support.",
    version="1.0.0",
)

# --- CORS (Cross-Origin Resource Sharing) Middleware ---
# This allows your frontend (running on a different domain/port) to communicate with this backend.
# For development, we allow all origins. For production, you should restrict this to your frontend's domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)


# --- Pydantic Models for Request and Response ---
# These models define the expected data structure for API requests and responses.
# They provide automatic data validation and documentation.

class ChatRequest(BaseModel):
    """Request model for the /chat endpoint."""
    question: str
    thread_id: Optional[str] = None

class ChatResponse(BaseModel):
    """Response model for the /chat endpoint."""
    answer: str
    thread_id: str


# --- API Endpoint for Chatting ---
@app.post("/chat", response_model=ChatResponse)
async def chat_with_agent(request: ChatRequest):
    """
    Receives a question, processes it with the supervisor agent, and returns the response.
    """
    try:
        # Use the provided thread_id or create a new one for a new conversation
        thread_id = request.thread_id or uuid.uuid4().hex
        
        # Configuration for the LangChain graph invocation
        config = {"configurable": {"thread_id": thread_id}}
        
        # The state to be passed to the agent, containing the user's message
        state = {"messages": [HumanMessage(content=request.question)]}
        
        print(f"🤖 Processing request for thread: {thread_id}...")
        
        # Invoke the supervisor agent with the state and config
        result = supervisor_prebuilt.invoke(state, config=config)
        
        # Extract the last message from the agent's response
        # The response is a list of messages, and we typically want the last one.
        if "messages" in result and result["messages"]:
            # The last message is the final answer from the agent
            last_message = result["messages"][-1]
            answer = last_message.content
        else:
            # Handle cases where no response is generated
            answer = "Sorry, I could not process your request. No response was generated."
            
        print(f"✅ Successfully processed request for thread: {thread_id}")

        # Return the answer and thread_id to the client
        return ChatResponse(answer=answer, thread_id=thread_id)

    except Exception as e:
        # Log the error for debugging purposes
        import traceback
        print(f"❌ Error processing request: {e}")
        traceback.print_exc()
        # Raise an HTTPException, which FastAPI will convert into a proper HTTP error response
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {e}")


# --- Root Endpoint for Health Check ---
@app.get("/")
def read_root():
    """
    A simple health check endpoint to confirm the API is running.
    """
    return {"status": "ok", "message": "Welcome to the Technical Support Assistant API"}


# --- How to run the server ---
# To run this FastAPI application, save the code as `api.py` and run the following command in your terminal:
# uvicorn api:app --reload
#
# - `uvicorn`: The ASGI server that runs the application.
# - `api`: The name of your Python file (api.py).
# - `app`: The FastAPI instance you created (`app = FastAPI()`).
# - `--reload`: Automatically restarts the server when you make changes to the code.
#
# The API will be available at http://127.0.0.1:8000
# You can access the interactive API documentation at http://127.0.0.1:8000/docs
