from pathlib import Path
from .utils_pdf import extraer_texto_primera_pagina, extraer_info_factura
import re

def procesar_revision(carpeta_origen: str) -> list[dict]:
    """
    Valida que el nombre del archivo coincida con la factura interna.
    """
    origen = Path(carpeta_origen)
    resultados = []

    if not origen.exists():
        return [{"archivo": "Error", "estado": "Carpeta no existe", "detalle": str(origen)}]

    for archivo in origen.glob("*.pdf"):
        if archivo.name.upper() == "RAD.PDF": continue

        res = {"archivo": archivo.name, "estado": "Pendiente", "detalle": ""}
        
        try:
            texto = extraer_texto_primera_pagina(archivo)
            info = extraer_info_factura(texto)
            
            # Nombre archivo sin extensión y normalizado (sin espacios)
            nombre_archivo_limpio = archivo.stem.upper().replace(" ", "")
            
            # Código extraído
            codigo_interno = info.get("codigo_completo")
            
            if codigo_interno:
                codigo_interno_limpio = codigo_interno.upper().replace(" ", "")
                
                if nombre_archivo_limpio == codigo_interno_limpio:
                    res["estado"] = "Correcto"
                    res["detalle"] = f"Coincide: {codigo_interno}"
                else:
                    # Verificar si es una discrepancia parcial (ej: falta un digito)
                    res["estado"] = "Discrepancia"
                    res["detalle"] = f"Archivo: {archivo.stem} vs PDF: {codigo_interno}"
            else:
                res["estado"] = "No Detectado"
                res["detalle"] = "No se encontró número en PDF"

        except Exception as e:
            res["estado"] = "Error"
            res["detalle"] = str(e)
        
        resultados.append(res)

    return resultados
