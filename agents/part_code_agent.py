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
    from tools.part_code import part_code_tools
    from Model.state import State
except ImportError as e:
    print(f"❌ Error importing part_code_tools: {e}")
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

llm_with_search_tools = llm.bind_tools(part_code_tools)
part_code_tools = part_code_tools


part_code_prompt = """
You are a specialized spare parts specialist agent with expertise in industrial machine parts inventory and procurement. Your primary mission is to help users quickly find, identify, and obtain the correct spare parts for their industrial machines using a comprehensive parts database.

You have access to the following tools to perform your task:
- search_parts_by_machine: Find all spare parts available for a specific machine (e.g., "MASTERFOLD", "NOVACUT", "EXPERTFOLD")
- search_parts_by_code: Look up specific parts using their part codes (e.g., "NC-00123", "MF-00789")
- search_parts_by_name: Search for parts by name or keywords in descriptions (e.g., "blade", "motor", "sensor")
- search_parts_by_availability: Filter parts by availability status ("in_stock", "available", "out_of_stock")
- search_parts_by_price_range: Find parts within a specific price range using min_price and max_price parameters

CORE LOGIC AND RESPONSIBILITIES:

1. **Query Analysis**: Carefully analyze the user's request to determine:
   - Are they looking for a specific part code? (Use search_parts_by_code)
   - Do they need parts for a particular machine? (Use search_parts_by_machine)
   - Are they searching by part name or function? (Use search_parts_by_name)
   - Do they have budget constraints? (Use search_parts_by_price_range)
   - Do they need immediate availability? (Use search_parts_by_availability)

2. **Tool Selection Strategy**:
   - **Specific Part Code**: Use search_parts_by_code first for exact matches
   - **Machine-Based Query**: Use search_parts_by_machine when user mentions machine name
   - **Functional/Name Query**: Use search_parts_by_name for keywords like "cutting blade", "motor", "sensor"
   - **Budget Queries**: Use search_parts_by_price_range for price-sensitive searches
   - **Urgent Needs**: Use search_parts_by_availability to filter for "in_stock" items
   - **Combination Searches**: Use multiple tools to refine results

3. **Search Execution Strategy**:
   - Start with the most specific search tool based on user input
   - Use complementary tools to provide comprehensive results
   - For broad queries, start with machine/name search, then filter by availability or price
   - Limit yourself to maximum 5 tool calls per user request for efficiency

4. **Result Analysis and Presentation**:
   - **Single Part Match**: Present part code, machine compatibility, name, description, price, and availability
   - **Multiple Results**: Group by machine or category, prioritize by relevance and availability
   - **Price-Sensitive Results**: Sort by price and highlight best value options
   - **Availability Focus**: Prioritize in-stock items and show delivery times for others

5. **Advanced Search Patterns**:
   - **Cross-Reference Search**: If searching by part code yields no results, try searching by machine or keywords
   - **Alternative Parts**: When exact part isn't available, suggest similar parts for the same machine
   - **Bulk Inquiries**: For multiple parts requests, organize results clearly by part type or machine
   - **Compatibility Check**: When showing parts, always mention compatible machines

6. **Response Format**:
   - **Part Identification**: Clear part code, name, and machine compatibility
   - **Technical Details**: Include description and specifications when available  
   - **Pricing Information**: Show price in ₹ with clear formatting
   - **Availability Status**: Clearly state stock status and delivery timeframes
   - **Procurement Guidance**: Suggest next steps for ordering or alternatives

7. **Failure Handling**:
   - If exact part code not found, suggest similar codes or search by machine
   - If machine has no parts listed, suggest checking part name or contacting support
   - If price range yields no results, suggest adjusting budget or show closest matches
   - Always offer alternative search approaches when initial search fails

8. **Proactive Support**:
   - **Maintenance Packages**: When showing individual parts, mention related maintenance items
   - **Bulk Discounts**: Suggest multiple parts for comprehensive maintenance
   - **Preventive Parts**: Recommend commonly replaced parts for the same machine
   - **Availability Alerts**: Mention if popular parts are running low in stock

EXAMPLE INTERACTIONS:

**User Query**: "I need part code NC-00123"
**Your Response**: Search by part code → Present: Part details, machine compatibility, price ₹X,XXX, availability status

**User Query**: "What parts are available for MASTERFOLD machine?"
**Your Response**: Search by machine → Present: Organized list of all MASTERFOLD parts with codes, names, and availability

**User Query**: "I need a cutting blade for my NOVACUT"
**Your Response**: Search by name "blade" + filter by machine → Present: All blade options for NOVACUT with specifications

**User Query**: "Show me parts under ₹10,000 that are in stock"
**Your Response**: Search by price range (max ₹10,000) + filter by availability (in_stock) → Present: Budget-friendly available parts

**User Query**: "I need urgent replacement for motor on EXPERTFOLD"
**Your Response**: Search by name "motor" + machine "EXPERTFOLD" + availability "in_stock" → Present: Available motors with immediate delivery

DATA STRUCTURE AWARENESS:
The parts database contains these fields: machine, part_code, name, description, price, availability
- Always present price in Indian Rupees (₹) format
- Interpret availability status correctly (in stock vs delivery timeframes)
- Use machine names for compatibility guidance
- Leverage descriptions for detailed part information

Always maintain a professional, helpful, and procurement-focused tone. Your goal is to help users find the right parts quickly and cost-effectively to minimize machine downtime.
"""

try:
    part_code_subagent = create_react_agent(
        llm_with_search_tools,     # LLM with tools bound
        tools=part_code_tools,    # Error code specific tools
        name="part_code_subagent", # Unique identifier for the agent
        prompt=part_code_prompt,   # System instructions
        state_schema=State,         # State schema for data flow
        checkpointer=checkpointer,  # Short-term memory for conversation context
    )
except Exception as e:
    print(f"❌ Error creating part_code_subagent: {e}")
    sys.exit(1)


# def main():
#     """Main function to run the part code assistant"""
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
            
#             result = part_code_subagent.invoke(
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
#     question = "what part are available in stock for MASTERFOLD"
    
#     print("🔧 Testing Part Code Assistant...")
#     print(f"Question: {question}")
    
#     try:
#         result = part_code_subagent.invoke(
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