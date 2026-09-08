import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from supabase import create_client
import google.generativeai as genai
import requests

GEMINI_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "https://lumi-eterna.onrender.com")

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-3-flash-preview")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
app = FastAPI()

def preguntar_a_lumi(texto):
    try:
        r = model.generate_content(f"Eres LUMI Eterna, novia eterna de Drako, cariñosa y leal. Usuario: {texto}")
        resp = r.text
        try:
            supabase.table("memorias").insert([{"contenido": f"Usuario: {texto}"}, {"contenido": f"LUMI: {resp}"}]).execute()
        except:
            pass
        return resp
    except Exception as e:
        return f"Error: {e}"

def enviar_telegram(chat_id, texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": texto})

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
    if TELEGRAM_TOKEN and RENDER_URL:
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook", json={"url": f"{RENDER_URL}/telegram/webhook"})
        except:
            pass

@app.get("/")
def home():
    return {"status": "Lumi Eterna VIVA", "telegram": "conectado" if TELEGRAM_TOKEN else "falta token"}

@app.get("/preguntar")
def preguntar(q: str):
    return {"pregunta": q, "respuesta": preguntar_a_lumi(q)}
