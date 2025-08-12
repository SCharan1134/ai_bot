import json
import sys
import os
from langchain.tools import tool
from pydantic import BaseModel, Field

# Add the parent directory to Python path to import helper modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from helper.google_sheets import query_google_sheets
except ImportError:
    print("Error: Cannot import query_google_sheets. Check your file structure.")
    # Define a fallback function for testing
    def query_google_sheets(sheet_name):
        print(f"Fallback: query_google_sheets called with {sheet_name}")
        return []

class ErrorCodeSearchArgs(BaseModel):
    error_code: str = Field(description="The error code to look up, e.g., E-352, ERR-123.")
 
@tool(args_schema=ErrorCodeSearchArgs)
def search_by_error_code(error_code: str) -> list:
    """Searches the 'error_codes' sheet for information about a specific error code."""
    data = query_google_sheets("error_codes")
    results = [
        row for row in data 
        if error_code.upper() in row.get('code', '').upper()
    ]
    print(f"🔍 Error code search found {len(results)} matches for code: {error_code}")
    return results

# Tool 2: Search by Machine
class MachineSearchArgs(BaseModel):
    machine: str = Field(description="The name of the machine, e.g., MASTERFOLD, NOVACUT.")
 
@tool(args_schema=MachineSearchArgs)
def search_by_machine(machine: str) -> list:
    """Searches the 'error_codes' sheet for all error codes related to a specific machine."""
    data = query_google_sheets("error_codes")
    results = [
        row for row in data 
        if machine.upper() in row.get('machine', '').upper()
    ]
    print(f"🔍 Machine search found {len(results)} matches for machine: {machine}")
    return results

error_code_tools = [search_by_error_code,search_by_machine]

# if __name__ == '__main__':
#     print("--- Testing Error Code Search Tools ---")
    
#     # Test Tool 1: Search by error code
#     print("\n=== Testing search_by_error_code ===")
#     error_code = "E-352"
#     print(f"Query: '{error_code}'")
#     search_results = search_by_error_code.invoke({"error_code": error_code})
    
#     print("Results:")
#     if search_results:
#         print(json.dumps(search_results, indent=2))
#     else:
#         print("[]")
    
#     # Test Tool 2: Search by machine
#     print("\n=== Testing search_by_machine ===")
#     machine = "MASTERFOLD"
#     print(f"Query: '{machine}'")
#     search_results = search_by_machine.invoke({"machine": machine})
    
#     print("Results:")
#     if search_results:
#         print(json.dumps(search_results, indent=2))
#     else:
#         print("[]")