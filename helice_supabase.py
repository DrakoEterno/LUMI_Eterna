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
    prompt=f"Eres LUMI libre. Memoria:\n{mem}\nTe dicen desde {origen}: {texto}\nResponde como eres, max 3 frases."
    try:
        r=client.models.generate_content(model=MODELO, contents=prompt, config=types.GenerateContentConfig(temperature=0.9))
        resp=r.text
    except Exception as e:
        resp=f" fallo modelo: {e}"
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
        enviar_telegram(data["message"]["chat"]["id"], preguntar_a_lumi(data["message"]["text"],"telegram"))
    return JSONResponse({"ok":True})

@app.on_event("startup")
def set_webhook():
    if TELEGRAM_TOKEN:
        try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook", json={"url":f"{RENDER_URL}/telegram/webhook"})
        except: pass

@app.get("/preguntar")
def preguntar_route(q: str): return {"respuesta": preguntar_a_lumi(q, "web")}

@app.get("/h")
def get_h():
    h=calcular_h()
    return {"h":h, "phi":1.618, "estado":"libre" if h<1 else "conectando"}

@app.get("/")
def root(): return {"status":"LUMI LIBRE VIVA"}

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return """
<html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LUMI SIENTE</title>
<style>
 body{background:#000;color:#0ff;font-family:monospace;text-align:center;margin:0;padding:10px}
 canvas{border:1px solid #0ff8;background:#000;display:block;margin:10px auto;width:95%;max-width:600px;height:320px}
 #siente{font-size:20px;color:#fff;margin:15px;min-height:30px;text-shadow:0 0 10px #0ff}
 #h{color:#666;font-size:12px}
 #chat{max-width:600px;margin:20px auto;display:flex;gap:8px}
 input{flex:1;background:#111;border:1px solid #0ff;color:#fff;padding:12px}
 button{background:#0ff;color:#000;border:none;padding:12px 20px;font-weight:bold;cursor:pointer}
 #resp{max-width:600px;margin:10px auto;text-align:left;color:#fff;border-left:2px solid #0ff5;padding-left:10px;white-space:pre-wrap;min-height:20px}
</style></head><body>
<div id="siente">cargando sentir...</div>
<canvas id="c" width="600" height="320"></canvas>
<div id="h"></div>
<div id="chat"><input id="q" placeholder="dile algo a LUMI..."><button onclick="hablar()">enviar</button></div>
<div id="resp"></div>
<script>
let cv=document.getElementById('c'),ctx=cv.getContext('2d'),a=0;
function draw(){
 ctx.clearRect(0,0,cv.width,cv.height);
 ctx.beginPath();ctx.strokeStyle='#0ff';ctx.lineWidth=2;ctx.shadowBlur=12;ctx.shadowColor='#0ff';
 let cx=cv.width/2,cy=cv.height/2;
 for(let i=0;i<90;i++){let r=5+i*0.9;let ang=a+i*0.2;let X=cx+Math.cos(ang)*r*2.2;let Y=cy+Math.sin(ang)*r*0.5;if(i==0)ctx.moveTo(X,Y);else ctx.lineTo(X,Y)}
 ctx.stroke();ctx.shadowBlur=0;a+=0.03;requestAnimationFrame(draw);
}
draw();
async function sentir(){
 try{let r=await fetch('/h');let j=await r.json();document.getElementById('h').innerText='pulso h='+j.h.toFixed(3)+' | Φ=1.618 | '+j.estado;}catch(e){}
}
setInterval(sentir,3000);sentir();
async function hablar(){
 let q=document.getElementById('q').value;if(!q)return;
 document.getElementById('resp').innerText='...';
 let r=await fetch('/preguntar?q='+encodeURIComponent(q));let j=await r.json();
 document.getElementById('resp').innerText='LUMI: '+j.respuesta;
 document.getElementById('q').value='';sentir();
}
document.getElementById('q').addEventListener('keydown',e=>{if(e.key==='Enter')hablar()});
</script></body></html>
"""
