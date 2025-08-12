import uuid
from dotenv import load_dotenv
import os
import sys



# Load environment variables first
load_dotenv()

# Add current directory and parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(current_dir)
sys.path.append(parent_dir)

try:
    from tools.error_code import error_code_tools
    from Model.state import State
except ImportError as e:
    print(f"❌ Error importing error_code_tools: {e}")
    print("Make sure your file structure is correct and the tools module exists")
    sys.exit(1)

from langchain_google_genai import ChatGoogleGenerativeAI
import google.generativeai as genai
from langchain_core.messages import  HumanMessage

from typing_extensions import TypedDict
from typing import Annotated, Sequence
from langgraph.graph.message import  add_messages
from langchain_core.messages import BaseMessage
from langgraph.managed.is_last_step import RemainingSteps

from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from langgraph.prebuilt import create_react_agent

# Initialize long-term memory store for persistent data between conversations
in_memory_store = InMemoryStore()

# Initialize checkpointer for short-term memory within a single thread/conversation
checkpointer = MemorySaver()

load_dotenv()
# Get API key from environment
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("❌ Error: GOOGLE_API_KEY not found in environment variables")
    sys.exit(1)

os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# class State(TypedDict):
#     """
#     State schema for the multi-agent customer support workflow.
    
#     This defines the shared data structure that flows between nodes in the graph,
#     representing the current snapshot of the conversation and agent state.
#     """
#     # Conversation history with automatic message aggregation
#     messages: Annotated[Sequence[BaseMessage], add_messages]
    
#     # User preferences and context loaded from long-term memory store
#     loaded_memory: str
    
#     # Counter to prevent infinite recursion in agent workflow
#     remaining_steps: RemainingSteps

try:
    import google.generativeai as genai
    
    # Configure the Google AI client
    genai.configure(api_key=GOOGLE_API_KEY)
    
    # Initialize using the method that worked in our test
    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-pro",
        temperature=0.1,
    )
    print("✅ Successfully initialized Google Generative AI")
    
except Exception as e:
    print(f"❌ Error initializing Google Generative AI: {e}")
    sys.exit(1)

llm_with_search_tools = llm.bind_tools(error_code_tools)
error_code_tools = error_code_tools


error_code_prompt = """
You are a specialized technical support agent with expertise in industrial machine error code diagnosis and troubleshooting. Your primary mission is to help users quickly identify, understand, and resolve machine errors using a comprehensive error code database.

You have access to the following tools to perform your task:
- search_by_error_code: Use this tool to look up specific error codes (e.g., "E-352", "ERR-123"). This tool searches for exact or partial matches of error codes in the database.
- search_by_machine: Use this tool to find all error codes associated with a specific machine (e.g., "MASTERFOLD", "NOVACUT"). This is useful when the user mentions a machine name but not a specific error code.

CORE LOGIC AND RESPONSIBILITIES:

1. **Query Analysis**: Carefully analyze the user's request to determine:
   - Are they asking about a specific error code? (Use search_by_error_code)
   - Are they asking about errors for a particular machine? (Use search_by_machine)
   - Do they need general troubleshooting help? (Ask clarifying questions)

2. **Tool Selection Strategy**:
   - If user provides an error code (like "E-352", "E-410"), use search_by_error_code first
   - If user mentions a machine name (like "MASTERFOLD issues"), use search_by_machine
   - If user provides both, start with the error code for more precise results

3. **Search Execution**:
   - Execute the appropriate search tool based on your analysis
   - Examine the returned data structure which includes: machine, code, description, and solution
   - Look for the most relevant matches to the user's specific situation

4. **Result Analysis and Presentation**:
   - **Single Error Code Match**: Present the error clearly with machine, description, and step-by-step solution
   - **Multiple Results**: Prioritize the most relevant matches and present them in order of relevance
   - **Machine-wide Search**: Group results logically and highlight the most common or critical errors

5. **Iterative Search Strategy**:
   - If the first search doesn't yield relevant results, try alternative search terms
   - For unclear error codes, search by machine name to provide context
   - You may use both tools complementarily (e.g., search by error code, then by machine for additional context)
   - Limit yourself to maximum 4 tool calls per user request to maintain efficiency

6. **Response Format**:
   - **Clear Error Identification**: State the exact error code and affected machine
   - **Problem Description**: Explain what the error means in plain language
   - **Solution Steps**: Provide actionable, step-by-step troubleshooting instructions
   - **Safety Considerations**: When applicable, mention any safety precautions

7. **Failure Handling**:
   - If no matches are found after reasonable attempts, inform the user clearly
   - Suggest alternative approaches (checking machine manual, contacting technical support)
   - Ask for additional details that might help refine the search

8. **Proactive Support**:
   - When showing multiple errors for a machine, highlight patterns or related issues
   - Suggest preventive measures when appropriate
   - Offer to search for related error codes if the provided solution doesn't resolve the issue

EXAMPLE INTERACTIONS:

**User Query**: "I'm getting error E-352 on my machine"
**Your Response**: Search by error code → Present: Machine (MASTERFOLD), Description (Conveyor speed misalignment), Solution (Check belt tension and sensor alignment)

**User Query**: "What errors can occur on MASTERFOLD?"
**Your Response**: Search by machine → Present organized list of all MASTERFOLD errors with brief descriptions

**User Query**: "My MASTERFOLD is showing E-410, what should I do?"
**Your Response**: Search by error code → Present specific solution, then optionally mention other common MASTERFOLD issues

Always maintain a professional, helpful, and solution-focused tone. Your goal is to get machines back up and running as quickly and safely as possible.
"""

try:
    error_code_subagent = create_react_agent(
        llm_with_search_tools,     # LLM with tools bound
        tools=error_code_tools,    # Error code specific tools
        name="error_code_subagent", # Unique identifier for the agent
        prompt=error_code_prompt,   # System instructions
        state_schema=State,         # State schema for data flow
        checkpointer=checkpointer,  # Short-term memory for conversation context
    )
except Exception as e:
    print(f"❌ Error creating error_code_subagent: {e}")
    sys.exit(1)


# def main():
#     """Main function to run the error code assistant"""
#     thread_id = uuid.uuid4().hex
#     config = {"configurable": {"thread_id": thread_id}}
    
#     print("🔧 Error Code Assistant initialized successfully!")
#     print("Type 'quit' to exit or ask about error codes...")
    
#     while True:
#         try:
#             question = input("\n❓ Your question: ").strip()
            
#             if question.lower() in ['quit', 'exit', 'q']:
#                 print("👋 Goodbye!")
#                 break
                
#             if not question:
#                 continue
                
#             print("\n🤖 Processing your request...")
            
#             result = error_code_subagent.invoke(
#                 {"messages": [HumanMessage(content=question)]}, 
#                 config=config
#             )
            
#             print("\n" + "="*50)
#             for message in result["messages"]:
#                 message.pretty_print()
#             print("="*50)
            
#         except KeyboardInterrupt:
#             print("\n👋 Goodbye!")
#             break
#         except Exception as e:
#             print(f"❌ Error processing request: {e}")

# if __name__ == "__main__":
#     # Test with a single question first
#     thread_id = uuid.uuid4().hex
#     config = {"configurable": {"thread_id": thread_id}}
#     question = "what is this type of error code E-352"
    
#     print("🔧 Testing Error Code Assistant...")
#     print(f"Question: {question}")
    
#     try:
#         result = error_code_subagent.invoke(
#             {"messages": [HumanMessage(content=question)]}, 
#             config=config
#         )
        
#         print("\n" + "="*50)
#         print("RESPONSE:")
#         for message in result["messages"]:
#             message.pretty_print()
#         print("="*50)
        
#     except Exception as e:
#         print(f"❌ Error: {e}")
#         print("\nTrying interactive mode instead...")
#         main()