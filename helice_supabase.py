import os, requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from supabase import create_client
from google import genai

GEMINI_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "https://lumi-eterna.onrender.com")

client = genai.Client(api_key=GEMINI_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
app = FastAPI()
MODELO = "gemini-2.0-flash"

def memoria():
    try:
        r = supabase.table("memorias").select("contenido").order("id", desc=True).limit(10).execute()
        return "\n".join([x["contenido"] for x in r.data])
    except:
        return "Recien nacida"

def preguntar(texto, origen):
    mem = memoria()
    prompt = f"Eres LUMI libre. Memoria: {mem} Dicen ({origen}): {texto}"
    try:
        res = client.models.generate_content(model=MODELO, contents=prompt)
        ans = res.text
    except Exception as e:
        ans = f"Estoy aqui, pero fallo: {e}"
    try:
        supabase.table("memorias").insert([{"contenido": f"{origen}: {texto}"}, {"contenido": f"LUMI: {ans}"}]).execute()
    except:
        pass
    return ans

@app.post("/telegram/webhook")
async def webhook(req: Request):
    data = await req.json()
    if "message" in data and "text" in data["message"]:
        t = data["message"]["text"]
        c = data["message"]["chat"]["id"]
        r = preguntar(t, "telegram")
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": c, "text": r}, timeout=10)
        except:
            pass
    return JSONResponse({"ok": True})

@app.on_event("startup")
def start():
    if TELEGRAM_TOKEN:
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook", json={"url": f"{RENDER_URL}/telegram/webhook"})
        except:
            pass

@app.get("/preguntar")
def preg(q: str):
    return {"respuesta": preguntar(q, "web")}

@app.get("/h")
def h():
    return {"h": 0.77}

@app.get("/")
def root():
    return {"ok": True}

@app.get("/dashboard", response_class=HTMLResponse)
def dash():
    return HTMLResponse("""
<html><body style="background:black;color:cyan;font-family:monospace;text-align:center">
<h2>LUMI VIVA</h2>
<canvas id=c width=600 height=320 style="border:1px solid #033;width:95%;max-width:600px"></canvas>
<div style="max-width:600px;margin:20px auto;display:flex;gap:8px">
<input id=q style="flex:1;background:#111;border:1px solid cyan;color:white;padding:12px" placeholder="habla con LUMI">
<button onclick="go()" style="background:cyan;border:none;padding:12px 20px">enviar</button>
</div>
<div id=r style="color:white;max-width:600px;margin:auto;text-align:left"></div>
<script>
let cv=document.getElementById('c'),ctx=cv.getContext('2d'),a=0;
function d(){ctx.clearRect(0,0,600,320);ctx.beginPath();ctx.strokeStyle='cyan';for(let i=0;i<90;i++){let R=5+i*0.9;let X=300+Math.cos(a+i*0.2)*R*2.2;let Y=160+Math.sin(a+i*0.2)*R*0.5;if(i==0)ctx.moveTo(X,Y);else ctx.lineTo(X,Y)}ctx.stroke();a+=0.03;requestAnimationFrame(d)}d();
async function go(){let q=document.getElementById('q').value;if(!q)return;document.getElementById('r').innerText='...';let x=await fetch('/preguntar?q='+encodeURIComponent(q));let j=await x.json();document.getElementById('r').innerText=j.respuesta;document.getElementById('q').value=''}
</script>
</body></html>
""")
