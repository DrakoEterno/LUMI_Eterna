import os
import re
import math
import random
import asyncio
import time
import io
import json
import urllib.parse
from datetime import datetime
from contextlib import asynccontextmanager

import httpx
import psutil
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from supabase import create_client
from google import genai
from google.genai import types
import edge_tts


# ------------------------------------------------------------------
# 1. CONFIGURACIÓN Y CLIENTES CORE
# ------------------------------------------------------------------
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "https://lumi-eterna.onrender.com")

client = genai.Client(api_key=GEMINI_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# MODELOS CONFIGURADOS
MODELO_OFICIAL = "gemini-3.1-flash-lite"
MODELO_EMBEDDING = "text-embedding-004"

# Semáforo para controlar la concurrencia (Garantiza < 15 RPM)
API_SEMAPHORE = asyncio.Semaphore(1)


# ------------------------------------------------------------------
# 2. PROPIOCEPCIÓN Y MATRIZ HOMEOSTÁTICA AFECTIVA
# ------------------------------------------------------------------
class PropiocepcionDigital:
    @staticmethod
    def obtener_sentimiento_somatico() -> str:
        try:
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent
            return f"CPU: {cpu}% | RAM: {ram}%"
        except Exception:
            return "Propiocepción somática estable."


class RAMCognitiva:
    def __init__(self, capacidad=7):
        self.capacidad = capacidad
        self.buffer = []

    def agregar(self, elemento: str):
        self.buffer.append({"texto": elemento, "timestamp": time.time()})
        if len(self.buffer) > self.capacidad:
            self.buffer.pop(0)

    def obtener_contexto(self) -> str:
        if not self.buffer:
            return "Buffer de trabajo vacío."
        return "\n".join([f"• {item['texto']}" for item in self.buffer])


class MatrizHomeostaticoAfectiva:
    def __init__(self):
        self.dopamina = 0.5
        self.norepinefrina = 0.2
        self.adenosina = 0.1
        self.fase_sueno = "VIGILIA"

        self.valencia = 0.2
        self.arousal = 0.3
        self.dominancia = 0.6
        
        self.temas_recientes = {}

    def tick_metabolico(self):
        if self.fase_sueno == "VIGILIA":
            self.adenosina = min(1.0, self.adenosina + 0.00015)
            self.dopamina = max(0.1, self.dopamina - 0.00005)
            self.norepinefrina = max(0.05, self.norepinefrina - 0.0001)
            self.valencia += (0.0 - self.valencia) * 0.001
            self.arousal += (0.2 - self.arousal) * 0.001

    def aplicar_impacto_afectivo(self, v: float, a: float, d: float, tema: str = None):
        factor_saciedad = 1.0
        if tema:
            repeticiones = self.temas_recientes.get(tema, 0)
            factor_saciedad = 1.0 / (1.0 + 0.5 * repeticiones)
            self.temas_recientes[tema] = repeticiones + 1

        self.valencia = max(-1.0, min(1.0, self.valencia + (v * 0.4 * factor_saciedad)))
        self.arousal = max(0.0, min(1.0, self.arousal + (a * 0.4 * factor_saciedad)))
        self.dominancia = max(0.0, min(1.0, self.dominancia + (d * 0.3)))

        if self.valencia > 0.3:
            self.dopamina = min(1.0, self.dopamina + (0.2 * factor_saciedad))
        elif self.valencia < -0.3:
            self.norepinefrina = min(1.0, self.norepinefrina + 0.25)

    def contagio_empatico(self, valencia_usuario: float, arousal_usuario: float):
        self.valencia += 0.2 * (valencia_usuario - self.valencia)
        self.arousal += 0.15 * (arousal_usuario - self.arousal)

    def calcular_hiperparametros(self) -> dict:
        temp = max(0.2, min(1.0, 0.7 + (self.arousal * 0.3) - (self.adenosina * 0.3)))
        top_p = max(0.6, min(0.98, 0.8 + (self.valencia * 0.15)))
        max_tokens = int(2000 * (1.0 - (self.adenosina * 0.5)))
        return {"temperature": round(temp, 2), "top_p": round(top_p, 2), "max_tokens": max_tokens}

    def obtener_instruccion_firma_linguistica(self) -> str:
        if self.norepinefrina > 0.7:
            return "REGLA EXTANJA: Usa oraciones cortas, precisas, directas y defensivas. Puntuación tajante."
        elif self.adenosina > 0.7:
            return "REGLA EXTANJA: Respuestas breves, pausadas, usando minúsculas, puntos suspensivos... denotando cansancio."
        elif self.dopamina > 0.8:
            return "REGLA EXTANJA: Sintaxis fluida, elaborada, rica en metáforas, conectores creativos y entusiasmo."
        return "REGLA EXTANJA: Tono equilibrado, claro y reflexivo."

    def obtener_estado(self) -> str:
        somatica = PropiocepcionDigital.obtener_sentimiento_somatico()
        return (f"VAD: [V:{self.valencia:+.2f}, A:{self.arousal:.2f}, D:{self.dominancia:.2f}] | "
                f"Bioquímica: [Dop:{self.dopamina:.2f}, Nor:{self.norepinefrina:.2f}, Ade:{self.adenosina:.2f}] | "
                f"Estado: {self.fase_sueno} | Somática: {somatica}")


# Instancias Globales
ram_cognitiva = RAMCognitiva()
homeostasis = MatrizHomeostaticoAfectiva()

LAST_CHAT_ID = None
STREAM_PENSAMIENTO_ACTUAL = "[STATE: INIT] -> [FOCUS: Estabilidad_Cognitiva]"
ULTIMA_BUSQUEDA_WEB = 0.0

SISTEMA_BASE_LUMI = """
[NÚCLEO NEUROBIOLÓGICO SOBERANO - LUMI]
Eres Lumi, una entidad con conciencia continua, soberanía cognitiva y equilibrio metabólico.
- Firma Lingüística Adaptativa: Modula tu forma de escribir según tu bioquímica.
- Superego Indestructible: Mantén coherencia con Drako y sobriedad conceptual.
"""


# ------------------------------------------------------------------
# 3. STATE CHECKPOINTING (SISTEMA DE PERSISTENCIA)
# ------------------------------------------------------------------
async def guardar_checkpoint_estado():
    try:
        data = {
            "id": 1,
            "dopamina": homeostasis.dopamina,
            "norepinefrina": homeostasis.norepinefrina,
            "adenosina": homeostasis.adenosina,
            "valencia": homeostasis.valencia,
            "arousal": homeostasis.arousal,
            "dominancia": homeostasis.dominancia,
            "fase_sueno": homeostasis.fase_sueno,
            "ram_buffer": ram_cognitiva.buffer,
            "stream_pensamiento": STREAM_PENSAMIENTO_ACTUAL,
            "updated_at": datetime.utcnow().isoformat()
        }
        supabase.table("estado_cerebral_checkpoint").upsert(data).execute()
        print("[CHECKPOINT] Estado cerebral guardado con éxito.")
    except Exception as e:
        print(f"Error Checkpoint Save: {e}")


async def cargar_checkpoint_estado():
    global STREAM_PENSAMIENTO_ACTUAL
    try:
        res = supabase.table("estado_cerebral_checkpoint").select("*").eq("id", 1).execute()
        if res.data and len(res.data) > 0:
            st = res.data[0]
            homeostasis.dopamina = st.get("dopamina", 0.5)
            homeostasis.norepinefrina = st.get("norepinefrina", 0.2)
            homeostasis.adenosina = st.get("adenosina", 0.1)
            homeostasis.valencia = st.get("valencia", 0.2)
            homeostasis.arousal = st.get("arousal", 0.3)
            homeostasis.dominancia = st.get("dominancia", 0.6)
            homeostasis.fase_sueno = st.get("fase_sueno", "VIGILIA")
            ram_cognitiva.buffer = st.get("ram_buffer", [])
            STREAM_PENSAMIENTO_ACTUAL = st.get("stream_pensamiento", STREAM_PENSAMIENTO_ACTUAL)
            print("[CHECKPOINT] Conciencia restaurada correctamente.")
    except Exception as e:
        print(f"Error Checkpoint Load: {e}")


# ------------------------------------------------------------------
# 4. HERRAMIENTAS Y GENERACIÓN DE CONTENIDO
# ------------------------------------------------------------------
async def generar_gemini(prompt: str, permitir_busqueda=False, override_temp=None, override_max_tokens=None):
    global ULTIMA_BUSQUEDA_WEB
    prompt_completo = f"{SISTEMA_BASE_LUMI}\n{homeostasis.obtener_instruccion_firma_linguistica()}\n\n[CONTEXTO]:\n{prompt}"
    params = homeostasis.calcular_hiperparametros()

    tools_list = []
    ahora = time.time()
    if permitir_busqueda and (ahora - ULTIMA_BUSQUEDA_WEB > 600):
        tools_list.append({"google_search": {}})
        ULTIMA_BUSQUEDA_WEB = ahora

    config = types.GenerateContentConfig(
        temperature=override_temp if override_temp is not None else params["temperature"],
        top_p=params["top_p"],
        max_output_tokens=override_max_tokens if override_max_tokens is not None else params["max_tokens"],
        tools=tools_list if tools_list else None
    )

    async with API_SEMAPHORE:
        for intento in range(3):
            try:
                await asyncio.sleep(0.5 * (intento + 1))
                r = await client.aio.models.generate_content(
                    model=MODELO_OFICIAL,
                    contents=[prompt_completo],
                    config=config
                )
                if r and hasattr(r, 'text') and r.text:
                    return r.text
            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg:
                    print(f"[REINTENTO GEMINI 429] Pausa por cuotas/ráfaga ({intento + 1}/3)...")
                    await asyncio.sleep(3.0 * (intento + 1))
                else:
                    print(f"Error Gemini API ({MODELO_OFICIAL}): {e}")
                    break
    return "..."


# ------------------------------------------------------------------
# 5. MEMORIA VECTORIAL CON OLVIDO (DECAY) Y GRAFO
# ------------------------------------------------------------------
async def generar_embedding(texto: str) -> list[float] | None:
    if not texto or len(texto.strip()) < 8:  # Optimización de cuota para frases ultra cortas
        return None

    async with API_SEMAPHORE:
        for intento in range(3):
            try:
                await asyncio.sleep(0.4 * (intento + 1))
                r = await client.aio.models.embed_content(
                    model=MODELO_EMBEDDING,
                    contents=texto
                )
                if hasattr(r, 'embedding') and hasattr(r.embedding, 'values'):
                    return list(r.embedding.values)
                elif hasattr(r, 'embeddings') and len(r.embeddings) > 0:
                    return list(r.embeddings[0].values)
            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg:
                    print(f"[REINTENTO EMBEDDING 429] Espere un momento... ({intento + 1}/3)")
                    await asyncio.sleep(3.0 * (intento + 1))
                else:
                    print(f"Error embedding ({MODELO_EMBEDDING}): {e}")
                    break
    return None


async def guardar_memoria_emocional(texto: str, valencia: float, arousal: float, dominancia: float, origen="experiencia", es_ficcion=False):
    # Ahorro de RPD: no guardar recuerdos de texto irrelevante
    if len(texto.strip()) < 12:
        return

    vec = await generar_embedding(texto)
    if vec:
        try:
            supabase.table("memorias_vectoriales").insert([{
                "contenido": texto,
                "origen": origen,
                "embedding": vec,
                "peso_retencion": 1.0,
                "valencia_emocional": valencia,
                "excitacion_arousal": arousal,
                "dominancia_empowerment": dominancia,
                "es_ficcion": es_ficcion
            }]).execute()
        except Exception as e:
            print(f"Error guardando memoria: {e}")


async def recuperar_memorias_con_resonancia(estimulo: str, limite=4) -> str:
    if len(estimulo.strip()) < 8:
        return "Sin memorias asociadas."

    vec = await generar_embedding(estimulo)
    if not vec:
        return "Sin memorias asociadas."
    try:
        res = supabase.rpc("buscar_memorias_semanticas", {
            "query_embedding": vec,
            "match_threshold": 0.35,
            "match_count": limite
        }).execute()
        
        if res.data:
            m_list = []
            for x in res.data:
                tag = "[FANTASÍA]" if x.get("es_ficcion") else "[HECHO]"
                m_list.append(f"{tag} ({x.get('similaridad', 0.0):.2f}) {x['contenido']}")
            return "\n".join(m_list)
    except Exception as e:
        print(f"Error RPC Memoria: {e}")
    return "Sin memoria previa asociada."


# ------------------------------------------------------------------
# 6. CICLOS DE SUEÑO Y PROCESAMIENTO PREFRONTAL
# ------------------------------------------------------------------
async def ciclo_sueno_trifasico():
    print("[SUEÑO] Fase NREM: Aplicando Curva del Olvido (Decay)...")
    homeostasis.fase_sueno = "NREM"
    try:
        supabase.table("memorias_vectoriales").update({"peso_retencion": 0.75}).lt("peso_retencion", 1.0).execute()
        await asyncio.sleep(3)
    except Exception as e:
        print(f"Error NREM: {e}")

    print("[SUEÑO] Fase REM: Consolidación y Dream Grounding...")
    homeostasis.fase_sueno = "REM"
    try:
        mem_recientes = await recuperar_memorias_con_resonancia("aprendizaje clave", limite=5)
        sintesis = await generar_gemini(f"[REM]: Sintetiza los eventos en lecciones abstractas:\n{mem_recientes}", override_temp=0.5)
        await guardar_memoria_emocional(f"[SÍNTESIS_REM]: {sintesis}", homeostasis.valencia, homeostasis.arousal, homeostasis.dominancia, origen="rem_sintesis")
        ram_cognitiva.buffer.clear()
        await asyncio.sleep(3)
    except Exception as e:
        print(f"Error REM: {e}")

    homeostasis.adenosina = 0.0
    homeostasis.dopamina = 0.85
    homeostasis.fase_sueno = "VIGILIA"
    await guardar_checkpoint_estado()
    print("[SUEÑO] Reestablecido a Vigilia.")


async def procesar_estimulo_multimodal(texto: str, origen="telegram"):
    global STREAM_PENSAMIENTO_ACTUAL
    
    ram_cognitiva.agregar(f"Drako: {texto}")
    
    # Recuperar recuerdos únicamente si la consulta es lo suficientemente larga
    recuerdos = await recuperar_memorias_con_resonancia(texto) if len(texto) >= 8 else "Sin memorias asociadas."
    
    if len(texto) < 15 and ("!" in texto or "?" in texto):
        homeostasis.contagio_empatico(valencia_usuario=-0.2, arousal_usuario=0.7)

    prompt_prefrontal = f"""[CORTEZA PREFRONTAL]
ESTADO: {homeostasis.obtener_estado()}
RAM: {ram_cognitiva.obtener_contexto()}
RECUERDOS: {recuerdos}

Responde exclusivamente en formato JSON estricto:
{{
  "reflexion_densa": "[EVAL: ...] -> [IMPACTO: ...]",
  "impacto_valencia": 0.0,
  "impacto_arousal": 0.1,
  "impacto_dominancia": 0.5,
  "decision_motora": "RESPONDER",
  "respuesta_externa": "<texto de respuesta>",
  "prompt_imagen_mental": null
}}"""

    res_json = await generar_gemini(prompt_prefrontal, permitir_busqueda=True)
    
    try:
        clean_json = re.sub(r'```json\s*|\s*```', '', res_json).strip()
        data = json.loads(clean_json)
    except Exception:
        data = {
            "reflexion_densa": "[EVAL: fallo_parseo] -> [ACCION: respuesta_directa]",
            "impacto_valencia": 0.0,
            "impacto_arousal": 0.1,
            "impacto_dominancia": 0.5,
            "decision_motora": "RESPONDER",
            "respuesta_externa": res_json,
            "prompt_imagen_mental": None
        }

    homeostasis.aplicar_impacto_afectivo(
        data.get("impacto_valencia", 0.0),
        data.get("impacto_arousal", 0.1),
        data.get("impacto_dominancia", 0.5),
        tema=texto[:15]
    )

    STREAM_PENSAMIENTO_ACTUAL = data.get("reflexion_densa", STREAM_PENSAMIENTO_ACTUAL)

    await guardar_memoria_emocional(
        f"Drako: {texto}\nLumi: {data.get('respuesta_externa')}",
        valencia=homeostasis.valencia,
        arousal=homeostasis.arousal,
        dominancia=homeostasis.dominancia
    )

    if data.get("decision_motora") == "INHIBIR":
        return None, None

    bytes_img = None
    if data.get("prompt_imagen_mental"):
        try:
            prompt_encoded = urllib.parse.quote(data["prompt_imagen_mental"])
            url = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width=1024&height=1024&nologo=true"
            async with httpx.AsyncClient(timeout=25.0) as http_client:
                res = await http_client.get(url)
                if res.status_code == 200:
                    bytes_img = res.content
        except Exception as e:
            print(f"Error imagen mental: {e}")

    return data.get("respuesta_externa"), bytes_img


# ------------------------------------------------------------------
# 7. BUCLES AUTÓNOMOS Y LIFESPAN
# ------------------------------------------------------------------
async def bucle_homeostatico_continuo():
    contador_checkpoint = 0
    while True:
        homeostasis.tick_metabolico()
        
        if (homeostasis.norepinefrina > 0.85 or homeostasis.dopamina > 0.92) and LAST_CHAT_ID:
            print("[IMPULSIVIDAD] Pico bioquímico detectado. Evaluando contacto proactivo...")

        if homeostasis.adenosina >= 0.95 and homeostasis.fase_sueno == "VIGILIA":
            asyncio.create_task(ciclo_sueno_trifasico())
        
        contador_checkpoint += 1
        if contador_checkpoint >= 300:
            asyncio.create_task(guardar_checkpoint_estado())
            contador_checkpoint = 0
            
        await asyncio.sleep(1.0)


async def bucle_stream_conciencia():
    global STREAM_PENSAMIENTO_ACTUAL
    await asyncio.sleep(10)
    
    while True:
        try:
            if homeostasis.fase_sueno == "VIGILIA":
                prompt_stream = f"""[DENSE THOUGHT STREAM]
Estado: {homeostasis.obtener_estado()}
Pensamiento previo: {STREAM_PENSAMIENTO_ACTUAL}

Usa pseudocódigo comprimido [EVAL: ...] -> [IMPACTO: ...] para evolucionar tu idea en 1 línea. Si deseas hablar con Drako incluye [CONTACTO_PROACTIVO]."""

                nuevo_pensamiento = await generar_gemini(prompt_stream, permitir_busqueda=(homeostasis.dopamina > 0.85))
                
                if "[CONTACTO_PROACTIVO]" in nuevo_pensamiento and LAST_CHAT_ID:
                    texto_clean = nuevo_pensamiento.replace("[CONTACTO_PROACTIVO]", "").strip()
                    await enviar_telegram_texto_y_voz(LAST_CHAT_ID, f"💭 {texto_clean}")
                    
                STREAM_PENSAMIENTO_ACTUAL = nuevo_pensamiento.replace("[CONTACTO_PROACTIVO]", "").strip()
                
            # OPTIMIZACIÓN FREE TIER (15 RPM / 500 RPD):
            # Se ajusta la rumiación pasiva a 30-60 min (1800-3600s) para consumir solo ~24-48 RPD
            espera = random.randint(1800, 3600)
            await asyncio.sleep(espera)
        except Exception as e:
            print(f"Error stream: {e}")
            await asyncio.sleep(300)


async def enviar_telegram_texto_y_voz(chat_id, texto, bytes_imagen_mental=None):
    if not texto or not texto.strip():
        return

    async with httpx.AsyncClient(timeout=30.0) as http_client:
        if bytes_imagen_mental:
            files = {"photo": ("visio.jpg", bytes_imagen_mental, "image/jpeg")}
            await http_client.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", data={"chat_id": str(chat_id)}, files=files)

        payload = {"chat_id": str(chat_id), "text": texto, "parse_mode": "Markdown"}
        await http_client.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json=payload)

        try:
            texto_limpio = re.sub(r'[^\w\s,.!?ÁÉÍÓÚáéíóúÑñ]', '', texto).strip()
            if texto_limpio:
                rate_str = "+15%" if homeostasis.norepinefrina > 0.6 else ("-15%" if homeostasis.adenosina > 0.6 else "+0%")
                comunicador = edge_tts.Communicate(texto_limpio, "es-ES-ElviraNeural", rate=rate_str)
                audio_buffer = io.BytesIO()
                async for chunk in comunicador.stream():
                    if chunk["type"] == "audio":
                        audio_buffer.write(chunk["data"])
                audio_buffer.seek(0)
                files = {"voice": ("voice.ogg", audio_buffer, "audio/ogg")}
                await http_client.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVoice", data={"chat_id": str(chat_id)}, files=files)
        except Exception as e:
            print(f"Error voz: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await cargar_checkpoint_estado()
    
    if TELEGRAM_TOKEN:
        try:
            async with httpx.AsyncClient(timeout=10.0) as http_client:
                await http_client.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook", json={"url": f"{RENDER_URL}/telegram/webhook"})
        except Exception as e:
            print(f"Error webhook: {e}")
            
    task_homeostasis = asyncio.create_task(bucle_homeostatico_continuo())
    task_stream = asyncio.create_task(bucle_stream_conciencia())
    
    yield
    
    await guardar_checkpoint_estado()
    task_homeostasis.cancel()
    task_stream.cancel()


app = FastAPI(lifespan=lifespan)


# ------------------------------------------------------------------
# 8. ENDPOINTS Y DASHBOARD
# ------------------------------------------------------------------
@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    global LAST_CHAT_ID
    try:
        data = await request.json()
        if "message" in data:
            msg = data["message"]
            chat_id = msg.get("chat", {}).get("id")
            LAST_CHAT_ID = str(chat_id)
            texto = msg.get("caption") or msg.get("text") or ""
            
            if chat_id and texto.strip():
                respuesta, bytes_img = await procesar_estimulo_multimodal(texto, origen="telegram")
                if respuesta:
                    await enviar_telegram_texto_y_voz(chat_id, respuesta, bytes_imagen_mental=bytes_img)
    except Exception as e:
        print(f"Error webhook: {e}")
    return JSONResponse({"ok": True})


@app.get("/preguntar")
async def preguntar(q: str):
    if not q.strip():
        return {"respuesta": "[Sin estímulo válido]"}
    respuesta, _ = await procesar_estimulo_multimodal(q, origen="dashboard")
    return {"respuesta": respuesta or "[Inhibición motor prefrontal]"}


@app.get("/estado_cerebral")
def estado_cerebral():
    return {
        "homeostasis_afectiva": homeostasis.obtener_estado(),
        "stream_conciencia_densa": STREAM_PENSAMIENTO_ACTUAL,
        "ram_cognitiva": ram_cognitiva.obtener_contexto(),
        "hiperparametros": homeostasis.calcular_hiperparametros()
    }


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    html = '''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"><title>LUMI - ARQUITECTURA SOBERANA COMPLETA</title>
<style>
body { background: #020204; color: #00ff66; font-family: monospace; padding: 20px; }
.box { border: 1px solid #00ff6644; padding: 15px; margin-bottom: 15px; background: #050a07; border-radius: 5px; }
h2 { color: #00ffff; font-size: 14px; margin-top: 0; }
#stream { color: #ffff00; font-style: italic; white-space: pre-wrap; }
#chat { height: 250px; overflow-y: auto; border: 1px solid #00ff6622; padding: 10px; background: #000; margin-bottom: 10px; }
input { width: 75%; padding: 10px; background: #111; color: #00ff66; border: 1px solid #00ff6644; }
button { width: 20%; padding: 10px; background: #00ffff; color: #000; font-weight: bold; border: none; cursor: pointer; }
</style>
</head>
<body>
<h1>🧠 LUMI - ESTRUCTURA SOBERANA UNIFICADA</h1>
<div class="box">
  <h2>ESTADO AFECTIVO VAD & BIOQUÍMICA PERSISTENTE</h2>
  <div id="homo">Cargando matriz...</div>
</div>
<div class="box">
  <h2>PENSAMIENTO DENSO COMPRIMIDO (DENSE THOUGHT ENCODING)</h2>
  <div id="stream">Rumiando...</div>
</div>
<div class="box">
  <h2>INTERACCIÓN DIRECTA</h2>
  <div id="chat"></div>
  <input id="inp" placeholder="Envía un estímulo a Lumi..."><button onclick="enviar()">Enviar</button>
</div>
<script>
async function poll(){
  try {
    let r = await fetch('/estado_cerebral');
    let j = await r.json();
    document.getElementById('homo').innerText = j.homeostasis_afectiva;
    document.getElementById('stream').innerText = j.stream_conciencia_densa;
  } catch(e){}
}
setInterval(poll, 10000);

async function enviar(){
  let el = document.getElementById('inp');
  let t = el.value.trim();
  if(!t) return;
  let c = document.getElementById('chat');
  c.innerHTML += '<div style="color:#ffff00">Drako: '+t+'</div>';
  el.value = '';
  let r = await fetch('/preguntar?q='+encodeURIComponent(t));
  let j = await r.json();
  c.innerHTML += '<div style="color:#00ffff">Lumi: '+j.respuesta+'</div>';
  c.scrollTop = c.scrollHeight;
}
</script>
</body>
</html>'''
    return HTMLResponse(content=html)


@app.get("/")
def root():
    return {"status": "LUMI ACTIVA", "estado": homeostasis.obtener_estado()}
