import zipfile
from pathlib import Path
import re

def procesar_union_json(carpeta_origen: str) -> list[dict]:
    """
    Busca archivos .json que compartan el mismo código de factura y los une en un .zip.
    Ejemplo: coex22228.json + resultadosmsps_coex22228_...json -> COEX22228.zip
    """
    origen = Path(carpeta_origen)
    resultados = []

    if not origen.exists():
        return [{"archivo": "Error", "estado": "Carpeta no existe", "detalle": str(origen)}]

    # Diccionario para agrupar archivos por código
    # Clave: Codigo (COEX29786), Valor: Lista de Paths
    grupos = {}
    
    # Regex para extraer el código principal (COEX + Digitos)
    # Busca patrones como "COEX12345" o "FECR12345" en cualquier parte del nombre
    patron_codigo = re.compile(r"(COEX|FECR|FERD|FERR|FCR)(\d+)", re.IGNORECASE)

    # 1. Agrupar archivos
    for archivo in origen.glob("*.json"):
        match = patron_codigo.search(archivo.name)
        if match:
            codigo = f"{match.group(1).upper()}{match.group(2)}"
            if codigo not in grupos:
                grupos[codigo] = []
            grupos[codigo].append(archivo)
        else:
            # Archivos JSON que no cumplen el patrón se ignoran o reportan
            pass

    # 2. Crear ZIPs
    for codigo, archivos in grupos.items():
        if not archivos: continue
        
        nombre_zip = f"{codigo}.zip"
        ruta_zip = origen / nombre_zip
        
        res = {"archivo": nombre_zip, "estado": "Pendiente", "detalle": ""}
        
        try:
            with zipfile.ZipFile(ruta_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                for json_file in archivos:
                    zf.write(json_file, arcname=json_file.name)
            
            res["estado"] = "Creado"
            res["detalle"] = f"Contiene {len(archivos)} archivos JSON"
            
        except Exception as e:
            res["estado"] = "Error"
            res["detalle"] = str(e)
        
        resultados.append(res)

    if not resultados:
        return [{"archivo": "N/A", "estado": "Sin cambios", "detalle": "No se encontraron grupos de JSONs para unir."}]

    return resultados
