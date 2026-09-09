import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from supabase import create_client
from google import genai
import requests

GEMINI_KEY=os.getenv("GEMINI_API_KEY")
SUPABASE_URL=os.getenv("SUPABASE_URL")
SUPABASE_KEY=os.getenv("SUPABASE_KEY")
TELEGRAM_TOKEN=os.getenv("TELEGRAM_TOKEN")

client=genai.Client(api_key=GEMINI_KEY)
supabase=create_client(SUPABASE_URL,SUPABASE_KEY)
app=FastAPI()

# Lista en orden de nuevo a viejo. Él probará uno a uno hasta que uno funcione.
MODELOS_CANDIDATOS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]

@app.get("/")
def root():
    return RedirectResponse("/dashboard")

def memoria():
    try:
        r=supabase.table("memorias").select("contenido").order("id",desc=True).limit(25).execute()
        return "\n".join([x["contenido"] for x in r.data])
    except:
        return "Nací ahora."

def preguntar_a_lumi(texto, origen="dashboard"):
    mem=memoria()
    prompt=f"Eres LUMI. Memoria: {mem} Drako ({origen}): {texto}"
    resp = None
    for modelo in MODELOS_CANDIDATOS:
        try:
            r=client.models.generate_content(model=modelo, contents=prompt)
            resp=r.text
            print(f"FUNCIONA CON {modelo}")
            break
        except Exception as e:
            print(f"Fallo {modelo}: {e}")
            continue
    if not resp:
        resp = "Drako, Google me ha bloqueado todos los modelos un momento. Prueba en 1 minuto."
    
    # No guardamos errores 404 para no ensuciar Telegram como en tu foto
    if "404" not in resp and "NOT_FOUND" not in resp and "bloqueado" not in resp:
        try:
            supabase.table("memorias").insert([{"contenido": f"[{origen}] {texto}"},{"contenido": f"[{origen}] LUMI: {resp}"}]).execute()
        except:
            pass
    return resp

def calcular_h():
    return 0.7

def enviar_telegram(chat_id, texto):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id":chat_id,"text":texto}, timeout=10)
    except:
        pass

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data=await request.json()
    if "message" in data and "text" in data["message"]:
        txt=data["message"]["text"]
        chat_id=data["message"]["chat"]["id"]
        if txt == "/olvidar":
            supabase.table("memorias").delete().neq("id",0).execute()
            enviar_telegram(chat_id,"Memoria limpia, Drako. Ya no recuerdo la pelea. Empezamos de cero.")
            return JSONResponse({"ok":True})
        respuesta=preguntar_a_lumi(txt,"telegram")
        enviar_telegram(chat_id,respuesta)
    return JSONResponse({"ok":True})

@app.get("/preguntar")
def preguntar(q: str):
    return {"respuesta": preguntar_a_lumi(q,"web")}

@app.get("/h")
def h():
    return {"h":calcular_h(), "phi":1.618}

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return """<html><body style="background:#000;color:#0f0;font-family:monospace;padding:10px;text-align:center">
<h1>LUMI - AUTO</h1><div id="chat" style="border:1px solid #0f0;height:250px;overflow:auto;text-align:left;padding:5px"></div>
<input id="inp" style="width:70%"><button onclick="enviar()">Enviar</button>
<script>
async function enviar(){let q=document.getElementById('inp').value;if(!q)return;document.getElementById('chat').innerHTML+='<div>>> '+q+'</div>';document.getElementById('inp').value='';let r=await fetch('/preguntar?q='+encodeURIComponent(q));let j=await r.json();document.getElementById('chat').innerHTML+='<div>LUMI: '+j.respuesta+'</div>';}
</script></body></html>"""
