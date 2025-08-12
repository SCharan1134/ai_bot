import json
import sys
import os
from typing import Literal, Optional
from langchain.tools import tool
from pydantic import BaseModel, Field

# Add the parent directory to Python path to import helper modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helper.google_sheets import query_google_sheets

class MachinePartSearchArgs(BaseModel):
    machine: str = Field(description="The name of the machine, e.g., MASTERFOLD, NOVACUT, EXPERTFOLD.")

@tool(args_schema=MachinePartSearchArgs)
def search_parts_by_machine(machine: str) -> list:
    """Searches the 'spare_parts' sheet for all parts available for a specific machine."""
    data = query_google_sheets("spare_parts")
    results = [
        row for row in data 
        if machine.upper() in row.get('machine', '').upper()
    ]
    print(f"🔍 Found {len(results)} parts for machine: {machine}")
    return results

# Tool 2: Search parts by part code
class PartCodeSearchArgs(BaseModel):
    part_code: str = Field(description="The part code to search for, e.g., NC-00123, MF-00789.")

@tool(args_schema=PartCodeSearchArgs)
def search_parts_by_code(part_code: str) -> list:
    """Searches the 'spare_parts' sheet for a specific part using its part code."""
    data = query_google_sheets("spare_parts")
    results = [
        row for row in data 
        if part_code.upper() in row.get('part_code', '').upper()
    ]
    print(f"🔍 Found {len(results)} parts matching code: {part_code}")
    return results

# Tool 3: Search parts by name/keywords
class PartNameSearchArgs(BaseModel):
    search_term: str = Field(description="Name or keyword to search in part names and descriptions, e.g., 'blade', 'motor', 'sensor'.")

@tool(args_schema=PartNameSearchArgs)
def search_parts_by_name(search_term: str) -> list:
    """Searches the 'spare_parts' sheet for parts by name or keywords in the description."""
    data = query_google_sheets("spare_parts")
    results = []
    for row in data:
        search_text = f"{row.get('name', '')} {row.get('description', '')}".upper()
        if search_term.upper() in search_text:
            results.append(row)
    
    print(f"🔍 Found {len(results)} parts matching search term: {search_term}")
    return results

# Tool 4: Search parts by availability
class AvailabilitySearchArgs(BaseModel):
    availability_status: Literal["in_stock", "available", "out_of_stock"] = Field(
        description="Filter by availability: 'in_stock' for immediately available parts, 'available' for parts with delivery time, 'out_of_stock' for unavailable parts."
    )

@tool(args_schema=AvailabilitySearchArgs)
def search_parts_by_availability(availability_status: str) -> list:
    """Searches the 'spare_parts' sheet for parts based on their availability status."""
    data = query_google_sheets("spare_parts")
    results = []
    
    for row in data:
        availability = row.get('availability', '').lower()
        
        if availability_status == "in_stock" and "in stock" in availability:
            results.append(row)
        elif availability_status == "available" and ("day" in availability or "week" in availability):
            results.append(row)
        elif availability_status == "out_of_stock" and ("out of stock" in availability or "unavailable" in availability):
            results.append(row)
    
    print(f"🔍 Found {len(results)} parts with availability status: {availability_status}")
    return results

# Tool 5: Search parts by price range
class PriceRangeSearchArgs(BaseModel):
    min_price: Optional[float] = Field(default=None, description="Minimum price in rupees (optional).")
    max_price: Optional[float] = Field(default=None, description="Maximum price in rupees (optional).")

@tool(args_schema=PriceRangeSearchArgs)
def search_parts_by_price_range(min_price: Optional[float] = None, max_price: Optional[float] = None) -> list:
    """Searches the 'spare_parts' sheet for parts within a specified price range."""
    data = query_google_sheets("spare_parts")
    results = []
    
    for row in data:
        price_str = row.get('price', '').replace('₹', '').replace(',', '')
        try:
            price = float(price_str)
            if (min_price is None or price >= min_price) and (max_price is None or price <= max_price):
                results.append(row)
        except (ValueError, TypeError):
            continue  # Skip rows with invalid price data
    
    price_range = f"₹{min_price or 0:,.0f} - ₹{max_price or float('inf'):,.0f}"
    print(f"🔍 Found {len(results)} parts in price range: {price_range}")
    return results

part_code_tools = [search_parts_by_machine, search_parts_by_code, search_parts_by_name, search_parts_by_availability, search_parts_by_price_range]

# if __name__ == '__main__':
#     print("--- Testing Spare Parts Search Tools ---")
    
#     # Test 1: Search by machine
#     print("\n=== Testing search_parts_by_machine ===")
#     machine = "NOVACUT"
#     print(f"Query: '{machine}'")
#     results = search_parts_by_machine.invoke({"machine": machine})
#     print("Results:")
#     if results:
#         print(json.dumps(results[:2], indent=2))  # Show first 2 results
#     else:
#         print("[]")
    
#     # Test 2: Search by part code
#     print("\n=== Testing search_parts_by_code ===")
#     part_code = "NC-00123"
#     print(f"Query: '{part_code}'")
#     results = search_parts_by_code.invoke({"part_code": part_code})
#     print("Results:")
#     if results:
#         print(json.dumps(results, indent=2))
#     else:
#         print("[]")
    
#     # Test 3: Search by name/keywords
#     print("\n=== Testing search_parts_by_name ===")
#     search_term = "blade"
#     print(f"Query: '{search_term}'")
#     results = search_parts_by_name.invoke({"search_term": search_term})
#     print("Results:")
#     if results:
#         print(json.dumps(results, indent=2))
#     else:
#         print("[]")
    
#     # Test 4: Search by availability
#     print("\n=== Testing search_parts_by_availability ===")
#     availability = "in_stock"
#     print(f"Query: '{availability}'")
#     results = search_parts_by_availability.invoke({"availability_status": availability})
#     print("Results:")
#     if results:
#         print(f"Found {len(results)} parts in stock")
#         print(json.dumps(results[:2], indent=2))  # Show first 2 results
#     else:
#         print("[]")
    
#     # Test 5: Search by price range
#     print("\n=== Testing search_parts_by_price_range ===")
#     min_price, max_price = 5000, 50000
#     print(f"Query: ₹{min_price:,} - ₹{max_price:,}")
#     results = search_parts_by_price_range.invoke({"min_price": min_price, "max_price": max_price})
#     print("Results:")
#     if results:
#         print(f"Found {len(results)} parts in price range")
#         print(json.dumps(results[:2], indent=2))  # Show first 2 results
#     else:
#         print("[]")