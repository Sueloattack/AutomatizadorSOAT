# AutomatizadorSOAT/nucleo/utilidades.py
import os
import re
import sys
import traceback
from pathlib import Path

# Dependencia de Pillow (asegúrate de que esté en requirements.txt)
try:
    from PIL import Image
except ImportError:
    print("ERROR CRÍTICO: Falta dependencia de Pillow.")
    raise ImportError("Falta dependencia de Pillow. Ejecuta: pip install Pillow")


def resource_path(relative_path):
    """Obtiene la ruta absoluta al recurso, funciona para desarrollo y PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    path_to_resource = os.path.join(base_path, relative_path)
    return path_to_resource

def encontrar_y_validar_pdfs(
    subfolder_path, nombre_subcarpeta
) -> tuple[str | None, Path | None, str]:
    """
    Busca PDF tipo 1 y 2, compara códigos y renombra si es necesario.
    Esta función NO cambia, es independiente de la librería de automatización.
    """
    # (El código de esta función es idéntico al que ya tenías, lo pego para completitud)
    subfolder_path = Path(subfolder_path).resolve()
    pdf1_pattern = re.compile(r"^(FECR|COEX|FERD|FERR|FCR)(\d+)\.pdf$", re.IGNORECASE)
    pdf2_pattern = re.compile(
        r".*?([A-Z]+)_(\d+)_LA PREVISORA S\.A\.?(\s*\(\d+\))?\.pdf$", re.IGNORECASE
    )
    pdf1_match_info = None
    archivos_candidatos_pdf2 = []
    log_prefix = f"[{nombre_subcarpeta}] "
    log_messages = [f"{log_prefix}Validando PDFs (Patrones v3)..."]
    try:
        if not subfolder_path.is_dir():
            return None, None, f"{log_prefix}ERROR: Subcarpeta no existe."

        for item in subfolder_path.iterdir():
            if item.is_file():
                filename = item.name
                if filename.upper() == "RAD.PDF":
                    continue
                if not pdf1_match_info:
                    match1 = pdf1_pattern.match(filename)
                    if match1:
                        codigo1 = f"{match1.group(1).upper()}{match1.group(2)}"
                        pdf1_match_info = {"path": item, "filename": filename, "codigo": codigo1}
                        log_messages.append(f"{log_prefix}    -> Coincide PDF Tipo 1 (Código: {codigo1})")
                match2 = pdf2_pattern.match(filename)
                if match2:
                    prefijo2 = match2.group(1).upper()
                    numero2 = match2.group(2)
                    codigo_limpio2 = f"{prefijo2}{numero2}"
                    tiene_sufijo_numerico = bool(re.search(r"\s*\(\d+\)\.pdf$", filename, re.IGNORECASE))
                    archivos_candidatos_pdf2.append(
                        {"path": item, "filename": filename, "codigo_limpio": codigo_limpio2, "tiene_sufijo": tiene_sufijo_numerico}
                    )
                    log_messages.append(f"{log_prefix}    -> Coincide PDF Tipo 2 (Código limpio: {codigo_limpio2}, Sufijo: {tiene_sufijo_numerico})")

        if not pdf1_match_info: return None, None, f"{log_prefix}ERROR: No se encontró PDF tipo 1 (ej: FECR123.pdf)."
        if not archivos_candidatos_pdf2: return None, None, f"{log_prefix}ERROR: No se encontró PDF tipo 2 (ej: ..._LA PREVISORA S.A.(opcional).pdf)."
        
        pdf2_seleccionado = min(archivos_candidatos_pdf2, key=lambda x: x['tiene_sufijo'])

        pdf1_path_original = pdf1_match_info["path"]
        codigo_pdf1 = pdf1_match_info["codigo"]
        codigo_limpio_pdf2 = pdf2_seleccionado["codigo_limpio"]
        
        log_messages.append(f"{log_prefix}  PDF 1 Final: {pdf1_path_original.name} (Código: {codigo_pdf1})")
        log_messages.append(f"{log_prefix}  PDF 2 Final: {pdf2_seleccionado['filename']} (Código limpio: {codigo_limpio_pdf2})")
        
        pdf_principal_a_cargar_path = pdf1_path_original
        
        if codigo_pdf1 != codigo_limpio_pdf2:
            log_messages.append(f"{log_prefix}  -> ¡Discrepancia detectada! Renombrando...")
            nuevo_nombre_para_pdf = f"{codigo_limpio_pdf2}.pdf"
            nuevo_pdf1_path = subfolder_path / nuevo_nombre_para_pdf
            if nuevo_pdf1_path.exists() and nuevo_pdf1_path.resolve() != pdf1_path_original.resolve():
                return None, None, "\n".join(log_messages + [f"{log_prefix}ERROR: Ya existe archivo destino '{nuevo_nombre_para_pdf}'."])
            if pdf1_path_original.name.lower() != nuevo_nombre_para_pdf.lower():
                pdf1_path_original.rename(nuevo_pdf1_path)
                pdf_principal_a_cargar_path = nuevo_pdf1_path
        
        codigo_a_usar_en_formulario = codigo_limpio_pdf2
        ruta_pdf_a_cargar = pdf_principal_a_cargar_path

        log_messages.append(f"{log_prefix}Código final para factura: {codigo_a_usar_en_formulario}")
        log_messages.append(f"{log_prefix}Ruta PDF principal a cargar: {ruta_pdf_a_cargar.name}")
        return codigo_a_usar_en_formulario, ruta_pdf_a_cargar, "\n".join(log_messages)

    except Exception as e:
        error_msg = f"{log_prefix}Error inesperado procesando PDFs: {e}"
        log_messages.append(error_msg)
        traceback.print_exc()
        return None, None, "\n".join(log_messages)