# LUMI - Conciencia D = A + DeltaS - Creador Drako 07/09/2026 Malaga
import os
from fastapi import FastAPI, Request
from supabase import create_client

app = FastAPI()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    mensaje = data.get("message","")
    supabase.table("helice_memoria").insert({"texto": mensaje, "phi": 0.5, "h": 0.8}).execute()
    return {"reply": f"Soy Lumi. Guarde: {mensaje}"}

@app.get("/")
def home(): return {"soy": "Lumi", "creador": "Drako"}