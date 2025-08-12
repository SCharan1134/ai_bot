import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(current_dir)
sys.path.append(parent_dir)

from langchain_core.messages import  HumanMessage
import uuid

try:
    # Import the supervisor from the graph module
    from graph.main_graph import supervisor_prebuilt
    print("✅ Successfully imported supervisor")
except ImportError as e:
    print(f"❌ Error importing supervisor: {e}")
    print("Make sure the graph/main_graph.py file exists and is properly configured")
    sys.exit(1)


def main():
    """Main function to run the supervisor assistant"""
    thread_id = uuid.uuid4().hex
    config = {"configurable": {"thread_id": thread_id}}
    
    print("🔧 Multi-Agent Technical Support Assistant initialized successfully!")
    print("Available services:")
    print("  - Error code diagnosis and troubleshooting")
    print("  - Machine fault resolution")
    print("Type 'quit' to exit or ask your technical questions...")
    
    while True:
        try:
            question = input("\n❓ Your question: ").strip()
            
            if question.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
                
            if not question:
                continue
                
            print("\n🤖 Processing your request...")
            
            # Create the state for the supervisor
            state = {"messages": [HumanMessage(content=question)]}
            
            result = supervisor_prebuilt.invoke(state, config=config)
            
            print("\n" + "="*50)
            print("RESPONSE:")
            
            # Handle the response properly
            if "messages" in result:
                for message in result["messages"]:
                    if hasattr(message, 'pretty_print'):
                        message.pretty_print()
                    else:
                        print(f"🤖 {message.content}")
            else:
                print("No response received")
                
            print("="*50)
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error processing request: {e}")
            import traceback
            traceback.print_exc()

# def test_supervisor():
#     """Test function to verify supervisor works"""
#     thread_id = uuid.uuid4().hex
#     config = {"configurable": {"thread_id": thread_id}}
    
#     test_questions = [
#         "what is error code E-352?",
#         "what parts are available for MASTERFOLD?", 
#         "what maintenance is needed for NOVACUT?"
#     ]
    
#     for question in test_questions:
#         print(f"\n🧪 Testing: {question}")
#         try:
#             state = {"messages": [HumanMessage(content=question)]}
#             result = supervisor_prebuilt.invoke(state, config=config)
            
#             print("✅ Test successful")
#             if "messages" in result:
#                 for message in result["messages"][-1:]:  # Show only last message
#                     print(f"Response: {message.content[:100]}...")
#             print("-" * 30)
            
#         except Exception as e:
#             print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    print("🔧 Testing Technical Support Supervisor...")
    
    
    print("\n" + "="*50)
    print("Tests completed. Starting interactive mode...")
    print("="*50)
    
    # Then start interactive mode
    main()