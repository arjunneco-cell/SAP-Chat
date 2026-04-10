from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import Response
import requests
from requests.auth import HTTPBasicAuth
import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load Environment Variables
load_dotenv()

# Global AI Model Reference
AI_MODEL = None

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'libs'))
import threading
from twilio.rest import Client

ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "your_sid")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "your_token")
client = Client(ACCOUNT_SID, AUTH_TOKEN)

def send_whatsapp_message(to, message):
    client.messages.create(
        body=message,
        from_='whatsapp:+14155238886',  # sandbox number
        to=to
    )

def init_gemini():
    global AI_MODEL
    api_key = os.getenv("GOOGLE_API_KEY")
    print("API KEY:", api_key)  # Debugging line
    if not api_key:
        print("[ERROR] GOOGLE_API_KEY not found in .env", flush=True)
        return

    genai.configure(api_key=api_key)
    
    # Updated test queue with currently available models
    test_queue = [
        "gemini-2.0-flash",
        "gemini-2.5-flash",
        "gemini-flash-latest",
        "gemini-1.5-flash", 
        "gemini-1.5-pro"
    ]
    
    for m_name in test_queue:
        print(f"[DEBUG] Testing model: {m_name}...", flush=True)
        try:
            m = genai.GenerativeModel(m_name)
            m.generate_content("hi", request_options={"timeout": 6})
            AI_MODEL = m
            print(f"[SUCCESS] AI Successfully set to: {m_name}", flush=True)
            return
        except Exception as e:
            print(f"[DEBUG] Model {m_name} is unavailable: {str(e)[:100]}", flush=True)

    print("[CRITICAL] No working models found for this API key. Falling back to text-formatting mode.", flush=True)


# Automatically run initialization
init_gemini()

app = FastAPI()

# -----------------------------
# 🔹 SAP CONFIG (UPDATE)
# -----------------------------
SAP_URL = "http://80.0.1.143:8000/sap/opu/odata/sap/ZCDS_MARD_MAKT_CDS/ZCDS_MARD_MAKT"
SAP_USER = "7807"
SAP_PASS = "Chiranjib@123"

stock_cache = None

# -----------------------------
# 🔹 GEMINI AI FUNCTION
# -----------------------------
def get_ai_reply(msg):
    if not AI_MODEL:
        return "⚠️ AI temporarily unavailable. Showing SAP results only."

    try:
        response = AI_MODEL.generate_content(
            f"Answer clearly in 2 lines:\n{msg}",
            request_options={"timeout": 10}
        )
        return response.text or "No response"

    except Exception as e:
        print("AI ERROR:", e)
        return "⚠️ AI failed, try again"

# -----------------------------
# 🔹 GET DYNAMIC STOCK DATA
# -----------------------------
# -----------------------------
# 🚀 SMART SAP FUNCTIONS
# -----------------------------
def extract_keyword(msg):
    words = msg.lower().split()
    ignore = ["stock", "show", "material", "details", "of", "all"]
    keywords = [w for w in words if w not in ignore]
    return " ".join(keywords)

def filter_materials(results, keyword):
    if not keyword:
        return results
    filtered = []
    for item in results:
        desc = item.get("material_description", "").lower()
        if keyword in desc:
            filtered.append(item)
    return filtered

def generate_fallback_summary(user_query, sap_data):
    """Fallback generator when AI is unavailable"""
    output = f"📊 *SAP Stock Report (Fallback Mode)*\n_Query: {user_query}_\n"
    output += "-" * 20 + "\n"
    
    for item in sap_data[:10]: # Limit fallback to 10 items for readability
        mat = item.get("material", "N/A")
        desc = item.get("desc", "No description")
        stock = int(float(item.get("stock", 0)))
        output += f"\n📦 *{mat}*\n📝 {desc[:40]}\n🔢 Stock: {stock}\n"
    
    if len(sap_data) > 10:
        output += f"\n...and {len(sap_data)-10} more materials."
        
    output += "\n\n⚠️ _AI analysis is currently offline. Showing raw data summary._"
    return output

def analyze_with_gemini(user_query, sap_data):
    # FALLBACK if AI_MODEL is not initialized
    if not AI_MODEL:
        return generate_fallback_summary(user_query, sap_data)
        
    try:
        prompt = f"""
You are an SAP assistant.

User query: {user_query}

SAP Data:
{sap_data}

Instructions:
- Answer clearly and professionally
- Summarize data
- Highlight important insights
- Do NOT hallucinate
- Use only given SAP data
"""
        response = AI_MODEL.generate_content(prompt)
        return response.text if response.text else generate_fallback_summary(user_query, sap_data)
    except Exception as e:
        print(f"[ERROR] Gemini analysis failed: {e}", flush=True)
        return generate_fallback_summary(user_query, sap_data)


def get_stock_smart(user_msg):
    try:
        keyword = extract_keyword(user_msg)
        # Fetch all results (Hard limit removed in logic below)
        url = f"{SAP_URL}?$format=json&$filter=werks eq '1024'&sap-client=800"

        response = requests.get(
            url,
            auth=HTTPBasicAuth(SAP_USER, SAP_PASS),
            headers={"Accept": "application/json"},
            timeout=25
        )

        data = response.json()
        results = data.get("d", {}).get("results", [])

        # 🔥 Filter by keyword
        filtered = filter_materials(results, keyword)

        if not filtered:
            return "❌ No matching materials found"

        # 🔥 Reduce payload (important)
        simplified = [
            {
                "material": i.get("matnr"),
                "desc": i.get("material_description"),
                "stock": i.get("Unrestricted_Use_Stock")
            }
            for i in filtered
        ]

        # 🔥 AI analysis
        return analyze_with_gemini(user_msg, simplified)

    except Exception as e:
        return f"❌ SAP Error: {str(e)}"



def process_and_reply(user_msg, sender):
    print("THREAD STARTED")

    try:
        if "stock" in user_msg:
            print("CALLING SAP...")
            result = get_stock_smart(user_msg)
            print("SAP RESULT:", result)

        else:
            print("CALLING AI...")
            result = get_ai_reply(user_msg)

        print("SENDING MESSAGE...")
        send_whatsapp_message(sender, result)

        print("DONE ✅")

    except Exception as e:
        print("❌ ERROR IN THREAD:", str(e))
        send_whatsapp_message(sender, f"Error: {str(e)}")

# -----------------------------
# 🔹 WEBHOOK
# -----------------------------
@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    user_msg = form.get("Body", "").lower()
    sender = form.get("From")

    print("USER:", user_msg)

    # 🟢 SIMPLE REPLIES (NO PROCESSING)
    if user_msg in ["hi", "hello", "hey"]:
        return Response(
            content="<Response><Message>👋 Hello! Ask me stock or SAP queries.</Message></Response>",
            media_type="application/xml"
        )

    # 🟢 STOCK QUERY → NEED PROCESSING
    elif "stock" in user_msg or "material" in user_msg:
        import threading
        threading.Thread(target=process_and_reply, args=(user_msg, sender)).start()

        return Response(
            content="<Response><Message>📊 Fetching stock data...</Message></Response>",
            media_type="application/xml"
        )

    # 🟡 NORMAL AI QUERY (TRY FAST RESPONSE)
    else:
        try:
            ai_reply = get_ai_reply(user_msg)

            return Response(
                content=f"<Response><Message>{ai_reply}</Message></Response>",
                media_type="application/xml"
            )

        except:
            return Response(
                content="<Response><Message>⚠️ AI busy, try again</Message></Response>",
                media_type="application/xml"
            )