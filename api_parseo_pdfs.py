import os
import json
from typing import List
from openai import OpenAI
from PyPDF2 import PdfReader

# ================== CONFIGURACIÓN ==================
# Antes de ejecutar:
#   setx OPENAI_API_KEY "tu_api_key"   ← Windows (ejecutar una vez en cmd)
#   export OPENAI_API_KEY="tu_api_key" ← Linux/Mac (solo sesión actual)

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise EnvironmentError("❌ Falta la variable de entorno OPENAI_API_KEY")

client = OpenAI(api_key=api_key)

CANDIDATES_DEFAULT = ["gpt-5", "gpt-4o", "gpt-4o-mini", "o3-mini", "o1"]

PROMPT_TEMPLATE = """
Analiza el siguiente texto y devuelve SOLO un JSON con este formato exacto:

{{
  "proyecto": {{
    "nombre": "",
    "lugar": "",
    "contrato_no": "",
    "contratista": "",
    "monto_total_contrato_MXN": 0.00,
    "fecha_inicio_programada": "",
    "fecha_termino_programada": "",
    "objetivo": "",
    "alcance_tecnico": [],
    "observaciones": []
  }},
  "partidas": [
    {{ "descripcion": "", "unidad": "", "cantidad": 0.00, "precio": "" }}
  ]
}}

Detalles para llenar:
- nombre, lugar, contrato_no, contratista, monto_total_contrato_MXN (Incluye IVA si aplica), fechas → del contrato
- objetivo → propósito principal de la obra
- alcance_tecnico → principales actividades o conceptos técnicos
- observaciones → notas relevantes del expediente (normas, control de calidad, condiciones, tipo de contrato, materiales)
No inventes nada; solo usa lo que esté realmente en los documentos.

Contenido:
{contenido}
""".strip()


def extract_text_from_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    parts = []
    for page in reader.pages:
        text = page.extract_text() or ""
        parts.append(text.strip())
    return "\n".join(parts)


def read_pdfs_from_folder(folder_path: str) -> str:
    if not os.path.isdir(folder_path):
        raise FileNotFoundError(f"No existe la carpeta: {folder_path}")
    chunks = []
    for name in sorted(os.listdir(folder_path)):
        if name.lower().endswith(".pdf"):
            ruta = os.path.join(folder_path, name)
            print(f"✅ Leyendo: {name}")
            chunks.append(f"\n\n### DOCUMENTO: {name}\n{extract_text_from_pdf(ruta)}")
    content = "".join(chunks).strip()
    if not content:
        raise RuntimeError("No se encontró ningún PDF en la carpeta.")
    return content


def first_available_model(client: OpenAI, candidates: List[str]) -> str:
    for m in candidates:
        try:
            params = {"model": m, "messages": [{"role": "user", "content": "ok"}]}
            try:
                client.chat.completions.create(**{**params, "max_completion_tokens": 1})
            except Exception:
                client.chat.completions.create(**{**params, "max_tokens": 1})
            print(f"🧠 Modelo seleccionado: {m}")
            return m
        except Exception:
            print(f"⏭️ No disponible: {m}")
            continue
    raise RuntimeError("No se encontró un modelo disponible.")


def analizar_carpeta_obras(folder_path: str, model_candidates: List[str] = None) -> str:
    contenido = read_pdfs_from_folder(folder_path)
    prompt = PROMPT_TEMPLATE.format(contenido=contenido)
    model_id = first_available_model(client, model_candidates or CANDIDATES_DEFAULT)

    response = client.chat.completions.create(
        model=model_id,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )

    json_text = response.choices[0].message.content
    json.loads(json_text)  # valida JSON
    return json_text


if __name__ == "__main__":
    ruta = r"Estados\Coahuila\Torreón\Pozo Las Brisas"
    try:
        resultado = analizar_carpeta_obras(ruta)
        print("\n✅ Resultado JSON:\n")
        print(resultado)
    except Exception as e:
        print(f"\n❌ Error: {e}")
