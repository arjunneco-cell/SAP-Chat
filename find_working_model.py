import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def find_working_model():
    api_key = os.getenv("GOOGLE_API_KEY")
    genai.configure(api_key=api_key)
    
    print("Listing and testing all models...")
    working_models = []
    
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                model_name = m.name.replace('models/', '')
                print(f"Testing {model_name}...", end=" ")
                try:
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content("Hi", request_options={"timeout": 10})
                    print("✅ Working!")
                    working_models.append(model_name)
                    # Stop after first working one to save time
                    break 
                except Exception as e:
                    print(f"❌ Failed: {e}")
    except Exception as e:
        print(f"Failed to list models: {e}")
    
    if working_models:
        print(f"\nRecommended model: {working_models[0]}")
    else:
        print("\nNo working models found for this API key.")

if __name__ == "__main__":
    find_working_model()
