import os
import shutil

def buscar_y_copiar_unico_nombre():
    print("--- COPIADOR FURIPS (FILTRO: UN SOLO NOMBRE) ---")
    
    # 1. Solicitar Rutas
    ruta_origen = input("Ingrese la ruta de ORIGEN: ").strip()
    if not os.path.exists(ruta_origen):
        print("Error: La ruta de origen no existe.")
        return

    ruta_destino = input("Ingrese la ruta de DESTINO: ").strip()
    
    # Crear carpeta destino si no existe
    if not os.path.exists(ruta_destino):
        try:
            os.makedirs(ruta_destino)
        except OSError as e:
            print(f"Error creando carpeta destino: {e}")
            return

    print("\nProcesando...\n")
    
    copiados = 0
    omitidos = 0

    # 2. Recorrer carpetas
    for raiz, directorios, archivos in os.walk(ruta_origen):
        for archivo in archivos:
            nombre_upper = archivo.upper()
            
            # Filtro de nombre
            if (nombre_upper.startswith("FURIPS1") or nombre_upper.startswith("FURIPS2")) and nombre_upper.endswith(".TXT"):
                
                ruta_origen_completa = os.path.join(raiz, archivo)
                ruta_destino_completa = os.path.join(ruta_destino, archivo)
                
                # 3. LÓGICA DE DUPLICADOS POR NOMBRE
                # Si el archivo YA existe en la carpeta de destino, no hacemos nada.
                if os.path.exists(ruta_destino_completa):
                    print(f"[OMITIDO] Ya existe un archivo llamado: {archivo}")
                    omitidos += 1
                else:
                    # Si NO existe, lo copiamos tal cual
                    try:
                        shutil.copy2(ruta_origen_completa, ruta_destino_completa)
                        print(f"[OK] Copiado: {archivo}")
                        copiados += 1
                    except Exception as e:
                        print(f"[ERROR] No se pudo copiar {archivo}: {e}")

    # Resumen
    print("\n" + "="*40)
    print(f"PROCESO FINALIZADO")
    print(f"Archivos copiados:  {copiados}")
    print(f"Archivos omitidos (por nombre repetido): {omitidos}")
    print(f"Ubicación de copias: {ruta_destino}")
    print("="*40)
    input("Presione Enter para salir...")

if __name__ == "__main__":
    buscar_y_copiar_unico_nombre()