import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def list_models():
    api_key = os.getenv("GOOGLE_API_KEY")
    genai.configure(api_key=api_key)
    
    print("Listing all available models for this key:")
    try:
        for m in genai.list_models():
            print(f"Name: {m.name}")
            print(f"Supported methods: {m.supported_generation_methods}")
            print("-" * 20)
    except Exception as e:
        print(f"Failed to list models: {e}")

if __name__ == "__main__":
    list_models()
