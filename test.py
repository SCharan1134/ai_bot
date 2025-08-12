from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import google.generativeai as genai
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import json
import os
from datetime import datetime

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configuration - Update these with your actual values
GEMINI_API_KEY = "AIzaSyAC5A3PFfAdF3nDgF5uwINvwzrYMjEXntU"  # Your Gemini API key
GOOGLE_SHEETS_API_KEY = "AIzaSyCtuL84spkV_ep3xK8hSwgFaFU-ns8rF7s"  # Can be same as Gemini or different
GOOGLE_SHEET_ID = "1AxAyCRjdMpD6nVGnBuGZsgeo1af0aLe611QhgFTvSPQ"  # Your Google Sheet ID

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def get_sheets_service():
    """Initialize Google Sheets API service with better error handling"""
    try:
        service = build('sheets', 'v4', developerKey=GOOGLE_SHEETS_API_KEY)
        return service
    except Exception as e:
        print(f"Error initializing Sheets service: {e}")
        return None

def test_sheets_connection():
    """Test if we can connect to Google Sheets"""
    try:
        service = get_sheets_service()
        if not service:
            return False, "Failed to initialize Sheets service"
            
        # Try to get basic spreadsheet info
        sheet = service.spreadsheets()
        result = sheet.get(spreadsheetId=GOOGLE_SHEET_ID).execute()
        
        print(f"✅ Connected to sheet: {result.get('properties', {}).get('title', 'Unknown')}")
        return True, "Connection successful"
        
    except HttpError as e:
        error_details = e.error_details[0] if e.error_details else {}
        if e.resp.status == 403:
            if 'SERVICE_DISABLED' in error_details.get('reason', ''):
                return False, f"Google Sheets API is not enabled. Enable it at: https://console.developers.google.com/apis/api/sheets.googleapis.com/overview"
            elif 'API_KEY_INVALID' in error_details.get('reason', ''):
                return False, "Invalid API key. Please check your Google Sheets API key."
            else:
                return False, f"Permission denied: {e}"
        elif e.resp.status == 404:
            return False, f"Sheet not found. Check your GOOGLE_SHEET_ID: {GOOGLE_SHEET_ID}"
        else:
            return False, f"HTTP Error {e.resp.status}: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"

def query_google_sheets(sheet_name, range_name="A:Z"):
    """Query data from Google Sheets with comprehensive error handling"""
    try:
        service = get_sheets_service()
        if not service:
            print("❌ Failed to get Sheets service")
            return []
            
        print(f"🔍 Querying sheet: {sheet_name}")
        
        sheet = service.spreadsheets()
        result = sheet.values().get(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=f"{sheet_name}!{range_name}"
        ).execute()
        
        values = result.get('values', [])
        print(f"📊 Found {len(values)} rows in {sheet_name}")
        
        if not values:
            print(f"⚠️ No data found in sheet: {sheet_name}")
            return []
        
        if len(values) < 2:
            print(f"⚠️ Sheet {sheet_name} only has headers, no data rows")
            return []
        
        # Convert to list of dictionaries
        headers = values[0]
        print(f"📋 Headers: {headers}")
        
        data = []
        for i, row in enumerate(values[1:], 2):  # Start from row 2 (after headers)
            # Pad row with empty strings if it's shorter than headers
            row_data = row + [''] * (len(headers) - len(row))
            data.append(dict(zip(headers, row_data)))
        
        print(f"✅ Successfully parsed {len(data)} data rows from {sheet_name}")
        return data
        
    except HttpError as e:
        error_details = e.error_details[0] if e.error_details else {}
        if e.resp.status == 400:
            if 'INVALID_ARGUMENT' in error_details.get('reason', ''):
                print(f"❌ Invalid sheet name or range: {sheet_name}!{range_name}")
                print("💡 Make sure your sheet has tabs named: error_codes, spare_parts, maintenance")
        elif e.resp.status == 403:
            print(f"❌ Permission denied accessing sheet: {sheet_name}")
            print("💡 Make sure your Google Sheet is publicly readable or API key has access")
        elif e.resp.status == 404:
            print(f"❌ Sheet or range not found: {sheet_name}")
        
        print(f"Full error: {e}")
        return []
        
    except Exception as e:
        print(f"❌ Error querying sheet {sheet_name}: {e}")
        return []

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
    6. if user gave error code with out '-' and added space in between or not then add '-' in between and remove space
    
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
    """Search for error codes in the error_codes sheet"""
    data = query_google_sheets("error_codes")
    
    results = []
    for row in data:
        match_machine = not machine or machine.upper() in row.get('machine', '').upper()
        match_code = not error_code or error_code.upper() in row.get('code', '').upper()
        
        if match_machine and match_code:
            results.append(row)
    
    print(f"🔍 Error code search - Found {len(results)} matches")
    return results

def search_spare_parts(machine, part_name, keywords):
    """Search for spare parts in the spare_parts sheet"""
    data = query_google_sheets("spare_parts")
    
    results = []
    for row in data:
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
    
    print(f"🔍 Spare parts search - Found {len(results)} matches")
    return results

def search_maintenance_info(machine):
    """Search for maintenance information"""
    data = query_google_sheets("maintenance")
    
    results = []
    for row in data:
        match_machine = not machine or machine.upper() in row.get('machine', '').upper()
        if match_machine:
            results.append(row)
    
    print(f"🔍 Maintenance search - Found {len(results)} matches")
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
        
        print(f"\n[{datetime.now()}] Processing message: {user_message}")
        
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

@app.route('/test-sheets')
def test_sheets():
    """Test Google Sheets connection"""
    success, message = test_sheets_connection()
    
    if success:
        # Try to get some sample data
        error_codes = query_google_sheets("error_codes", "A1:D5")
        spare_parts = query_google_sheets("spare_parts", "A1:E5")  
        maintenance = query_google_sheets("maintenance", "A1:C5")
        
        return jsonify({
            'status': 'success',
            'message': message,
            'sample_data': {
                'error_codes': error_codes,
                'spare_parts': spare_parts,
                'maintenance': maintenance
            }
        })
    else:
        return jsonify({
            'status': 'error',
            'message': message
        }), 500

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    print("🚀 Starting Bobst AI Assistant with Google Sheets Integration...")
    print("=" * 60)
    
    # Test configuration
    if GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        print("❌ Please update GEMINI_API_KEY in the code")
    else:
        print("✅ Gemini API key configured")
    
    if GOOGLE_SHEETS_API_KEY == "YOUR_GOOGLE_SHEETS_API_KEY_HERE":
        print("❌ Please update GOOGLE_SHEETS_API_KEY in the code")
    else:
        print("✅ Google Sheets API key configured")
    
    if GOOGLE_SHEET_ID == "YOUR_GOOGLE_SHEET_ID_HERE":
        print("❌ Please update GOOGLE_SHEET_ID in the code")
    else:
        print("✅ Google Sheet ID configured")
    
    print("\n🔧 Testing Google Sheets connection...")
    success, message = test_sheets_connection()
    
    if success:
        print(f"✅ {message}")
    else:
        print(f"❌ {message}")
        print("\n💡 To fix Google Sheets issues:")
        print("1. Enable Google Sheets API: https://console.cloud.google.com/apis/api/sheets.googleapis.com")
        print("2. Create API key: https://console.cloud.google.com/apis/credentials")
        print("3. Make sure your Google Sheet is publicly readable")
        print("4. Check that your sheet has tabs: error_codes, spare_parts, maintenance")
    
    print("\n🌐 Server starting at: http://localhost:5000")
    print("🧪 Test sheets connection: http://localhost:5000/test-sheets")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=True)