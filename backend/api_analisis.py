# api_analisis.py
import os
import json
import time
from typing import List
from openai import OpenAI

# ================== OPENAI ==================
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise EnvironmentError("❌ Falta la variable de entorno OPENAI_API_KEY")

client = OpenAI(api_key=api_key)
CANDIDATES_DEFAULT = ["gpt-4o", "gpt-4o-mini", "o3-mini"]

# Usa [[JSON_DATA]] como marcador para evitar .format y llaves conflictivas
PROMPT_BASE = """
Analiza el siguiente JSON y devuelve **solo** un nuevo JSON con el formato EXACTO mostrado abajo.
Es muy importante que en resumen_general la informacion esté COMPLETA, no lo dejes en 0
Los precios que calcules deben ser en MXN, reales o muy cercanos a la realidad, no disparates

=== FORMATO DE SALIDA ===
{
  "resumen_general": {
    "costo_en_contrato": 0,
    "precio_estimado_mercado": 0,
    "diferencia_total": 0,
    "diferencia_porcentaje": 0.0,
    "credibilidad": 0
  },
  "partidas": [
    {
      "concepto": "",
      "unidad": "",
      "cantidad": 0,
      "costo_en_contrato": 0,
      "precio_estimado_mercado": 0,
      "diferencia": 0,
      "diferencia_%": 0.0,
      "observaciones": ""
    }
  ],
  "alertas": [],
  "recomendaciones": []
}

=== INSTRUCCIONES CLARAS ===
- Usa TODA la información del JSON de entrada. No inventes ni elimines nada.
- Los precios, unidades y cantidades SIEMPRE vienen en el JSON de entrada, así que úsalos.
- Si el precio del contrato es 0, busca o estima el precio de mercado **según el concepto** y pon un valor real promedio en México.
- Calcula todo:
  - costo_en_contrato = suma de (costo_en_contrato * cantidad)
  - precio_estimado_mercado = suma de (precio_estimado_mercado * cantidad)
  - diferencia_total = mercado − contrato
  - diferencia_porcentaje = (diferencia_total / contrato) * 100 si contrato > 0, o 0 si no
  - credibilidad = 100 si los precios son similares, menor si hay diferencias grandes
- En observaciones: explica de dónde salió el dato
- En alertas: señala errores o vacíos o poca transparencia
- En recomendaciones: sugiere qué hacer
monto_total_contrato_MXN es costo_en_contrato

- Devuelve **solo el JSON**, bien formateado con 2 espacios y sin texto extra.

=== ENTRADA ===
[[JSON_DATA]]
""".strip()


def first_available_model(client: OpenAI, candidates: List[str]) -> str:
    start = time.perf_counter()
    selected = None
    for m in candidates:
        try:
            params = {"model": m, "messages": [{"role": "user", "content": "ok"}]}
            client.chat.completions.create(**{**params, "max_tokens": 1})
            selected = m
            break
        except Exception:
            continue
    elapsed_ms = (time.perf_counter() - start) * 1000
    if not selected:
        raise RuntimeError("No se encontró un modelo disponible.")
    print(f"🧠 Modelo seleccionado: {selected}  |  ⏱️ selección modelo: {elapsed_ms:.0f} ms")
    return selected


def analizar_costos_por_api(json_input: str, model_candidates: List[str] = None) -> str:
    # 1) Selección de modelo
    model_id = first_available_model(client, model_candidates or CANDIDATES_DEFAULT)

    # 2) Construcción de prompt (sin .format; usamos replace del marcador)
    t0 = time.perf_counter()
    prompt = PROMPT_BASE.replace("[[JSON_DATA]]", json_input)
    t1 = time.perf_counter()
    print(f"🧩 Construcción del prompt: {(t1 - t0) * 1000:.0f} ms")

    # 3) Llamada a la API
    t2 = time.perf_counter()
    response = client.chat.completions.create(
        model=model_id,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    t3 = time.perf_counter()
    print(f"🌐 Llamada al modelo: {(t3 - t2) * 1000:.0f} ms")

    # 4) Validación/parseo JSON
    t4 = time.perf_counter()
    json_text = response.choices[0].message.content
    data = json.loads(json_text)

    # Validaciones mínimas
    assert "resumen_general" in data and "partidas" in data and "alertas" in data and "recomendaciones" in data, \
        "El JSON no contiene las llaves requeridas"

    # === 🔧 AJUSTES LÓGICOS Y NUMÉRICOS ===
    def _round_num(x, nd):
        return round(x, nd) if isinstance(x, (int, float)) else x

    # Ajuste en resumen general
    rg = data.get("resumen_general", {})
    for k in ["costo_en_contrato", "precio_estimado_mercado", "diferencia_total"]:
        if k in rg and isinstance(rg[k], (int, float)):
            rg[k] = _round_num(rg[k], 2)
    if "diferencia_porcentaje" in rg and isinstance(rg["diferencia_porcentaje"], (int, float)):
        rg["diferencia_porcentaje"] = _round_num(rg["diferencia_porcentaje"], 4)

    # Ajuste detallado por partida
    for p in data.get("partidas", []):
        costo_contrato = p.get("costo_en_contrato", 0)
        costo_mercado = p.get("precio_estimado_mercado", 0)

        # Si el costo en contrato es 0, diferencia y porcentaje = 0
        if not costo_contrato or costo_contrato == 0:
            p["diferencia"] = 0
            p["diferencia_%"] = 0
        else:
            diff = costo_mercado - costo_contrato
            p["diferencia"] = _round_num(diff, 2)
            p["diferencia_%"] = _round_num((diff / costo_contrato) * 100, 4)

        # Redondeos de campos
        for campo in ["costo_en_contrato", "precio_estimado_mercado", "diferencia", "diferencia_%"]:
            if campo in p and isinstance(p[campo], (int, float)):
                p[campo] = _round_num(p[campo], 2 if campo != "diferencia_%" else 4)

    # === 🔧 REEMPLAZO FINAL JSON PRETTY ===
    json_text = json.dumps(data, ensure_ascii=False, indent=2)

    t5 = time.perf_counter()
    print(f"✅ Validación/parseo: {(t5 - t4) * 1000:.0f} ms")

    return json_text
