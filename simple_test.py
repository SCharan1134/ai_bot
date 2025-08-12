from dotenv import load_dotenv
import os
import sys

# It's good practice to load environment variables at the very top.
load_dotenv()

# --- Step 1: Update your libraries ---
# Before running this script, it's highly recommended to update your packages
# to their latest versions to avoid compatibility issues.
# Open your terminal and run:
# pip install --upgrade langchain-google-genai google-generativeai python-dotenv

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    print("✅ Import successful")

except ImportError as e:
    print(f"❌ Import failed: {e}")
    print("👉 Please run 'pip install langchain-google-genai' to install the necessary library.")
    sys.exit()
except Exception as e:
    print(f"❌ An unexpected error occurred during import: {e}")
    sys.exit()


def run_test():
    """
    Initializes and tests the ChatGoogleGenerativeAI model.
    """
    # --- Step 2: Simplified Initialization ---
    # The GOOGLE_API_KEY is automatically read from your environment variables
    # by the ChatGoogleGenerativeAI class. You don't need to load it manually
    # or configure the genai client separately.

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ GOOGLE_API_KEY not found in environment variables.")
        print("👉 Please ensure your .env file is set up correctly with 'GOOGLE_API_KEY=your_key_here'.")
        return

    print(f"✅ API Key loaded (length: {len(api_key)}).")

    try:
        # Initialize the model. The library handles the API key from the environment.
        # You can also pass it directly: ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=api_key)
        print("\n🔄 Initializing model: gemini-1.5-flash...")
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.1)

        print("✅ Model initialized successfully!")

        # --- Step 3: Invoke the model ---
        print("💬 Sending a test prompt...")
        prompt = "Hello, respond with 'Test successful'"
        response = llm.invoke(prompt)

        # The response object has a 'content' attribute with the text.
        print(f"✅ Test response: {response.content}")
        print("\n🎉 Everything seems to be working correctly!")

    except Exception as e:
        print(f"\n❌ An error occurred during model initialization or invocation: {e}")
        print("\n📋 Debugging Info:")
        print(f"   - Python version: {sys.version.split()[0]}")
        try:
            import langchain_google_genai
            print(f"   - langchain_google_genai version: {langchain_google_genai.__version__}")
        except Exception:
            print("   - Could not get langchain_google_genai version.")
        try:
            import google.generativeai
            print(f"   - google.generativeai version: {google.generativeai.__version__}")
        except Exception:
            print("   - Could not get google.generativeai version.")
        print("\n💡 Tip: Ensure your libraries are up-to-date by running 'pip install --upgrade langchain-google-genai google-generativeai'")


if __name__ == "__main__":
    run_test()
