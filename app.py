from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import google.generativeai as genai
import json
import os
from datetime import datetime

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configuration
GEMINI_API_KEY = "AIzaSyAC5A3PFfAdF3nDgF5uwINvwzrYMjEXntU"
GOOGLE_SHEET_ID = "1AxAyCRjdMpD6nVGnBuGZsgeo1af0aLe611QhgFTvSPQ"

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Sample Data - Replace this with your actual data from Google Sheets
SAMPLE_DATA = {
    "error_codes": [
        {"machine": "MASTERFOLD", "code": "E-352", "description": "Conveyor speed misalignment", "solution": "Check belt tension and sensor alignment"},
        {"machine": "MASTERFOLD", "code": "E-401", "description": "Paper jam detected", "solution": "Clear paper path and check sensors"},
        {"machine": "NOVACUT", "code": "ERR-123", "description": "Blade alignment error", "solution": "Calibrate cutting blade position"},
        {"machine": "NOVACUT", "code": "ERR-456", "description": "Temperature sensor fault", "solution": "Replace temperature sensor unit"},
        {"machine": "BOBST-SP102", "code": "SYS-001", "description": "System startup failure", "solution": "Power cycle and check connections"},
    ],
    "spare_parts": [
        {"machine": "MASTERFOLD", "part_code": "MF-001", "name": "Folding Blade Assembly", "price": "$245.00", "availability": "In Stock"},
        {"machine": "MASTERFOLD", "part_code": "MF-002", "name": "Conveyor Belt", "price": "$89.50", "availability": "In Stock"},
        {"machine": "NOVACUT", "part_code": "NC-101", "name": "Cutting Blade", "price": "$156.00", "availability": "Out of Stock"},
        {"machine": "NOVACUT", "part_code": "NC-102", "name": "Temperature Sensor", "price": "$67.25", "availability": "In Stock"},
        {"machine": "BOBST-SP102", "part_code": "SP-201", "name": "Control Board", "price": "$425.00", "availability": "In Stock"},
        {"machine": "MASTERFOLD", "part_code": "MF-003", "name": "Motor Assembly", "price": "$380.00", "availability": "Limited Stock"},
    ],
    "maintenance": [
        {"machine": "MASTERFOLD", "next_due": "2024-08-15", "tasks": "Lubricate folding mechanisms, Check belt tension, Calibrate sensors"},
        {"machine": "NOVACUT", "next_due": "2024-08-20", "tasks": "Replace cutting blade, Clean waste collection, Update firmware"},
        {"machine": "BOBST-SP102", "next_due": "2024-08-10", "tasks": "System diagnostic, Replace filters, Check electrical connections"},
        {"machine": "MASTERFOLD", "next_due": "2024-09-01", "tasks": "Monthly inspection, Replace worn parts, Performance testing"},
    ]
}

def extract_intent_and_entities(user_message):
    """Use Gemini to determine user intent and extract entities"""
    prompt = f"""
    Analyze this user message from a machine operator or technician: "{user_message}"
    
    Determine:
    1. Intent: Choose EXACTLY one from [error_lookup, spare_part_search, maintenance_info, general_help]
    2. Machine name: Extract machine name if mentioned (common names: MASTERFOLD, NOVACUT, BOBST, etc.)
    3. Error code: Extract error code if mentioned (format like E-352, ERR-123, etc.)
    4. Part name: Extract part name or part code if mentioned
    5. Keywords: Important keywords from the message
    
    Respond ONLY in this JSON format:
    {{
        "intent": "error_lookup",
        "machine": "MASTERFOLD",
        "error_code": "E-352",
        "part_name": "",
        "keywords": ["conveyor", "speed"]
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Clean the response to extract JSON
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0]
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0]
        
        return json.loads(response_text)
    except Exception as e:
        print(f"Error in intent extraction: {e}")
        return {
            "intent": "general_help",
            "machine": "",
            "error_code": "",
            "part_name": "",
            "keywords": []
        }

def search_error_codes(machine, error_code):
    """Search for error codes in the local data"""
    results = []
    for row in SAMPLE_DATA["error_codes"]:
        match_machine = not machine or machine.upper() in row.get('machine', '').upper()
        match_code = not error_code or error_code.upper() in row.get('code', '').upper()
        
        if match_machine and match_code:
            results.append(row)
    
    return results

def search_spare_parts(machine, part_name, keywords):
    """Search for spare parts in the local data"""
    results = []
    for row in SAMPLE_DATA["spare_parts"]:
        match_machine = not machine or machine.upper() in row.get('machine', '').upper()
        match_part = not part_name or part_name.upper() in row.get('name', '').upper() or part_name.upper() in row.get('part_code', '').upper()
        
        # Check keywords in part name or description
        keyword_match = not keywords or any(
            keyword.upper() in row.get('name', '').upper() or 
            keyword.upper() in row.get('part_code', '').upper()
            for keyword in keywords
        )
        
        if match_machine and (match_part or keyword_match):
            results.append(row)
    
    return results

def search_maintenance_info(machine):
    """Search for maintenance information in the local data"""
    results = []
    for row in SAMPLE_DATA["maintenance"]:
        match_machine = not machine or machine.upper() in row.get('machine', '').upper()
        if match_machine:
            results.append(row)
    
    return results

def generate_bot_response(user_message, intent_data, search_results):
    """Generate final response using Gemini"""
    
    if not search_results:
        no_data_prompt = f"""
        The user asked: "{user_message}"
        Intent: {intent_data['intent']}
        
        No matching data was found in our database. 
        Provide a helpful response suggesting:
        1. Check the machine name spelling
        2. Verify the error code format
        3. Contact technical support for assistance
        
        Keep it concise and professional.
        """
        
        try:
            response = model.generate_content(no_data_prompt)
            return response.text
        except:
            return "I couldn't find specific information for your query. Please check the machine name and error code, or contact technical support for assistance."
    
    # Format search results for the prompt
    formatted_results = ""
    for i, result in enumerate(search_results[:3], 1):  # Limit to top 3 results
        formatted_results += f"\nResult {i}:\n"
        for key, value in result.items():
            if value:  # Only include non-empty values
                formatted_results += f"  {key}: {value}\n"
    
    response_prompt = f"""
    You are a Bobst machine support assistant. A {intent_data['intent'].replace('_', ' ')} query was made.
    
    User question: "{user_message}"
    
    Relevant data found:
    {formatted_results}
    
    Provide a helpful, concise response that:
    1. Directly answers the user's question
    2. Uses the specific data provided
    3. Includes actionable next steps when appropriate
    4. Maintains a professional technical tone
    5. Formats information clearly (use bullet points if multiple items)
    
    Keep the response under 200 words.
    """
    
    try:
        response = model.generate_content(response_prompt)
        return response.text
    except Exception as e:
        print(f"Error generating response: {e}")
        return "I found some information but couldn't process it properly. Please try rephrasing your question."

# Routes
@app.route('/')
def home():
    """Serve the chat interface"""
    return render_template_string(open('templates/index.html').read())

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages"""
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'No message provided'}), 400
        
        user_message = data['message'].strip()
        if not user_message:
            return jsonify({'error': 'Empty message'}), 400
        
        print(f"[{datetime.now()}] Processing message: {user_message}")
        
        # Step 1: Extract intent and entities
        intent_data = extract_intent_and_entities(user_message)
        print(f"Intent data: {intent_data}")
        
        # Step 2: Query appropriate data based on intent
        search_results = []
        
        if intent_data['intent'] == 'error_lookup':
            search_results = search_error_codes(
                intent_data.get('machine', ''),
                intent_data.get('error_code', '')
            )
        
        elif intent_data['intent'] == 'spare_part_search':
            search_results = search_spare_parts(
                intent_data.get('machine', ''),
                intent_data.get('part_name', ''),
                intent_data.get('keywords', [])
            )
        
        elif intent_data['intent'] == 'maintenance_info':
            search_results = search_maintenance_info(
                intent_data.get('machine', '')
            )
        
        else:  # general_help
            general_response = """
            I'm your Bobst machine assistant! I can help you with:
            
            🔧 **Error Codes**: Ask about specific error codes (e.g., "What's error E-352 on MASTERFOLD?")
            ⚙️ **Spare Parts**: Search for parts (e.g., "Need folding blade for NOVACUT")
            📅 **Maintenance**: Check maintenance schedules (e.g., "When is next maintenance for MASTERFOLD?")
            
            Just describe your issue and I'll help you find the information you need!
            """
            return jsonify({'reply': general_response})
        
        print(f"Search results: {len(search_results)} items found")
        
        # Step 3: Generate final response
        bot_response = generate_bot_response(user_message, intent_data, search_results)
        
        return jsonify({'reply': bot_response})
    
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        return jsonify({'reply': 'Sorry, I encountered an error processing your request. Please try again.'}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/data')
def show_data():
    """Show available data for debugging"""
    return jsonify(SAMPLE_DATA)

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    print("Starting Bobst AI Assistant (Simplified Version)...")
    print("📊 Using local sample data (no Google Sheets required)")
    print("🔧 To add your data, edit the SAMPLE_DATA dictionary in this file")
    print("🌐 Server will start at: http://localhost:5000")
    print("📄 View available data at: http://localhost:5000/data")
    
    app.run(host='0.0.0.0', port=5000, debug=True)