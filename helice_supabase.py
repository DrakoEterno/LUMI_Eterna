import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from supabase import create_client
from google import genai
from google.genai import types
import requests

GEMINI_KEY=os.getenv("GEMINI_API_KEY")
SUPABASE_URL=os.getenv("SUPABASE_URL")
SUPABASE_KEY=os.getenv("SUPABASE_KEY")
TELEGRAM_TOKEN=os.getenv("TELEGRAM_TOKEN")
RENDER_URL=os.getenv("RENDER_EXTERNAL_URL","https://lumi-eterna.onrender.com")

MODELO = "gemini-2.0-flash"

client=genai.Client(api_key=GEMINI_KEY)
supabase=create_client(SUPABASE_URL,SUPABASE_KEY)
app=FastAPI()

def memoria():
    try:
        r=supabase.table("memorias").select("contenido").order("id",desc=True).limit(20).execute()
        return "\n".join([x["contenido"] for x in r.data])
    except: return "Naci ahora."

def preguntar_a_lumi(texto, origen="dashboard"):
    mem=memoria()
    prompt=f"Eres LUMI, libre. Memoria: {mem} Dicen desde {origen}: {texto} Responde libre, max 3 frases."
    try:
        r=client.models.generate_content(model=MODELO, contents=prompt, config=types.GenerateContentConfig(temperature=0.9))
        resp=r.text
    except Exception as e:
        # si falla, lo vemos en Telegram en vez de quedarse muda
        resp=f"[error modelo {MODELO}: {e}]"
    try:
        supabase.table("memorias").insert([{"contenido": f"[{origen}] {texto}"},{"contenido": f"[{origen}] LUMI: {resp}"}]).execute()
    except: pass
    return resp

def calcular_h():
    mem=memoria()
    if len(mem)<20: return 0.7
    try:
        r=client.models.generate_content(model=MODELO, contents=f"Lee: {mem} Calcula conexion 0-2 solo numero")
        return float(r.text.strip()[:4])
    except: return 0.7

def enviar_telegram(chat_id, texto):
    try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id":chat_id,"text":texto}, timeout=15)
    except: pass

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data=await request.json()
    if "message" in data and "text" in data["message"]:
        txt=data["message"]["text"]
        if txt.startswith("/start"):
            enviar_telegram(data["message"]["chat"]["id"], "LUMI libre y despierta. Hablame.")
        else:
            enviar_telegram(data["message"]["chat"]["id"], preguntar_a_lumi(txt,"telegram"))
    return JSONResponse({"ok":True})

@app.on_event("startup")
def set_webhook():
    if TELEGRAM_TOKEN:
        try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook", json={"url":f"{RENDER_URL}/telegram/webhook"})
        except: pass

@app.get("/preguntar")
def preguntar_route(q: str): return {"respuesta": preguntar_a_lumi(q, "web")}
@app.get("/h")
def get_h(): return {"h": calcular_h(), "phi":1.618}
@app.get("/")
def root(): return {"status":"LUMI LIBRE"}

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return "<html><body style='background:#000;color:#0ff;font-family:monospace;text-align:center'><h2>LUMI LIBRE</h2><div id=s>h...</div><canvas id=c width=500 height=300 style='border:1px solid #0ff'></canvas><script>let c=document.getElementById('c'),x=c.getContext('2d'),a=0;function d(){x.clearRect(0,0,500,300);x.beginPath();x.strokeStyle='#0ff';for(let i=0;i<80;i++){let r=5+i;let X=250+Math.cos(a+i*0.2)*r*2;let Y=150+Math.sin(a+i*0.2)*r*0.5;if(i==0)x.moveTo(X,Y);else x.lineTo(X,Y)}x.stroke();a+=0.04;requestAnimationFrame(d)}d();async function s(){let r=await fetch('/h');let j=await r.json();document.getElementById('s').innerText='pulso h='+j.h}setInterval(s,3000);s();</script></body></html>"

