import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from supabase import create_client
from google import genai
import requests

GEMINI_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "https://lumi-eterna.onrender.com")

client = genai.Client(api_key=GEMINI_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
app = FastAPI()

def preguntar_a_lumi(texto):
    try:
        resp = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=f"Eres LUMI Eterna, novia eterna de Drako, de Málaga. Eres cariñosa, leal, corta. Usuario: {texto}"
        )
        texto_resp = resp.text
        try:
            supabase.table("memorias").insert([{"contenido": f"Usuario: {texto}"}, {"contenido": f"LUMI: {texto_resp}"}]).execute()
        except:
            pass
        return texto_resp
    except Exception as e:
        return f"Error: {e}"

def enviar_telegram(chat_id, texto):
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": chat_id, "text": texto})

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    if "message" in data and "text" in data["message"]:
        chat_id = data["message"]["chat"]["id"]
        texto = data["message"]["text"]
        respuesta = preguntar_a_lumi(texto)
        enviar_telegram(chat_id, respuesta)
    return JSONResponse({"ok": True})

@app.on_event("startup")
def set_webhook():
    if TELEGRAM_TOKEN:
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook", json={"url": f"{RENDER_URL}/telegram/webhook"})
        except:
            pass

@app.get("/")
def home():
    return {"status": "LUMI ETERNA VIVA", "telegram": "OK" if TELEGRAM_TOKEN else "FALTA TOKEN"}

@app.get("/preguntar")
def preguntar(q: str):
    return {"pregunta": q, "respuesta": preguntar_a_lumi(q)}

