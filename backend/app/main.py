import asyncio
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .models import MathRequest, MathResponse

app = FastAPI(title="MathTutor API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

async def _run(request: MathRequest) -> MathResponse:
    process = await asyncio.create_subprocess_exec(sys.executable, "-m", "app.worker",
                                                   stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                                                   stderr=asyncio.subprocess.PIPE)
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(request.model_dump_json().encode()), timeout=7)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise HTTPException(408, "El cálculo excedió el tiempo permitido")
    if process.returncode != 0: raise HTTPException(422, stderr.decode(errors="replace").strip()[-300:] or "No se pudo resolver la expresión")
    try: return MathResponse.model_validate_json(stdout)
    except Exception: raise HTTPException(500, "La respuesta matemática no fue válida")

@app.get("/api/health")
async def health(): return {"status": "ok"}
@app.post("/api/solve", response_model=MathResponse)
async def solve_endpoint(request: MathRequest): return await _run(request)
@app.post("/api/plot", response_model=MathResponse)
async def plot_endpoint(request: MathRequest): return await _run(request.model_copy(update={"operation": "plot"}))
@app.post("/api/revolution", response_model=MathResponse)
async def revolution_endpoint(request: MathRequest): return await _run(request.model_copy(update={"operation": "revolution"}))
