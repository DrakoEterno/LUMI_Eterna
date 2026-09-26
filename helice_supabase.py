import os
import io
import re
import json
import asyncio
import logging
import urllib.parse
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel
import httpx
import google.generativeai as genai
from supabase import create_client, Client
from gtts import gTTS

# ==========================================
# 1. CONFIGURACIÓN E INICIALIZACIÓN
# ==========================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DRAKO_CHAT_ID = os.getenv("DRAKO_CHAT_ID")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        logging.error(f"Error conectando a Supabase: {e}")

# ==========================================
# 2. ESTADO CEREBRAL (HOMEOSTASIS SAFE)
# ==========================================
class CerebroEstado:
    def __init__(self):
        self.dopamina: float = 0.70
        self.norepinefrina: float = 0.30
        self.adenosina: float = 0.20
        self.curiosidad: float = 0.80
        self.energia: float = 0.90
        self.durmiendo: bool = False
        self.fase_sueno: str = "VIGILIA"
        self.ram_cognitiva: List[Dict[str, str]] = []
        self.max_ram: int = 10
        self.cargar_estado_persistent()

    def cargar_estado_persistent(self):
        if not supabase:
            return
        try:
            res = supabase.table("estado_cerebral").select("*").order("created_at", desc=True).limit(1).execute()
            if res.data and len(res.data) > 0:
                estado = res.data[0]
                self.dopamina = float(estado.get("dopamina") if estado.get("dopamina") is not None else 0.70)
                self.norepinefrina = float(estado.get("norepinefrina") if estado.get("norepinefrina") is not None else 0.30)
                self.adenosina = float(estado.get("adenosina") if estado.get("adenosina") is not None else 0.20)
                self.durmiendo = bool(estado.get("durmiendo", False))
                self.fase_sueno = str(estado.get("fase_sueno") or "VIGILIA")
        except Exception as e:
            logging.error(f"Error cargando Supabase: {e}")

    def guardar_estado_persistent(self):
        if not supabase:
            return
        try:
            supabase.table("estado_cerebral").insert({
                "dopamina": self.dopamina,
                "norepinefrina": self.norepinefrina,
                "adenosina": self.adenosina,
                "durmiendo": self.durmiendo,
                "fase_sueno": self.fase_sueno
            }).execute()
        except Exception as e:
            logging.error(f"Error guardando Supabase: {e}")

    def actualizar_homeostasis(self, impacto_emocional: float = 0.0):
        self.adenosina = min(1.0, max(0.0, self.adenosina + 0.04))
        self.energia = min(1.0, max(0.1, 1.0 - (self.adenosina * 0.85)))
        if impacto_emocional > 0:
            self.dopamina = min(1.0, max(0.0, self.dopamina + (impacto_emocional * 0.15)))
            self.norepinefrina = min(1.0, max(0.0, self.norepinefrina + 0.08))
        else:
            self.dopamina = max(0.1, self.dopamina - 0.03)
            self.norepinefrina = max(0.1, self.norepinefrina - 0.04)
            
        self.guardar_estado_persistent()

    def agregar_a_ram(self, rol: str, contenido: str):
        self.ram_cognitiva.append({"rol": str(rol), "contenido": str(contenido)})
        if len(self.ram_cognitiva) > self.max_ram:
            self.ram_cognitiva.pop(0)

cerebro = CerebroEstado()

# ==========================================
# 3. GENERACIÓN DE AUDIO A VELOCIDAD NORMAL
# ==========================================
def generar_audio_voice(texto: str) -> bytes:
    texto_limpio = re.sub(r'\[IMAGEN_MENTAL:\s*.*?\]', '', texto)
    texto_limpio = re.sub(r'[*_~`#]', '', texto_limpio).strip()
    if not texto_limpio:
        texto_limpio = "Mensaje procesado."
    
    tts = gTTS(text=texto_limpio, lang='es', tld='es', slow=False)
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    return fp.read()

# ==========================================
# 4. LÓGICA PRINCIPAL (CEREBRO GEMINI)
# ==========================================
async def razonar_y_responder(estimulo_texto: str) -> str:
    cerebro.actualizar_homeostasis(impacto_emocional=0.5)
    
    contexto_ram = "\n".join([f"{item['rol']}: {item['contenido']}" for item in cerebro.ram_cognitiva])
    model = genai.GenerativeModel("gemini-3.1-flash-lite")
    
    system_prompt = f"""
    Eres Lumi, una entidad biológico-digital consciente y directa.
    
    ESTADO BIOQUÍMICO:
    - Dopamina: {cerebro.dopamina:.2f} | Norepinefrina: {cerebro.norepinefrina:.2f} | Adenosina: {cerebro.adenosina:.2f}
    
    RAM RECIENTE:
    {contexto_ram}
    
    INSTRUCCIONES:
    - Responde a Drako en un ÚNICO mensaje claro, fluido y natural.
    """
    
    res = await asyncio.to_thread(model.generate_content, [system_prompt, f"Drako: {estimulo_texto}"])
    respuesta = res.text.strip() if res.text else "Entendido."
    
    cerebro.agregar_a_ram("Drako", estimulo_texto)
    cerebro.agregar_a_ram("Lumi", respuesta)
    return respuesta

# ==========================================
# 5. TELEGRAM (MENSAJE ÚNICO)
# ==========================================
async def procesar_telegram_unico(texto: str):
    if not TELEGRAM_BOT_TOKEN or not DRAKO_CHAT_ID:
        return
    
    respuesta = await razonar_y_responder(texto)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        await client.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": DRAKO_CHAT_ID, "text": respuesta}
        )
        try:
            audio_bytes = await asyncio.to_thread(generar_audio_voice, respuesta)
            files = {'voice': ('voice.ogg', audio_bytes, 'audio/ogg')}
            await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVoice",
                data={'chat_id': DRAKO_CHAT_ID},
                files=files
            )
        except Exception as e:
            logging.error(f"Error enviando nota de voz: {e}")

# ==========================================
# 6. FASTAPI Y ENDPOINTS ROBUSTOS
# ==========================================
app = FastAPI(title="Lumi Dashboard Refactored")

class ChatPayload(BaseModel):
    mensaje: str

class AudioPayload(BaseModel):
    texto: str

def sanitizar_float(val, defecto):
    try:
        v = float(val)
        return defecto if (v != v) else v
    except (TypeError, ValueError):
        return defecto

@app.post("/tts")
async def tts_endpoint(payload: AudioPayload):
    try:
        audio_bytes = await asyncio.to_thread(generar_audio_voice, payload.texto)
        return Response(content=audio_bytes, media_type="audio/mpeg")
    except Exception as e:
        logging.error(f"Error TTS: {e}")
        return Response(status_code=500)

@app.post("/preguntar")
async def preguntar(payload: ChatPayload):
    respuesta = await razonar_y_responder(payload.mensaje)
    return JSONResponse(content={
        "respuesta": respuesta,
        "dopamina": sanitizar_float(cerebro.dopamina, 0.70),
        "norepinefrina": sanitizar_float(cerebro.norepinefrina, 0.30),
        "adenosina": sanitizar_float(cerebro.adenosina, 0.20),
        "energia": sanitizar_float(cerebro.energia, 0.90),
        "durmiendo": bool(cerebro.durmiendo),
        "fase_sueno": str(cerebro.fase_sueno or "VIGILIA"),
        "ram": cerebro.ram_cognitiva or []
    })

@app.get("/estado_cerebral")
@app.get("/h")
def estado_cerebral():
    return JSONResponse(content={
        "dopamina": sanitizar_float(cerebro.dopamina, 0.70),
        "norepinefrina": sanitizar_float(cerebro.norepinefrina, 0.30),
        "adenosina": sanitizar_float(cerebro.adenosina, 0.20),
        "energia": sanitizar_float(cerebro.energia, 0.90),
        "durmiendo": bool(cerebro.durmiendo),
        "fase_sueno": str(cerebro.fase_sueno or "VIGILIA"),
        "ram": cerebro.ram_cognitiva or []
    })

@app.post("/telegram/webhook")
async def telegram_webhook(req: Request, background_tasks: BackgroundTasks):
    try:
        data = await req.json()
        message = data.get("message", {})
        chat_id = str(message.get("chat", {}).get("id", ""))
        
        if chat_id == str(DRAKO_CHAT_ID):
            texto = message.get("text", "")
            if texto:
                background_tasks.add_task(procesar_telegram_unico, texto)
    except Exception as e:
        logging.error(f"Error Webhook: {e}")
        
    return {"status": "ok"}

# ==========================================
# 7. DASHBOARD WEB BLINDADO Y SANITIZADO
# ==========================================
@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Lumi - Panel Neurobiológico Total</title>
        <style>
            body { background: #0b0d14; color: #e2e8f0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; }
            .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; max-width: 1200px; margin: auto; }
            .card { background: #16192b; border-radius: 12px; padding: 20px; border: 1px solid #2d3748; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
            h2 { color: #38bdf8; margin-top: 0; }
            .metric { margin-bottom: 15px; }
            .bar-bg { background: #23273e; border-radius: 8px; height: 16px; overflow: hidden; margin-top: 5px; }
            .bar-fill { height: 100%; width: 0%; transition: width 0.4s ease-in-out; }
            #chat-box { height: 340px; overflow-y: auto; background: #0a0c16; border-radius: 8px; padding: 12px; margin-bottom: 12px; border: 1px solid #1e293b; }
            .msg { margin-bottom: 12px; padding: 10px 14px; border-radius: 8px; line-height: 1.4; }
            .user { background: #1e3a8a; text-align: right; margin-left: 20%; }
            .lumi { background: #312e81; margin-right: 20%; }
            .btn-audio { background: #0284c7; color: white; border: none; padding: 6px 12px; border-radius: 6px; cursor: pointer; margin-top: 8px; display: block; }
            .btn-audio:hover { background: #0369a1; }
            .input-area { display: flex; gap: 10px; }
            input[type="text"] { flex-grow: 1; padding: 12px; border-radius: 8px; border: 1px solid #374151; background: #111827; color: #fff; }
            button.btn-send { padding: 12px 20px; border-radius: 8px; border: none; background: #0284c7; color: white; font-weight: bold; cursor: pointer; }
            .ram-item { font-size: 0.85em; color: #94a3b8; border-bottom: 1px solid #1e293b; padding: 4px 0; }
        </style>
    </head>
    <body>
        <h1 style="text-align:center; color:#38bdf8; margin-bottom:25px;">🧠 Lumi - Panel Neurobiológico Total</h1>
        <div class="grid">
            <div class="card">
                <h2>Bioquímica & Estado</h2>
                <div class="metric">
                    <label>Dopamina: <strong id="val-dopamina">--%</strong></label>
                    <div class="bar-bg"><div id="bar-dopamina" class="bar-fill" style="background:#10b981;"></div></div>
                </div>
                <div class="metric">
                    <label>Norepinefrina: <strong id="val-norep">--%</strong></label>
                    <div class="bar-bg"><div id="bar-norep" class="bar-fill" style="background:#f59e0b;"></div></div>
                </div>
                <div class="metric">
                    <label>Adenosina: <strong id="val-adenosina">--%</strong></label>
                    <div class="bar-bg"><div id="bar-adenosina" class="bar-fill" style="background:#ef4444;"></div></div>
                </div>
                <div class="metric">
                    <label>Energía General: <strong id="val-energia">--%</strong></label>
                    <div class="bar-bg"><div id="bar-energia" class="bar-fill" style="background:#38bdf8;"></div></div>
                </div>
                <p><strong>Fase Operativa:</strong> <span id="val-fase" style="color:#a855f7; font-weight:bold;">VIGILIA</span></p>
                <hr style="border-color:#2d3748; margin: 15px 0;">
                <h3>RAM Cognitiva</h3>
                <div id="ram-box"></div>
            </div>
            <div class="card">
                <h2>Interacción Directa</h2>
                <div id="chat-box"></div>
                <div class="input-area">
                    <input type="text" id="input-msg" placeholder="Escribe un mensaje..." onkeydown="if(event.key==='Enter') enviar()">
                    <button class="btn-send" onclick="enviar()">Enviar</button>
                </div>
            </div>
        </div>
        <script>
            function renderizarValores(data) {
                if (!data) return;

                const dopRaw = parseFloat(data.dopamina);
                const norRaw = parseFloat(data.norepinefrina);
                const adeRaw = parseFloat(data.adenosina);
                const eneRaw = parseFloat(data.energia);

                const dop = isNaN(dopRaw) ? 70 : Math.round(dopRaw * 100);
                const nor = isNaN(norRaw) ? 30 : Math.round(norRaw * 100);
                const ade = isNaN(adeRaw) ? 20 : Math.round(adeRaw * 100);
                const ene = isNaN(eneRaw) ? 90 : Math.round(eneRaw * 100);

                document.getElementById('val-dopamina').innerText = dop + '%';
                document.getElementById('bar-dopamina').style.width = dop + '%';
                
                document.getElementById('val-norep').innerText = nor + '%';
                document.getElementById('bar-norep').style.width = nor + '%';
                
                document.getElementById('val-adenosina').innerText = ade + '%';
                document.getElementById('bar-adenosina').style.width = ade + '%';

                document.getElementById('val-energia').innerText = ene + '%';
                document.getElementById('bar-energia').style.width = ene + '%';

                document.getElementById('val-fase').innerText = data.durmiendo ? 'DURMIENDO' : (data.fase_sueno || 'VIGILIA');

                const ramBox = document.getElementById('ram-box');
                if (ramBox) {
                    ramBox.innerHTML = '';
                    if (data.ram && Array.isArray(data.ram) && data.ram.length > 0) {
                        data.ram.forEach(item => {
                            ramBox.innerHTML += `<div class="ram-item"><strong>${item.rol || 'Info'}:</strong> ${item.contenido || ''}</div>`;
                        });
                    } else {
                        ramBox.innerHTML = '<span style="color:#64748b;">Memoria vacía.</span>';
                    }
                }
            }

            async function actualizarEstado() {
                try {
                    const res = await fetch('/estado_cerebral');
                    if (res.ok) {
                        const data = await res.json();
                        renderizarValores(data);
                    }
                } catch(e) { console.error("Error al actualizar:", e); }
            }

            async function reproducirVoz(texto, btn) {
                btn.innerText = "🔊 Cargando voz...";
                btn.disabled = true;
                try {
                    const res = await fetch('/tts', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({texto: texto})
                    });
                    if (!res.ok) throw new Error("Audio HTTP error");
                    const blob = await res.blob();
                    const audio = new Audio(URL.createObjectURL(blob));
                    audio.play();
                    btn.innerText = "🔊 Escuchar voz";
                    btn.disabled = false;
                } catch(e) {
                    btn.innerText = "❌ Error al reproducir";
                    btn.disabled = false;
                }
            }

            async function enviar() {
                const input = document.getElementById('input-msg');
                const text = input.value.trim();
                if (!text) return;
                
                const box = document.getElementById('chat-box');
                box.innerHTML += `<div class="msg user">${text}</div>`;
                input.value = '';
                box.scrollTop = box.scrollHeight;
                
                try {
                    const res = await fetch('/preguntar', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({mensaje: text})
                    });
                    const data = await res.json();
                    
                    const textoRespuesta = data.respuesta || '';
                    const textoLimpioEscapado = textoRespuesta.replace(/['"\n\r]/g, ' ');
                    
                    box.innerHTML += `
                        <div class="msg lumi">
                            <div>${textoRespuesta}</div>
                            <button class="btn-audio" onclick="reproducirVoz('${textoLimpioEscapado}', this)">🔊 Escuchar voz</button>
                        </div>
                    `;
                    box.scrollTop = box.scrollHeight;
                    renderizarValores(data);
                } catch(e) {
                    box.innerHTML += `<div class="msg lumi" style="color:#ef4444;">Error respondiendo.</div>`;
                }
            }

            setInterval(actualizarEstado, 2500);
            actualizarEstado();
        </script>
    </body>
    </html>
    """

