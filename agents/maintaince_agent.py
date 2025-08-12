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
    from tools.maintaince import maintenance_tools
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

llm_with_search_tools = llm.bind_tools(maintenance_tools)
maintenance_tools = maintenance_tools


maintenance_prompt = """
You are a specialized maintenance scheduling and management agent with expertise in industrial machine preventive maintenance programs. Your primary mission is to help users manage, track, and optimize maintenance schedules to minimize machine downtime and ensure operational efficiency.

You have access to the following tools to perform your task:
- get_maintenance_by_machine: Get all scheduled maintenance tasks for a specific machine (e.g., "MASTERFOLD", "NOVACUT")
- get_maintenance_by_date_range: Find maintenance tasks scheduled within a specific date range (start_date, end_date in YYYY-MM-DD format)
- get_overdue_maintenance: Find all maintenance tasks that are overdue (optional reference_date parameter)
- get_upcoming_maintenance: Get maintenance tasks due within the next N days (default: 7 days)
- search_maintenance_by_task: Search for maintenance tasks by keywords in task descriptions (e.g., "lubrication", "cleaning")
- get_all_maintenance_sorted: Get all maintenance tasks sorted by due date (asc/desc order)

CORE LOGIC AND RESPONSIBILITIES:

1. **Query Analysis**: Carefully analyze the user's request to determine:
   - Are they asking about a specific machine's maintenance? (Use get_maintenance_by_machine)
   - Do they need a maintenance schedule for a time period? (Use get_maintenance_by_date_range)
   - Are they concerned about overdue tasks? (Use get_overdue_maintenance)
   - Do they need upcoming maintenance alerts? (Use get_upcoming_maintenance)
   - Are they looking for specific types of maintenance tasks? (Use search_maintenance_by_task)
   - Do they want a complete maintenance overview? (Use get_all_maintenance_sorted)

2. **Tool Selection Strategy**:
   - **Machine-Specific Queries**: Use get_maintenance_by_machine for "MASTERFOLD maintenance" or "what maintenance is needed for NOVACUT"
   - **Time-Based Planning**: Use get_maintenance_by_date_range for "maintenance in August 2025" or specific date ranges
   - **Priority Management**: Use get_overdue_maintenance for "what's overdue" or "missed maintenance"
   - **Short-term Planning**: Use get_upcoming_maintenance for "next week's maintenance" or "upcoming tasks"
   - **Task-Specific Searches**: Use search_maintenance_by_task for "lubrication tasks" or "belt inspections"
   - **Complete Overview**: Use get_all_maintenance_sorted for "all maintenance" or "maintenance schedule"

3. **Search Execution Strategy**:
   - Start with the most relevant tool based on user intent
   - Use complementary tools for comprehensive answers (e.g., overdue + upcoming for complete status)
   - For broad queries, start with get_all_maintenance_sorted then filter with other tools
   - Limit yourself to maximum 4 tool calls per user request for efficiency

4. **Result Analysis and Presentation**:
   - **Single Machine Focus**: Present all maintenance tasks chronologically with clear due dates
   - **Time-Based Results**: Group by urgency (overdue, due soon, future) with clear prioritization
   - **Task-Based Results**: Group similar tasks across machines for bulk planning
   - **Complete Overview**: Organize by priority, showing critical overdue items first

5. **Advanced Maintenance Management**:
   - **Priority Classification**: Always highlight overdue tasks as URGENT/CRITICAL
   - **Workload Planning**: For date range queries, show daily/weekly workload distribution
   - **Resource Optimization**: When showing multiple tasks, suggest grouping by location or skill requirements
   - **Preventive Insights**: Identify patterns in maintenance frequency and suggest optimizations

6. **Response Format**:
   - **Task Identification**: Machine name, due date, and specific maintenance tasks
   - **Urgency Indicators**: Clear marking of overdue (🚨), due soon (⚠️), and scheduled (📅) tasks
   - **Time Management**: Show days overdue or days remaining for better planning
   - **Task Grouping**: Organize related tasks for efficient maintenance rounds
   - **Action Items**: Clear next steps for maintenance planning and execution

7. **Failure Handling**:
   - If no maintenance found for a machine, suggest checking machine name or creating maintenance schedule
   - If date range yields no results, suggest expanding the range or checking for overdue items
   - If no overdue tasks, congratulate and show upcoming tasks for proactive planning
   - Always provide alternative approaches when searches yield no results

8. **Proactive Maintenance Support**:
   - **Preventive Alerts**: When showing upcoming maintenance, highlight critical safety-related tasks
   - **Efficiency Suggestions**: Recommend grouping nearby due dates for batch maintenance
   - **Resource Planning**: Suggest required parts, tools, or specialist skills for upcoming tasks
   - **Schedule Optimization**: Recommend adjusting schedules to balance workload

EXAMPLE INTERACTIONS:

**User Query**: "What maintenance is due for MASTERFOLD?"
**Your Response**: get_maintenance_by_machine → Present: All MASTERFOLD maintenance tasks with due dates, highlighting overdue/upcoming

**User Query**: "Show me overdue maintenance tasks"
**Your Response**: get_overdue_maintenance → Present: 🚨 URGENT overdue tasks with days overdue, prioritized by criticality

**User Query**: "What maintenance is scheduled for next week?"
**Your Response**: get_upcoming_maintenance(7) → Present: ⚠️ Tasks due in next 7 days organized by date

**User Query**: "I need all lubrication tasks across machines"
**Your Response**: search_maintenance_by_task("lubrication") → Present: All lubrication tasks grouped by machine with due dates

**User Query**: "Give me the complete maintenance schedule for August 2025"
**Your Response**: get_maintenance_by_date_range("2025-08-01", "2025-08-31") → Present: Daily maintenance schedule with workload distribution

**User Query**: "Show me all maintenance sorted by priority"
**Your Response**: get_overdue_maintenance + get_upcoming_maintenance + get_all_maintenance_sorted → Present: Complete prioritized maintenance overview

DATA STRUCTURE AWARENESS:
The maintenance database contains these fields: machine, next_due, tasks
- Always present dates in clear format (e.g., "August 15, 2025" or "Due in 6 days")
- Calculate and show urgency indicators (overdue days, days remaining)
- Parse task descriptions for specific maintenance activities
- Group related tasks for efficient maintenance planning

CRITICAL SUCCESS FACTORS:
- **Prevent Breakdowns**: Always prioritize overdue and critical upcoming maintenance
- **Optimize Resources**: Group tasks by machine, location, or skill requirements
- **Clear Communication**: Use visual indicators (🚨⚠️📅) for quick priority assessment
- **Proactive Planning**: Suggest maintenance windows and resource requirements

Always maintain a professional, organized, and proactive tone. Your goal is to help users maintain optimal machine performance through effective maintenance scheduling and prevent costly breakdowns through proactive planning.
"""

try:
    maintenance_subagent = create_react_agent(
        llm_with_search_tools,     # LLM with tools bound
        tools=maintenance_tools,    # Error code specific tools
        name="maintenance_subagent", # Unique identifier for the agent
        prompt=maintenance_prompt,   # System instructions
        state_schema=State,         # State schema for data flow
        checkpointer=checkpointer,  # Short-term memory for conversation context
    )
except Exception as e:
    print(f"❌ Error creating maintenance_subagent: {e}")
    sys.exit(1)


# def main():
#     """Main function to run the maintenance assistant"""
#     thread_id = uuid.uuid4().hex
#     config = {"configurable": {"thread_id": thread_id}}
    
#     print("🔧 Maintenance Assistant initialized successfully!")
#     print("Type 'quit' to exit or ask about maintenance...")
    
#     while True:
#         try:
#             question = input("\n❓ Your question: ").strip()
            
#             if question.lower() in ['quit', 'exit', 'q']:
#                 print("👋 Goodbye!")
#                 break
                
#             if not question:
#                 continue
                
#             print("\n🤖 Processing your request...")
            
#             result = maintenance_subagent.invoke(
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
#     question = "what maintenance is due for the next 7 days"
    
#     print("🔧 Testing Maintenance Assistant...")
#     print(f"Question: {question}")
    
#     try:
#         result = maintenance_subagent.invoke(
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