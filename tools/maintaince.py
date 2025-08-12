from datetime import date, datetime
import json
import sys
import os
from typing import Literal, Optional
from langchain.tools import tool
from pydantic import BaseModel, Field

# Add the parent directory to Python path to import helper modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helper.google_sheets import query_google_sheets

class MachineMaintenanceArgs(BaseModel):
    machine: str = Field(description="The name of the machine to get maintenance info for, e.g., MASTERFOLD, NOVACUT.")

@tool(args_schema=MachineMaintenanceArgs)
def get_maintenance_by_machine(machine: str) -> list:
    """Gets all scheduled maintenance tasks for a specific machine."""
    data = query_google_sheets("maintenance")
    results = [
        row for row in data
        if machine.upper() in row.get('machine', '').upper()
    ]
    print(f"🔍 Found {len(results)} maintenance tasks for machine: {machine}")
    return results

# Tool 2: Get maintenance tasks due within a date range
class DateRangeMaintenanceArgs(BaseModel):
    start_date: str = Field(description="Start date in YYYY-MM-DD format, e.g., 2025-08-01")
    end_date: str = Field(description="End date in YYYY-MM-DD format, e.g., 2025-08-31")

@tool(args_schema=DateRangeMaintenanceArgs)
def get_maintenance_by_date_range(start_date: str, end_date: str) -> list:
    """Gets all maintenance tasks scheduled within a specific date range."""
    data = query_google_sheets("maintenance")
    results = []
    
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        
        for row in data:
            next_due = row.get('next_due', '')
            if next_due:
                try:
                    due_date = datetime.strptime(next_due, "%Y-%m-%d").date()
                    if start_dt <= due_date <= end_dt:
                        results.append(row)
                except ValueError:
                    continue  # Skip rows with invalid date format
                    
    except ValueError as e:
        print(f"❌ Invalid date format: {e}")
        return []
    
    print(f"🔍 Found {len(results)} maintenance tasks between {start_date} and {end_date}")
    return results

# Tool 3: Get overdue maintenance tasks
class OverdueMaintenanceArgs(BaseModel):
    reference_date: Optional[str] = Field(default=None, description="Reference date in YYYY-MM-DD format (defaults to today)")

@tool(args_schema=OverdueMaintenanceArgs)
def get_overdue_maintenance(reference_date: Optional[str] = None) -> list:
    """Gets all maintenance tasks that are overdue as of the reference date (defaults to today)."""
    data = query_google_sheets("maintenance")
    results = []
    
    if reference_date:
        try:
            ref_dt = datetime.strptime(reference_date, "%Y-%m-%d").date()
        except ValueError:
            print(f"❌ Invalid date format: {reference_date}")
            return []
    else:
        ref_dt = date.today()
    
    for row in data:
        next_due = row.get('next_due', '')
        if next_due:
            try:
                due_date = datetime.strptime(next_due, "%Y-%m-%d").date()
                if due_date < ref_dt:
                    results.append(row)
            except ValueError:
                continue  # Skip rows with invalid date format
    
    print(f"🔍 Found {len(results)} overdue maintenance tasks as of {ref_dt}")
    return results

# Tool 4: Get upcoming maintenance tasks (next N days)
class UpcomingMaintenanceArgs(BaseModel):
    days_ahead: int = Field(default=7, description="Number of days to look ahead for upcoming maintenance (default: 7)")

@tool(args_schema=UpcomingMaintenanceArgs)
def get_upcoming_maintenance(days_ahead: int = 7) -> list:
    """Gets maintenance tasks due within the next N days."""
    data = query_google_sheets("maintenance")
    results = []
    
    today = date.today()
    future_date = date.fromordinal(today.toordinal() + days_ahead)
    
    for row in data:
        next_due = row.get('next_due', '')
        if next_due:
            try:
                due_date = datetime.strptime(next_due, "%Y-%m-%d").date()
                if today <= due_date <= future_date:
                    results.append(row)
            except ValueError:
                continue  # Skip rows with invalid date format
    
    print(f"🔍 Found {len(results)} maintenance tasks due in the next {days_ahead} days")
    return results

# Tool 5: Search maintenance tasks by keywords
class MaintenanceTaskSearchArgs(BaseModel):
    search_term: str = Field(description="Keywords to search in maintenance tasks, e.g., 'lubrication', 'belt', 'cleaning'")

@tool(args_schema=MaintenanceTaskSearchArgs)
def search_maintenance_by_task(search_term: str) -> list:
    """Searches maintenance tasks by keywords in the task description."""
    data = query_google_sheets("maintenance")
    results = []
    
    for row in data:
        tasks = row.get('tasks', '').upper()
        if search_term.upper() in tasks:
            results.append(row)
    
    print(f"🔍 Found {len(results)} maintenance tasks containing: {search_term}")
    return results

# Tool 6: Get all maintenance tasks (sorted by due date)
class AllMaintenanceArgs(BaseModel):
    sort_order: Literal["asc", "desc"] = Field(default="asc", description="Sort order by due date: 'asc' for earliest first, 'desc' for latest first")

@tool(args_schema=AllMaintenanceArgs)
def get_all_maintenance_sorted(sort_order: str = "asc") -> list:
    """Gets all maintenance tasks sorted by due date."""
    data = query_google_sheets("maintenance")
    
    # Filter out rows with invalid dates and sort
    valid_data = []
    for row in data:
        next_due = row.get('next_due', '')
        if next_due:
            try:
                due_date = datetime.strptime(next_due, "%Y-%m-%d").date()
                row['_sort_date'] = due_date  # Add for sorting
                valid_data.append(row)
            except ValueError:
                continue  # Skip rows with invalid date format
    
    # Sort by date
    reverse_order = sort_order == "desc"
    sorted_data = sorted(valid_data, key=lambda x: x['_sort_date'], reverse=reverse_order)
    
    # Remove the temporary sort field
    for row in sorted_data:
        row.pop('_sort_date', None)
    
    print(f"🔍 Retrieved {len(sorted_data)} maintenance tasks sorted by due date ({sort_order})")
    return sorted_data

maintenance_tools = [get_maintenance_by_machine, get_maintenance_by_date_range, get_overdue_maintenance, get_upcoming_maintenance, search_maintenance_by_task, get_all_maintenance_sorted]
    
# if __name__ == '__main__':
#     print("--- Testing Maintenance Search Tools ---")
    
#     # Test 1: Get maintenance by machine
#     print("\n=== Testing get_maintenance_by_machine ===")
#     machine = "MASTERFOLD"
#     print(f"Query: '{machine}'")
#     results = get_maintenance_by_machine.invoke({"machine": machine})
#     print("Results:")
#     if results:
#         print(json.dumps(results, indent=2))
#     else:
#         print("[]")
    
#     # Test 2: Get maintenance by date range
#     print("\n=== Testing get_maintenance_by_date_range ===")
#     start_date, end_date = "2025-08-01", "2025-08-31"
#     print(f"Query: {start_date} to {end_date}")
#     results = get_maintenance_by_date_range.invoke({"start_date": start_date, "end_date": end_date})
#     print("Results:")
#     if results:
#         print(json.dumps(results, indent=2))
#     else:
#         print("[]")
    
#     # Test 3: Get overdue maintenance
#     print("\n=== Testing get_overdue_maintenance ===")
#     results = get_overdue_maintenance.invoke({})
#     print("Results:")
#     if results:
#         print(f"Found {len(results)} overdue tasks")
#         print(json.dumps(results[:2], indent=2))  # Show first 2
#     else:
#         print("[]")
    
#     # Test 4: Get upcoming maintenance
#     print("\n=== Testing get_upcoming_maintenance ===")
#     days_ahead = 14
#     print(f"Query: Next {days_ahead} days")
#     results = get_upcoming_maintenance.invoke({"days_ahead": days_ahead})
#     print("Results:")
#     if results:
#         print(f"Found {len(results)} upcoming tasks")
#         print(json.dumps(results[:2], indent=2))  # Show first 2
#     else:
#         print("[]")
    
#     # Test 5: Search maintenance by task keywords
#     print("\n=== Testing search_maintenance_by_task ===")
#     search_term = "lubrication"
#     print(f"Query: '{search_term}'")
#     results = search_maintenance_by_task.invoke({"search_term": search_term})
#     print("Results:")
#     if results:
#         print(json.dumps(results, indent=2))
#     else:
#         print("[]")
    
#     # Test 6: Get all maintenance sorted
#     print("\n=== Testing get_all_maintenance_sorted ===")
#     sort_order = "asc"
#     print(f"Query: Sort order '{sort_order}'")
#     results = get_all_maintenance_sorted.invoke({"sort_order": sort_order})
#     print("Results:")
#     if results:
#         print(f"Found {len(results)} total maintenance tasks")
#         print(json.dumps(results[:3], indent=2))  # Show first 3
#     else:
#         print("[]")