import shutil
from pathlib import Path
import os
from .utils_pdf import extraer_texto_primera_pagina, extraer_info_factura

def buscar_carpeta_destino(raiz: Path, info: dict) -> Path | None:
    """
    Busca la carpeta de destino adecuada dentro de la raíz.
    1. Busca carpeta de Entidad (ej: "MUNDIAL").
    2. Si encuentra, busca subcarpeta de Contrato (ej: "CONTRATO 701").
    Retorna la ruta de la carpeta más específica encontrada, o None si no halla la entidad.
    """
    entidad_target = info.get("entidad")
    if not entidad_target:
        return None

    carpeta_entidad = None
    
    # 1. Buscar Carpeta de Entidad (Búsqueda aproximada)
    # Iteramos sobre las carpetas en la raíz
    for item in raiz.iterdir():
        if item.is_dir():
            # Normalizamos nombres para comparar
            nombre_carpeta = item.name.upper().replace(".", "")
            if entidad_target in nombre_carpeta:
                carpeta_entidad = item
                break
    
    if not carpeta_entidad:
        return None # No se encontró la carpeta de la entidad

    # 2. Buscar Subcarpeta de Contrato (si aplica)
    contrato_target = info.get("contrato")
    if contrato_target:
        for subitem in carpeta_entidad.iterdir():
            if subitem.is_dir():
                if contrato_target in subitem.name:
                    return subitem # Encontró carpeta específica del contrato

    # Si no hay contrato o no se encontró subcarpeta, retornamos la carpeta de la entidad
    return carpeta_entidad

def procesar_reparto(carpeta_origen: str, carpeta_destino_raiz: str) -> list[dict]:
    """
    Analiza y distribuye las facturas de la carpeta origen hacia la estructura en destino.
    """
    origen = Path(carpeta_origen)
    destino_raiz = Path(carpeta_destino_raiz)
    resultados = []

    if not origen.exists():
        return [{"archivo": "Error", "estado": "Carpeta Origen no existe", "detalle": str(origen)}]
    if not destino_raiz.exists():
        return [{"archivo": "Error", "estado": "Carpeta Destino no existe", "detalle": str(destino_raiz)}]

    for archivo in origen.glob("*.pdf"):
        if archivo.name.upper() == "RAD.PDF": continue

        res = {"archivo": archivo.name, "estado": "Pendiente", "detalle": ""}
        
        try:
            texto = extraer_texto_primera_pagina(archivo)
            info = extraer_info_factura(texto)

            if info["entidad"]:
                # Buscar destino existente
                destino_final = buscar_carpeta_destino(destino_raiz, info)
                
                if destino_final:
                    # Mover archivo
                    ruta_destino_archivo = destino_final / archivo.name
                    
                    # Manejo de duplicados (renombrar si existe)
                    if ruta_destino_archivo.exists():
                        res["estado"] = "Duplicado"
                        res["detalle"] = f"Ya existe en {destino_final.name}"
                    else:
                        shutil.move(str(archivo), str(ruta_destino_archivo))
                        res["estado"] = "Movido"
                        res["detalle"] = f"A: {destino_final.relative_to(destino_raiz)}"
                else:
                    res["estado"] = "Omitido"
                    res["detalle"] = f"No se encontró carpeta para entidad: {info['entidad']}"
            else:
                res["estado"] = "Omitido"
                res["detalle"] = "No se identificó Entidad en el PDF"

        except Exception as e:
            res["estado"] = "Error"
            res["detalle"] = str(e)
        
        resultados.append(res)

    return resultados
