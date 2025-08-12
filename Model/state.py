from typing_extensions import TypedDict
from typing import Annotated, Sequence
from langgraph.graph.message import  add_messages
from langchain_core.messages import BaseMessage
from langgraph.managed.is_last_step import RemainingSteps

class State(TypedDict):
    """
    State schema for the multi-agent customer support workflow.
    
    This defines the shared data structure that flows between nodes in the graph,
    representing the current snapshot of the conversation and agent state.
    """
    # Conversation history with automatic message aggregation
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # User preferences and context loaded from long-term memory store
    loaded_memory: str
    
    # Counter to prevent infinite recursion in agent workflow
    remaining_steps: RemainingSteps
