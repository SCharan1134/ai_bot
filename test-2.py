import asyncio
import getpass
import os
import json
from datetime import datetime
from typing import List, Literal, Optional, Annotated, TypedDict
import uuid

from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.graph.message import add_messages
from langchain.chat_models import init_chat_model
from dotenv import load_dotenv

load_dotenv()

# Use environment variables with fallbacks (remove hardcoded keys)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_SHEETS_API_KEY = os.getenv("GOOGLE_SHEETS_API_KEY")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")

os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY

class GraphState(TypedDict):
    """Represents the state of our graph."""
    messages: Annotated[list, add_messages]
    entities: Optional[dict]
    tool_outputs: Optional[list]
    generation: Optional[str]

def query_google_sheets(sheet_name: str, range_name: str = "A:Z") -> list:
    """Query data from a specific sheet in Google Sheets."""
    try:
        service = build('sheets', 'v4', developerKey=GOOGLE_SHEETS_API_KEY)
        sheet = service.spreadsheets()
        result = sheet.values().get(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=f"{sheet_name}!{range_name}"
        ).execute()
        
        values = result.get('values', [])
        if not values or len(values) < 2:
            print(f"⚠️ No data or only headers found in sheet: {sheet_name}")
            return []

        headers = values[0]
        data = [dict(zip(headers, row + [''] * (len(headers) - len(row)))) for row in values[1:]]
        print(f"✅ Successfully parsed {len(data)} rows from {sheet_name}")
        return data
    except HttpError as e:
        print(f"❌ HTTP Error querying sheet {sheet_name}: {e}")
        return []
    except Exception as e:
        print(f"❌ Unexpected error querying sheet {sheet_name}: {e}")
        return []
    
class ErrorSearchArgs(BaseModel):
    machine: Optional[str] = Field(description="The name of the machine, e.g., MASTERFOLD, NOVACUT.")
    error_code: str = Field(description="The error code to look up, e.g., E-352, ERR-123.")

@tool(args_schema=ErrorSearchArgs)
def search_error_codes(machine: Optional[str], error_code: str) -> list:
    """Searches the 'error_codes' sheet for information about a specific error on a machine."""
    data = query_google_sheets("error_codes")
    results = [
        row for row in data 
        if (not machine or machine.upper() in row.get('machine', '').upper()) and \
           (error_code.upper() in row.get('code', '').upper())
    ]
    print(f"🔍 Error code tool found {len(results)} matches.")
    return results

class PartSearchArgs(BaseModel):
    machine: Optional[str] = Field(description="The name of the machine, e.g., MASTERFOLD.")
    part_name: Optional[str] = Field(description="The name or code of the spare part.")
    keywords: Optional[List[str]] = Field(description="Keywords related to the part or its function.")

@tool(args_schema=PartSearchArgs)
def search_spare_parts(machine: Optional[str], part_name: Optional[str], keywords: Optional[List[str]]) -> list:
    """Searches the 'spare_parts' sheet for available parts based on name, code, or keywords."""
    data = query_google_sheets("spare_parts")
    results = []
    for row in data:
        match_machine = not machine or machine.upper() in row.get('machine', '').upper()
        match_part = not part_name or part_name.upper() in row.get('name', '').upper() or part_name.upper() in row.get('part_code', '').upper()
        
        keyword_text = f"{row.get('name', '')} {row.get('description', '')}".upper()
        match_keywords = not keywords or any(k.upper() in keyword_text for k in keywords)

        if match_machine and (match_part or match_keywords):
            results.append(row)
            
    print(f"🔍 Spare parts tool found {len(results)} matches.")
    return results

class MaintenanceSearchArgs(BaseModel):
    machine: str = Field(description="The name of the machine to get maintenance info for.")

@tool(args_schema=MaintenanceSearchArgs)
def search_maintenance_info(machine: str) -> list:
    """Searches the 'maintenance' sheet for procedures and schedules for a specific machine."""
    data = query_google_sheets("maintenance")
    results = [
        row for row in data
        if machine.upper() in row.get('machine', '').upper()
    ]
    print(f"🔍 Maintenance tool found {len(results)} matches.")
    return results

class Entities(BaseModel):
    """The entities extracted from the user's message."""
    intent: Literal["error_lookup", "spare_part_search", "maintenance_info", "general_help"] = Field(
        description="The user's primary goal."
    )
    machine: Optional[str] = Field(None, description="The machine name mentioned, e.g., MASTERFOLD.")
    error_code: Optional[str] = Field(None, description="The error code mentioned, e.g., E-352. Standardize by adding '-' if missing.")
    part_name: Optional[str] = Field(None, description="The part name or code mentioned.")
    keywords: Optional[List[str]] = Field(None, description="Other important keywords from the message.")

def extract_entities_node(state: GraphState) -> dict:
    """Extracts intent and entities from the user message to decide the next step."""
    print("---NODE: EXTRACT ENTITIES---")
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert at analyzing messages from machine technicians. Your goal is to extract key information and determine the user's intent. Respond ONLY with the requested JSON object."),
        ("human", "Analyze the following message: '{message}'")
    ])
    
    try:
        # Try different initialization methods for compatibility
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro", 
            temperature=0.1,
            google_api_key=GEMINI_API_KEY
        )
    except Exception as e:
        print(f"Error initializing ChatGoogleGenerativeAI: {e}")
        # Fallback to a simple rule-based entity extraction
        user_message = state["messages"][-1].content.lower()
        
        # Simple rule-based intent detection
        if any(keyword in user_message for keyword in ["error", "e-", "err-"]):
            intent = "error_lookup"
        elif any(keyword in user_message for keyword in ["part", "spare", "component"]):
            intent = "spare_part_search"
        elif any(keyword in user_message for keyword in ["maintenance", "service", "schedule"]):
            intent = "maintenance_info"
        else:
            intent = "general_help"
            
        # Extract machine name (simple pattern matching)
        machine = None
        for word in user_message.split():
            if word.upper() in ["MASTERFOLD", "NOVACUT", "BOBST"]:
                machine = word.upper()
                break
                
        # Extract error code (simple pattern)
        error_code = None
        import re
        error_match = re.search(r'e-?\d+|err-?\d+', user_message, re.IGNORECASE)
        if error_match:
            error_code = error_match.group().upper()
            if '-' not in error_code and error_code.startswith('E'):
                error_code = error_code[0] + '-' + error_code[1:]
        
        extracted_data = {
            "intent": intent,
            "machine": machine,
            "error_code": error_code,
            "part_name": None,
            "keywords": None
        }
        print(f"Extracted entities (fallback): {extracted_data}")
        return {"entities": extracted_data}
    
    # Use structured_output to get a reliable Pydantic object
    extractor: Runnable[dict, Entities] = prompt | llm.with_structured_output(Entities)
    
    user_message = state["messages"][-1].content
    try:
        extracted_data = extractor.invoke({"message": user_message})
        print(f"Extracted entities: {extracted_data.dict()}")
        return {"entities": extracted_data.dict()}
    except Exception as e:
        print(f"Error in entity extraction: {e}")
        # Fallback to general help
        return {"entities": {"intent": "general_help"}}

def call_tools_node(state: GraphState) -> dict:
    """Calls the appropriate tools based on the extracted entities."""
    print("---NODE: CALL TOOLS---")
    entities = state["entities"]
    intent = entities["intent"]
    tool_outputs = []
    
    try:
        if intent == "error_lookup":
            if entities.get("error_code"):
                results = search_error_codes(entities.get("machine"), entities["error_code"])
                tool_outputs.extend(results)
        
        elif intent == "spare_part_search":
            results = search_spare_parts(
                entities.get("machine"), 
                entities.get("part_name"), 
                entities.get("keywords")
            )
            tool_outputs.extend(results)
            
        elif intent == "maintenance_info":
            if entities.get("machine"):
                results = search_maintenance_info(entities["machine"])
                tool_outputs.extend(results)
    
    except Exception as e:
        print(f"Error calling tools: {e}")
        tool_outputs = []
    
    print(f"Tool outputs collected: {len(tool_outputs)} items")
    return {"tool_outputs": tool_outputs}

def generate_response_node(state: GraphState) -> dict:
    """Generates a final, user-facing response based on the collected data."""
    print("---NODE: GENERATE RESPONSE---")
    user_message = state["messages"][-1].content
    entities = state["entities"]
    tool_outputs = state.get("tool_outputs", [])

    if not tool_outputs:
        response_text = "I couldn't find any information matching your request. Please try rephrasing, check the spelling of the machine name, or verify the error code format. If you need further help, please contact technical support."
        return {"generation": response_text}

    # Try to use LLM for response generation, with fallback
    try:
        # Prepare data for the prompt
        context = "\n\n".join([json.dumps(output) for output in tool_outputs])
        
        prompt = ChatPromptTemplate.from_template(
            """You are a helpful Bobst machine support assistant.
            
            A user asked the following question:
            "{user_message}"
            
            Based on their question, we determined their intent was '{intent}' and found the following relevant data from our knowledge base:
            <DATA>
            {context}
            </DATA>
            
            Please synthesize this information into a clear, concise, and helpful response for the user.
            - Directly answer their question.
            - Use the provided data to support your answer.
            - If applicable, suggest the next logical step for the technician.
            - Format the response for readability (e.g., use bullet points).
            """
        )
        
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro", 
            temperature=0.1,
            google_api_key=GEMINI_API_KEY
        )
        chain = prompt | llm
        
        response = chain.invoke({
            "user_message": user_message,
            "intent": entities.get("intent"),
            "context": context
        })
        
        print(f"Generated response: {response.content}")
        return {"generation": response.content}
        
    except Exception as e:
        print(f"Error generating LLM response: {e}")
        # Fallback to simple response formatting
        intent = entities.get("intent", "unknown")
        response_parts = [f"Based on your {intent} request, I found the following information:"]
        
        for i, output in enumerate(tool_outputs[:5], 1):  # Limit to first 5 results
            response_parts.append(f"\n{i}. {json.dumps(output, indent=2)}")
            
        if len(tool_outputs) > 5:
            response_parts.append(f"\n... and {len(tool_outputs) - 5} more results.")
            
        response_text = "\n".join(response_parts)
        print(f"Generated fallback response")
        return {"generation": response_text}

def general_help_node(state: GraphState) -> dict:
    """Provides a static help message."""
    print("---NODE: GENERAL HELP---")
    return {"generation": """
I'm your Bobst machine assistant! I can help you with:

🔧 **Error Codes**: Ask about specific error codes (e.g., "What's error E-352 on MASTERFOLD?")
⚙️ **Spare Parts**: Search for parts (e.g., "Need folding blade for NOVACUT")
📅 **Maintenance**: Check maintenance schedules (e.g., "When is next maintenance for MASTERFOLD?")
            
How can I assist you today?
"""}

def route_after_extraction(state: GraphState) -> str:
    """Routes to the correct node based on intent."""
    intent = state["entities"]["intent"]
    print(f"---ROUTING based on intent: {intent}---")
    if intent == "general_help":
        return "general_help"
    else:
        return "call_tools"

# Define the workflow
workflow = StateGraph(GraphState)

workflow.add_node("extract_entities", extract_entities_node)
workflow.add_node("call_tools", call_tools_node)
workflow.add_node("generate_response", generate_response_node)
workflow.add_node("general_help", general_help_node)

# Define the edges and control flow
workflow.set_entry_point("extract_entities")
workflow.add_conditional_edges(
    "extract_entities",
    route_after_extraction,
    {
        "call_tools": "call_tools",
        "general_help": "general_help",
    },
)
workflow.add_edge("call_tools", "generate_response")
workflow.add_edge("generate_response", END)
workflow.add_edge("general_help", END)

in_memory_store = InMemoryStore()
checkpointer = MemorySaver()

graph = workflow.compile(
    name="bobst_machine_assistant",
    checkpointer=checkpointer,
    store=in_memory_store,
)

print("\nbobst_machine_assistant Workflow Graph:")
# Removed dependency on utils.show_graph - implement inline or remove
try:
    print("Graph compiled successfully!")
except Exception as e:
    print(f"Graph visualization not available: {e}")

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Simple HTML template inline instead of file dependency
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Bobst Machine Assistant</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        #chat { border: 1px solid #ccc; height: 400px; overflow-y: scroll; padding: 10px; margin-bottom: 10px; }
        #input { width: 80%; padding: 5px; }
        #send { padding: 5px 10px; }
        .message { margin: 5px 0; }
        .user { color: blue; }
        .bot { color: green; }
    </style>
</head>
<body>
    <h1>Bobst Machine Assistant</h1>
    <div id="chat"></div>
    <input type="text" id="input" placeholder="Ask about error codes, spare parts, or maintenance...">
    <button id="send">Send</button>
    
    <script>
        const chat = document.getElementById('chat');
        const input = document.getElementById('input');
        const sendBtn = document.getElementById('send');
        
        function addMessage(text, className) {
            const div = document.createElement('div');
            div.className = `message ${className}`;
            div.textContent = text;
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }
        
        function sendMessage() {
            const message = input.value.trim();
            if (!message) return;
            
            addMessage('You: ' + message, 'user');
            input.value = '';
            
            fetch('/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: message})
            })
            .then(response => response.json())
            .then(data => {
                addMessage('Bot: ' + data.reply, 'bot');
            })
            .catch(error => {
                addMessage('Error: ' + error.message, 'bot');
            });
        }
        
        sendBtn.addEventListener('click', sendMessage);
        input.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') sendMessage();
        });
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    """Serve the chat interface"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages using the LangGraph agent."""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        # A thread_id is needed to maintain conversation state
        thread_id = data.get('thread_id', 'default-thread')

        if not user_message:
            return jsonify({'error': 'Empty message'}), 400
            
        print(f"\n[{datetime.now()}] Processing message for thread '{thread_id}': {user_message}")

        # Define the input for the graph
        inputs = {"messages": [HumanMessage(content=user_message)]}
        # Define the configuration to use the correct conversation thread
        config = {"configurable": {"thread_id": thread_id}}

        # Invoke the graph
        final_state = None
        for event in graph.stream(inputs, config=config, stream_mode="values"):
            final_state = event
        
        # The final reply is in the 'generation' key of the last state
        bot_response = final_state.get('generation', "I'm sorry, I encountered an issue and couldn't generate a response.")
        
        return jsonify({'reply': bot_response, 'thread_id': thread_id})

    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        return jsonify({'reply': 'Sorry, an internal error occurred.'}), 500

async def run_interactive_agent():
    """Runs the main interactive loop for the agent."""
    print("\n--- Welcome to the Bobst Machine Assistant! Type 'exit' or 'quit' to end. ---\n")

    thread_id = uuid.uuid4().hex
    config = {"configurable": {"thread_id": thread_id}}

    while True:
        user_input = input("You: ")
        if user_input.strip().lower() in ["exit", "quit"]:
            print("Exiting the conversation. Goodbye!")
            break

        # Fixed: Use the correct GraphState structure
        graph_input = {
            "messages": [HumanMessage(content=user_input)]
        }

        print("\n--- Agent Thinking... ---")
        try:
            # Use the corrected input dictionary
            result = await graph.ainvoke(graph_input, config=config)

            # Extract and print the generation from the final state
            if generation := result.get("generation"):
                print(f"\nAgent:\n{generation}")
            else:
                print("\n(Graph run complete, but no response was generated.)")

        except Exception as e:
            print(f"\nAn error occurred: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        # Run in interactive mode
        asyncio.run(run_interactive_agent())
    else:
        # Run Flask web server
        print("🚀 Starting Bobst AI Assistant with LangGraph...")
        print("=" * 60)
        print("✅ Configuration loaded.")
        print("✅ LangGraph compiled with memory.")
        print("\n🌐 Server starting at: http://127.0.0.1:5000")
        print("=" * 60)
        app.run(host='0.0.0.0', port=5000, debug=False)