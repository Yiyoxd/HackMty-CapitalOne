import os
import json
import argparse
import traceback
import time
from typing import Optional, Dict, Any, Union

# ================== RUTAS ABSOLUTAS ==================
BASE_DIR = r"C:\Users\Alfredo\Downloads\PapusPorMexico"
DEFAULT_PDFS_DIR = os.path.join(BASE_DIR, "Privado")
DEFAULT_OUT_FINAL = os.path.join(BASE_DIR, "resultado_final.json")
DEFAULT_OUT_INTER = os.path.join(BASE_DIR, "contrato_intermedio.json")

# ================== IMPORTS ==================
from api_analisis import analizar_costos_por_api            # string JSON in -> string JSON out
from api_parseo_pdfs import analizar_carpeta_obras          # folder -> string JSON


# ================== FUNCIONES AUXILIARES ==================
def _ensure_json_dict(maybe_json: Union[str, Dict[str, Any]], etiqueta: str) -> Dict[str, Any]:
    """Valida y convierte string/dict a JSON dict."""
    if isinstance(maybe_json, dict):
        return maybe_json
    if isinstance(maybe_json, str):
        try:
            return json.loads(maybe_json)
        except Exception as e:
            raise ValueError(f"❌ {etiqueta}: no es JSON válido. Detalle: {e}")
    raise TypeError(f"❌ {etiqueta}: tipo no soportado ({type(maybe_json)}).")


def _write_json(path: str, data: Dict[str, Any]) -> None:
    """Guarda el JSON en disco con formato bonito."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ================== FUNCIÓN PRINCIPAL ==================
def analizar_obras_completo(
    folder_path: str,
    ruta_salida: Optional[str] = None,
    ruta_intermedio: Optional[str] = None,
    validar_campos_final: bool = True,
) -> Dict[str, Any]:
    """Ejecuta el flujo completo de análisis y mide los tiempos."""
    if not os.path.isdir(folder_path):
        raise FileNotFoundError(f"❌ La carpeta no existe: {folder_path}")

    tiempos = {}
    t_inicio = time.perf_counter()
    print(f"\n📂 Carpeta: {folder_path}")

    try:
        # 1️⃣ EXTRACCIÓN DE CONTRATO
        print("\n🧩 Extrayendo contrato (analizar_carpeta_obras)...")
        t1 = time.perf_counter()
        contrato_json_str = analizar_carpeta_obras(folder_path)
        tiempos["extraccion"] = time.perf_counter() - t1

        contrato_json = _ensure_json_dict(contrato_json_str, "Contrato (intermedio)")
        print(f"✅ Contrato extraído y validado ({tiempos['extraccion']:.2f}s).")

        if ruta_intermedio:
            _write_json(ruta_intermedio, contrato_json)
            print(f"📝 JSON intermedio guardado en: {ruta_intermedio}")

        # 2️⃣ ANÁLISIS DE COSTOS
        print("\n📊 Analizando costos (analizar_costos_por_api)...")
        t2 = time.perf_counter()
        final_json_str = analizar_costos_por_api(contrato_json_str)
        tiempos["analisis_costos"] = time.perf_counter() - t2

        final_json = _ensure_json_dict(final_json_str, "Resultado final (análisis)")
        print(f"✅ Análisis de costos completado y validado ({tiempos['analisis_costos']:.2f}s).")

        if validar_campos_final:
            faltantes = [k for k in ("resumen_general", "partidas", "alertas", "recomendaciones") if k not in final_json]
            if faltantes:
                raise KeyError(f"❌ JSON final sin llaves requeridas: {faltantes}")

        if ruta_salida:
            _write_json(ruta_salida, final_json)
            print(f"💾 Resultado final guardado en: {ruta_salida}")

        tiempos["total"] = time.perf_counter() - t_inicio
        print(f"\n⏱️ TIEMPOS DEL PROCESO:")
        print(f"   🧩 Extracción:        {tiempos['extraccion']:.2f} segundos")
        print(f"   📊 Análisis costos:   {tiempos['analisis_costos']:.2f} segundos")
        print(f"   🕒 Total:             {tiempos['total']:.2f} segundos")

        return final_json

    except Exception as e:
        print("\n❌ ERROR DURANTE EL PROCESO:")
        print(f"   {type(e).__name__}: {e}")
        traceback.print_exc(limit=3)
        raise

    finally:
        if "total" not in tiempos:
            tiempos["total"] = time.perf_counter() - t_inicio
        print(f"\n🏁 Fin del proceso. (Duración total: {tiempos['total']:.2f}s)\n")


# ================== ARGPARSE ==================
def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Master que orquesta extractor de PDFs y analizador de costos.")
    p.add_argument(
        "carpeta",
        nargs="?",
        default=DEFAULT_PDFS_DIR,
        help=f"Ruta a la carpeta con PDFs de la obra (default: {DEFAULT_PDFS_DIR})."
    )
    p.add_argument(
        "--out", "-o",
        dest="ruta_salida",
        default=DEFAULT_OUT_FINAL,
        help=f"Ruta del archivo JSON final (default: {DEFAULT_OUT_FINAL})."
    )
    p.add_argument(
        "--dump-intermedio", "-i",
        dest="ruta_intermedio",
        default=DEFAULT_OUT_INTER,
        help=f"(Opcional) Ruta para guardar el JSON intermedio (default: {DEFAULT_OUT_INTER})."
    )
    p.add_argument(
        "--no-validate",
        action="store_true",
        help="Desactiva validación de llaves mínimas del JSON final."
    )
    return p


# ================== MAIN ==================
def main():
    args = _build_arg_parser().parse_args()

    print("============================================")
    print("🧠 INICIANDO PROCESO DE ANÁLISIS DE OBRAS 🧩")
    print("============================================")

    if args.carpeta == DEFAULT_PDFS_DIR:
        print(f"ℹ️ Usando carpeta por defecto: {DEFAULT_PDFS_DIR}")
    if args.ruta_salida == DEFAULT_OUT_FINAL:
        print(f"ℹ️ Guardando salida final en: {DEFAULT_OUT_FINAL}")
    if args.ruta_intermedio == DEFAULT_OUT_INTER:
        print(f"ℹ️ Guardando intermedio en: {DEFAULT_OUT_INTER}")

    try:
        resultado = analizar_obras_completo(
            folder_path=args.carpeta,
            ruta_salida=args.ruta_salida,
            ruta_intermedio=args.ruta_intermedio,
            validar_campos_final=(not args.no_validate),
        )

        rg = resultado.get("resumen_general", {})
        print("\n📌 RESUMEN GENERAL:")
        print(f"  - Costo en contrato:       {rg.get('costo_en_contrato')}")
        print(f"  - Precio estimado mercado: {rg.get('precio_estimado_mercado')}")
        print(f"  - Diferencia total:        {rg.get('diferencia_total')}")
        print(f"  - Diferencia %:            {rg.get('diferencia_porcentaje')}")
        print(f"  - Credibilidad:            {rg.get('credibilidad')}")
        print("\n✅ Proceso completado correctamente.")

    except Exception as e:
        print("\n💥 ERROR CRÍTICO:")
        print(f"   {type(e).__name__}: {e}")
        traceback.print_exc(limit=3)
        print("--------------------------------------------")
        print("💡 Revisa la ruta, permisos o la respuesta de la API.")

    finally:
        print("\n🏁 Fin del proceso.")


if __name__ == "__main__":
    main()
