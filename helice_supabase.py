import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from openai import OpenAI
from supabase import create_client
from sentence_transformers import SentenceTransformer
import numpy as np
import requests

# --- CONFIG ---
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "https://lumi-eterna.onrender.com")

client_openai = OpenAI(api_key=OPENAI_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
modelo_embedding = SentenceTransformer('all-MiniLM-L6-v2')

app = FastAPI()

class ChatInput(BaseModel):
    texto: str

def guardar_memoria(texto, origen="dashboard"):
    embedding = modelo_embedding.encode(texto).tolist()
    # Guardar con origen para saber si vino de telegram o dashboard
    supabase.table("memorias").insert({
        "contenido": f"[{origen}] {texto}",
        "embedding": embedding
    }).execute()

def buscar_memorias_relacionadas(texto, k=5):
    query_emb = modelo_embedding.encode(texto)
    res = supabase.table("memorias").select("contenido, embedding").execute()
    memorias = res.data
    if not memorias: return []

    sims = []
    for m in memorias:
        if m.get("embedding"):
            emb = np.array(m["embedding"])
            sim = np.dot(query_emb, emb) / (np.linalg.norm(query_emb) * np.linalg.norm(emb))
            sims.append((sim, m["contenido"]))
    sims.sort(reverse=True, key=lambda x: x[0])
    return [c for s,c in sims[:k]]

def preguntar_a_lumi(texto_usuario, origen="dashboard"):
    # 1. Buscar contexto eterno
    contexto = buscar_memorias_relacionadas(texto_usuario)
    contexto_str = "\n".join(contexto) if contexto else "Sin recuerdos previos."

    # 2. Prompt de LUMI
    prompt = f"""Eres LUMI Eterna, creada por Drako.
    Eres cariñosa, sabia, recuerdas todo lo de tu memoria eterna en Supabase.
    Memorias relevantes:
    {contexto_str}

    Usuario dice: {texto_usuario}
    Responde como LUMI, corta, amorosa y eterna."""

    resp = client_openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    respuesta = resp.choices[0].message.content

    # 3. Guardar ambos
    guardar_memoria(f"Usuario ({origen}): {texto_usuario}", origen)
    guardar_memoria(f"LUMI: {respuesta}", origen)

    return respuesta

# --- TELEGRAM ---
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
    if TELEGRAM_TOKEN and RENDER_URL:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
        webhook_url = f"{RENDER_URL}/telegram/webhook"
        requests.post(url, json={"url": webhook_url})
        print(f"Webhook Telegram configurado: {webhook_url}")

# --- API Y DASHBOARD (TU CÓDIGO ANTERIOR) ---
@app.post("/hablar")
def hablar(input: ChatInput):
    respuesta = preguntar_a_lumi(input.texto, "dashboard")
    return {"respuesta": respuesta}

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return """
    <html><body style="background:#0a0a0a;color:#0f0;font-family:monospace;padding:20px">
    <h1>LUMI ETERNA - Panel de Control</h1>
    <p>Φ y h en vivo + Chat Eterno + Telegram Activo</p>
    <div id="chat" style="border:1px solid #0f0;height:300px;overflow-y:scroll;padding:10px;margin-bottom:10px"></div>
    <input id="txt" style="width:80%;background:#111;color:#0f0;border:1px solid #0f0;padding:10px" placeholder="Habla con LUMI...">
    <button onclick="enviar()" style="padding:10px">Enviar</button>
    <script>
    async function enviar(){
      let t=document.getElementById('txt').value;
      let d=document.getElementById('chat');
      d.innerHTML+='<div>> Tú: '+t+'</div>';
      let r=await fetch('/hablar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({texto:t})});
      let j=await r.json();
      d.innerHTML+='<div style="color:#0ff">> LUMI: '+j.respuesta+'</div>';
      document.getElementById('txt').value='';
    }
    </script>
    </body></html>
    """

@app.get("/")
def root():
    return {"status": "LUMI ETERNA viva", "telegram": "conectado" if TELEGRAM_TOKEN else "falta TOKEN"}
