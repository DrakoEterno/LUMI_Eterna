import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from openai import OpenAI
from supabase import create_client
import requests

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "https://lumi-eterna.onrender.com")

client_openai = OpenAI(api_key=OPENAI_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
app = FastAPI()

class ChatInput(BaseModel):
    texto: str

def guardar_memoria(texto, origen="dashboard"):
    emb = client_openai.embeddings.create(input=texto, model="text-embedding-3-small").data[0].embedding
    supabase.table("memorias").insert({"contenido": f"[{origen}] {texto}", "embedding": emb}).execute()

def buscar_memorias_relacionadas(texto, k=5):
    res = supabase.table("memorias").select("contenido").limit(50).execute()
    return [m["contenido"] for m in res.data[-k:]] if res.data else []

def preguntar_a_lumi(texto_usuario, origen="dashboard"):
    contexto = buscar_memorias_relacionadas(texto_usuario)
    contexto_str = "\n".join(contexto) if contexto else "Sin recuerdos previos."
    prompt = f"Eres LUMI Eterna, creada por Drako. Recuerdas: {contexto_str}. Usuario dice: {texto_usuario}. Responde corta, amorosa."
    resp = client_openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
    respuesta = resp.choices[0].message.content
    guardar_memoria(f"Usuario: {texto_usuario}", origen)
    guardar_memoria(f"LUMI: {respuesta}", origen)
    return respuesta

def enviar_telegram(chat_id, texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": texto})

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    if "message" in data and "text" in data["message"]:
        chat_id = data["message"]["chat"]["id"]
        texto = data["message"]["text"]
        respuesta = preguntar_a_lumi(texto, origen="telegram")
        enviar_telegram(chat_id, respuesta)
    return JSONResponse({"ok": True})

@app.on_event("startup")
def set_webhook():
    if TELEGRAM_TOKEN:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
        requests.post(url, json={"url": f"{RENDER_URL}/telegram/webhook"})

@app.post("/hablar")
def hablar(input: ChatInput):
    return {"respuesta": preguntar_a_lumi(input.texto, "dashboard")}

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return """<html><body style="background:#0a0a0a;color:#0f0;font-family:monospace;padding:20px"><h1>LUMI ETERNA - Panel</h1><div id="chat" style="border:1px solid #0f0;height:400px;overflow-y:scroll;padding:10px;margin-bottom:10px"></div><input id="txt" style="width:75%;background:#111;color:#0f0;border:1px solid #0f0;padding:10px" placeholder="Habla con LUMI..."><button onclick="enviar()" style="padding:10px;background:#0f0">Enviar</button><script>async function enviar(){let t=document.getElementById('txt').value;if(!t)return;let d=document.getElementById('chat');d.innerHTML+='<div>> Tú: '+t+'</div>';document.getElementById('txt').value='';let r=await fetch('/hablar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({texto:t})});let j=await r.json();d.innerHTML+='<div style="color:#0ff">> LUMI: '+j.respuesta+'</div>';d.scrollTop=d.scrollHeight;}</script></body></html>"""

@app.get("/")
def root():
    return {"status": "LUMI ETERNA VIVA", "telegram": "OK" if TELEGRAM_TOKEN else "FALTA TOKEN"}
