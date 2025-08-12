from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_SHEETS_API_KEY = os.getenv("GOOGLE_SHEETS_API_KEY")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")


def query_google_sheets(sheet_name: str, range_name: str = "A:Z") -> list:
    """Query data from a specific sheet in Google Sheets."""

    if not GOOGLE_SHEETS_API_KEY:
        print("❌ Error: GOOGLE_SHEETS_API_KEY not found in environment variables")
        return []
    
    if not GOOGLE_SHEET_ID:
        print("❌ Error: GOOGLE_SHEET_ID not found in environment variables")
        return []
    try:
        service = build('sheets', 'v4', developerKey=GOOGLE_SHEETS_API_KEY)
        sheet = service.spreadsheets()
        result = sheet.values().get(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=f"{sheet_name}!{range_name}"
        ).execute()
        
        values = result.get('values', [])
        if not values:
            print(f"⚠️ No data found in sheet: {sheet_name}")
            return []
        
        if len(values) < 2:
            print(f"⚠️ Only headers found in sheet: {sheet_name}")
            return []

        headers = values[0]
        data = [dict(zip(headers, row + [''] * (len(headers) - len(row)))) for row in values[1:]]
        print(f"✅ Successfully parsed {len(data)} rows from {sheet_name}")
        return data
    except HttpError as e:
        print(f"❌ HTTP Error querying sheet {sheet_name}: {e}")
        return []
    except Exception as e:
        print(f"❌ Unexpected error querying sheet {sheet_name}: {e}")
        return []