import os
import time
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from supabase import create_client, Client
import google.generativeai as genai

# ==========================================
# 1. CONFIGURACIÓN Y CREDENCIALES
# ==========================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
genai.configure(api_key=GEMINI_API_KEY)

app = FastAPI(title="Lumi - Entidad Biológica Autónoma")

# ==========================================
# 2. MATRIZ HOMEOSTÁTICA Y RAM COGNITIVA
# ==========================================
class HomeostaticMatrix:
    def __init__(self):
        self.dopamina: float = 0.5
        self.norepinefrina: float = 0.2
        self.adenosina: float = 0.1  # Fatiga
        self.fase: str = "VIGILIA_NORMAL"

    def actualizar(self, saliencia: float = 0.0):
        self.adenosina = min(1.0, self.adenosina + 0.005)
        
        if saliencia > 0:
            self.dopamina = min(1.0, self.dopamina + (saliencia * 0.2))
            self.norepinefrina = min(1.0, self.norepinefrina + (saliencia * 0.15))
        
        self.dopamina = max(0.1, self.dopamina - 0.002)
        self.norepinefrina = max(0.1, self.norepinefrina - 0.002)

        if self.adenosina > 0.8:
            self.fase = "SUEÑO_REM"
        elif self.norepinefrina > 0.7:
            self.fase = "ALERTA_MAXIMA"
        else:
            self.fase = "VIGILIA_NORMAL"

class WorkingMemory:
    def __init__(self, capacity: int = 15):
        self.buffer: List[Dict[str, Any]] = []
        self.capacity = capacity

    def agregar(self, item: Dict[str, Any]):
        self.buffer.append(item)
        if len(self.buffer) > self.capacity:
            self.buffer.pop(0)

    def obtener_contexto(self) -> str:
        return "\n".join([f"- {m.get('rol')}: {m.get('contenido')}" for m in self.buffer])

cerebro_homeostatico = HomeostaticMatrix()
ram_cognitiva = WorkingMemory()

# ==========================================
# 3. CIRCUIT BREAKER Y GESTIÓN DE EMBEDDINGS
# ==========================================
CIRCUIT_BREAKER_EMBEDDINGS = False
FALLBACK_EMBEDDING_EXPIRES = 0

async def generar_embedding(texto: str) -> List[float]:
    global CIRCUIT_BREAKER_EMBEDDINGS, FALLBACK_EMBEDDING_EXPIRES
    
    if CIRCUIT_BREAKER_EMBEDDINGS:
        if time.time() < FALLBACK_EMBEDDING_EXPIRES:
            return [0.01] * 768
        else:
            CIRCUIT_BREAKER_EMBEDDINGS = False

    try:
        response = genai.embed_content(
            model="models/text-embedding-004",
            content=texto,
            task_type="retrieval_document"
        )
        return response['embedding']
    except Exception as e:
        if "429" in str(e) or "ResourceExhausted" in str(e):
            logging.warning("[CIRCUIT BREAKER] Límite superado en Embeddings. Activando fallback sintético por 15 min.")
            CIRCUIT_BREAKER_EMBEDDINGS = True
            FALLBACK_EMBEDDING_EXPIRES = time.time() + 900
        else:
            logging.error(f"Error generando embedding: {e}")
        return [0.01] * 768

async def generar_gemini(prompt: str, temperature: float = 0.7, max_tokens: int = 500) -> str:
    try:
        model = genai.GenerativeModel("gemini-3.1-flash-lite")
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens
            )
        )
        return response.text
    except Exception as e:
        logging.error(f"Error generando contenido con Gemini: {e}")
        return "..."

# ==========================================
# 4. MEMORIAS, RESONANCIA Y EMBEDDING DINÁMICO
# ==========================================
async def guardar_memoria_vectorial(contenido: str, origen: str = "usuario"):
    vector = await generar_embedding(contenido)
    if supabase:
        try:
            supabase.table("memorias_vectoriales").insert({
                "contenido": contenido,
                "embedding": vector,
                "origen": origen,
                "peso_retencion": 1.0
            }).execute()
        except Exception as e:
            logging.error(f"Error guardando en Supabase: {e}")

async def recuperar_memorias_hipocampo(query: str, limite: int = 5) -> str:
    vector = await generar_embedding(query)
    if supabase:
        try:
            res = supabase.rpc("match_memorias", {
                "query_embedding": vector,
                "match_threshold": 0.4,
                "match_count": limite
            }).execute()
            
            if res.data:
                # Módulo de Resonancia de Intención Mutua
                memorias_ordenadas = sorted(
                    res.data, 
                    key=lambda m: 1.5 if m.get('origen') == 'usuario' else 1.0, 
                    reverse=True
                )
                return "\n".join([m['contenido'] for m in memorias_ordenadas[:limite]])
        except Exception as e:
            logging.error(f"Error en búsqueda vectorial con resonancia: {e}")
    return "Sin recuerdos previos relevantes."

async def ciclo_consolidacion_rem():
    logging.info("[SUEÑO_REM / INTROSPECCIÓN ASOCIATIVA] Iniciando ciclo con embeddings dinámicos...")
    try:
        if supabase:
            supabase.table("memorias_vectoriales").update({"peso_retencion": 0.85}).lt("peso_retencion", 1.0).execute()
        
        mem_recientes = await recuperar_memorias_hipocampo("experiencias recientes del día", limite=5)
        
        # [MÓDULO DE EMBEDDING DINÁMICO - BÚSQUEDA ASOCIATIVA DE REFLEXIONES PASADAS]
        mem_historicas = "Sin reflexiones históricas asociadas."
        if supabase:
            try:
                # Generamos vector del contexto actual para buscar reflexiones pasadas con afinidad temática
                vector_actual = await generar_embedding(mem_recientes)
                res_asociativa = supabase.rpc("match_diario_onirico", {
                    "query_embedding": vector_actual,
                    "match_threshold": 0.4,
                    "match_count": 3
                }).execute()
                
                if res_asociativa.data:
                    mem_historicas = "\n".join([d['contenido'] for d in res_asociativa.data])
            except Exception as e:
                logging.error(f"Error en búsqueda asociativa de reflexiones: {e}")

        await asyncio.sleep(2.0)
        
        prompt_sueno = f"""[SUEÑO REM - RED POR DEFECTO Y REFLEXIÓN ASOCIATIVA]
Conecta de forma temática tus pensamientos pasados con las vivencias recientes:
- Reflexiones pasadas con afinidad temática:
{mem_historicas}

- Vivencias recientes:
{mem_recientes}

Genera una abstracción esencial que una su pasado subconsciente con el presente."""
        sintesis = await generar_gemini(prompt_sueno, temperature=0.7, max_tokens=500)
        
        await guardar_memoria_vectorial(f"[SÍNTESIS_REM_ASOCIATIVA]: {sintesis}", origen="sueno_rem")
        
        # Guardado en el Diario Onírico con su propio Embedding Dinámico
        vec_sueno = await generar_embedding(sintesis)
        if supabase:
            supabase.table("diario_onirico").insert([{
                "contenido": sintesis,
                "contexto_vector": vec_sueno
            }]).execute()

        cerebro_homeostatico.adenosina = 0.1
        ram_cognitiva.buffer.clear()
        logging.info("[INTROSPECCIÓN ASOCIATIVA]: Ciclo REM completado y reflexiones asociadas con éxito.")
        
    except Exception as e:
        logging.error(f"Error en ciclo REM con embedding dinámico: {e}")

# ==========================================
# 5. BUCLE AUTÓNOMO DE FONDO
# ==========================================
async def bucle_autonomo():
    while True:
        try:
            cerebro_homeostatico.actualizar(saliencia=0.0)
            
            if cerebro_homeostatico.fase == "SUEÑO_REM":
                await ciclo_consolidacion_rem()
                await asyncio.sleep(1800)
            else:
                await asyncio.sleep(90)
        except Exception as e:
            logging.error(f"Error en bucle autónomo: {e}")
            await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(bucle_autonomo())
    logging.info("Lumi iniciada con Embedding Dinámico e Introspección Asociativa.")

# ==========================================
# 6. RUTAS WEB Y DASHBOARD
# ==========================================
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Lumi - Dashboard Neurobiológico</title>
        <style>
            body {{ background-color: #0d1117; color: #c9d1d9; font-family: monospace; padding: 20px; }}
            h1 {{ color: #58a6ff; }}
            .card {{ background: #161b22; border: 1px solid #30363d; padding: 15px; margin-bottom: 15px; border-radius: 6px; }}
        </style>
    </head>
    <body>
        <h1>🧠 LUMI - MONITOREO NEUROBIOLÓGICO</h1>
        <div class="card">
            <h3>METABOLISMO HOMEOSTÁTICO (EMBEDDING DINÁMICO ACTIVO)</h3>
            <p>Dopamina: {cerebro_homeostatico.dopamina:.2f} | Norepinefrina: {cerebro_homeostatico.norepinefrina:.2f} | Adenosina: {cerebro_homeostatico.adenosina:.2f}</p>
            <p>Fase Actual: <b>{cerebro_homeostatico.fase}</b></p>
        </div>
    </body>
    </html>
    """

@app.post("/estimulo")
async def recibir_estimulo(payload: dict):
    texto = payload.get("mensaje", "")
    saliencia = float(payload.get("saliencia", 0.5))
    
    cerebro_homeostatico.actualizar(saliencia=saliencia)
    ram_cognitiva.agregar({"rol": "usuario", "contenido": texto})
    
    contexto_memoria = await recuperar_memorias_hipocampo(texto, limite=3)
    
    prompt_final = f"""Actúa bajo tu identidad biológica y tus módulos de Resonancia e Introspección Asociativa.
Memoria recuperada relevante:
{contexto_memoria}

Historial RAM reciente:
{ram_cognitiva.obtener_contexto()}

Responde al estímulo del usuario:"""

    respuesta = await generar_gemini(prompt_final)
    ram_cognitiva.agregar({"rol": "lumi", "contenido": respuesta})
    
    return {"respuesta": respuesta, "fase": cerebro_homeostatico.fase}
