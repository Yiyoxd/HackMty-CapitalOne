import os, json, time, traceback
from typing import Union, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ===== CONFIG =====
BASE_DIR = os.path.dirname(os.path.abspath("."))

# ===== IMPORTS REALES =====
from api_analisis import analizar_costos_por_api
from api_parseo_pdfs import analizar_carpeta_obras

app = FastAPI(title="Papus por México API", version="1.0")

# ===== CORS (para que el HTML pueda llamarlo) =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # si quieres, limita a ["http://127.0.0.1", "http://localhost:5500"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _ensure_json_dict(maybe_json: Union[str, Dict[str, Any]], etiqueta: str) -> Dict[str, Any]:
    if isinstance(maybe_json, dict):
        return maybe_json
    if isinstance(maybe_json, str):
        try:
            return json.loads(maybe_json)
        except Exception as e:
            raise ValueError(f"{etiqueta}: no es JSON válido: {e}")
    raise TypeError(f"{etiqueta}: tipo no soportado: {type(maybe_json)}")

def analizar_obras_completo(folder_path: str) -> Dict[str, Any]:
    if not os.path.isdir(folder_path):
        raise FileNotFoundError(f"No existe la carpeta: {folder_path}")

    t0 = time.perf_counter()
    try:
        # 1) extracción
        t1 = time.perf_counter()
        contrato_json_str = analizar_carpeta_obras(folder_path)
        extraccion = time.perf_counter() - t1
        contrato_json = _ensure_json_dict(contrato_json_str, "Contrato (intermedio)")

        # 2) análisis de costos
        t2 = time.perf_counter()
        final_json_str = analizar_costos_por_api(contrato_json_str)
        analisis = time.perf_counter() - t2
        final_json = _ensure_json_dict(final_json_str, "Resultado final (análisis)")

        final_json["_tiempos"] = {
            "extraccion": extraccion,
            "analisis_costos": analisis,
            "total": time.perf_counter() - t0
        }
        return final_json
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ===== ENDPOINTS =====
@app.get("/api/listar/{estado}/{ciudad}")
def listar_contenido(estado: str, ciudad: str):
    """
    Lista carpetas y archivos en: BASE_DIR/Estados/{estado}/{ciudad}
    """
    full_path = os.path.join(BASE_DIR, "Estados", estado, ciudad)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail=f"No existe: {full_path}")

    contenido = os.listdir(full_path)
    carpetas = [c for c in contenido if os.path.isdir(os.path.join(full_path, c))]
    archivos = [f for f in contenido if os.path.isfile(os.path.join(full_path, f))]

    return {
        "ruta": f"{estado}/{ciudad}",
        "ruta_completa": full_path,
        "carpetas": carpetas,
        "archivos": archivos,
        "total_items": len(contenido)
    }

@app.get("/api/analizar/{estado}/{ciudad}/{carpeta}")
def analizar_ruta(estado: str, ciudad: str, carpeta: str):
    """
    Ejecuta análisis en: BASE_DIR/Estados/{estado}/{ciudad}/{carpeta}
    """
    full_path = os.path.join(BASE_DIR, "Estados", estado, ciudad, carpeta)
    if not os.path.isdir(full_path):
        raise HTTPException(status_code=404, detail=f"No existe la carpeta: {full_path}")

    print(f"🚀 Analizando: {estado} / {ciudad} / {carpeta}")
    resultado = analizar_obras_completo(full_path)

    return JSONResponse(content={
        "ruta": f"{estado}/{ciudad}/{carpeta}",
        "estado": "ok",
        "resultado": resultado
    })

# === NUEVO (reemplazo correcto): subir 1–3 PDFs a Estados/temp/temp/temp ===
from typing import List
from fastapi import UploadFile, File, HTTPException
from pathlib import Path
import os, shutil

@app.post("/api/upload/temp")
async def upload_temp_files(files: List[UploadFile] = File(...)):
    """
    Recibe archivos via multipart/form-data (clave 'files') y los guarda en:
    BASE_DIR/Estados/temp/temp/temp
    De esta forma, tu endpoint de análisis /api/analizar/temp/temp/temp
    SÍ encuentra la carpeta.
    """
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No se recibió ningún archivo.")
        if len(files) > 3:
            raise HTTPException(status_code=400, detail="Máximo 3 archivos.")

        estados_dir = Path(os.path.join(BASE_DIR, "Estados"))
        dest_dir = estados_dir / "temp" / "temp" / "temp"   # <-- 3er 'temp' para que /analizar/... funcione
        dest_dir.mkdir(parents=True, exist_ok=True)

        saved = []
        for f in files:
            filename = (f.filename or "archivo.pdf").strip()
            ctype = (f.content_type or "").lower()
            if not filename.lower().endswith(".pdf") and "pdf" not in ctype:
                raise HTTPException(status_code=400, detail=f"Solo PDFs. Archivo: {filename}")

            target = dest_dir / filename
            base, ext = target.stem, (target.suffix or ".pdf")
            i = 1
            while target.exists():
                target = dest_dir / f"{base} ({i}){ext}"
                i += 1

            with target.open("wb") as out:
                shutil.copyfileobj(f.file, out)

            saved.append(target.name)

        return {
            "status": "ok",
            "ruta_relativa": "temp/temp/temp",   # coincide con /api/analizar/temp/temp/temp
            "saved": saved,
            "analizar_endpoint": "/api/analizar/temp/temp/temp"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al guardar: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_master:app", host="0.0.0.0", port=8000, reload=True)
