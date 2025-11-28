import os
import shutil

def buscar_y_copiar_furips():
    print("=" * 70)
    print("--- BUSCADOR Y COPIADOR DE ARCHIVOS FURIPS ---")
    print("=" * 70)
    
    # 1. Solicitar Ruta de Origen
    ruta_origen = input("\nIngrese la ruta (carpeta) donde debo BUSCAR los archivos: ").strip()
    if not os.path.exists(ruta_origen):
        print(f"Error: La ruta de origen '{ruta_origen}' no existe.")
        input("Presione Enter para salir...")
        return

    # 2. Solicitar Ruta de Destino
    ruta_destino = input("Ingrese la ruta (carpeta) donde debo GUARDAR las copias: ").strip()
    
    # Crear la carpeta de destino si no existe
    if not os.path.exists(ruta_destino):
        try:
            os.makedirs(ruta_destino)
            print(f"✓ Carpeta de destino creada: {ruta_destino}")
        except OSError as e:
            print(f"Error al crear la carpeta de destino: {e}")
            input("Presione Enter para salir...")
            return

    # 3. Solicitar listado de códigos de factura (uno por renglón)
    print("\n" + "=" * 70)
    print("INGRESE LOS CÓDIGOS DE FACTURA")
    print("=" * 70)
    print("Formato: serie + número (ej: FECR237823, FECR240254, etc.)")
    print("Ingrese un código por renglón.")
    print("Cuando termine, escriba 'FIN' y presione Enter.\n")
    
    codigos_factura = []
    while True:
        codigo = input("Código: ").strip()
        if codigo.upper() == 'FIN':
            break
        if codigo:
            # Extraer solo el número de la factura (últimos dígitos)
            # Ejemplo: FECR237823 -> 237823
            numero_factura = ''.join(filter(str.isdigit, codigo))
            if numero_factura:
                codigos_factura.append({
                    'completo': codigo.upper(),
                    'numero': numero_factura
                })
            else:
                print(f"  ⚠ Advertencia: '{codigo}' no contiene números, se omitirá.")
    
    if not codigos_factura:
        print("\nError: No se ingresaron códigos de factura válidos.")
        input("Presione Enter para salir...")
        return
    
    print(f"\n{'=' * 70}")
    print(f"INICIANDO BÚSQUEDA - {len(codigos_factura)} factura(s)")
    print("=" * 70)
    
    archivos_copiados_total = 0
    facturas_con_furips = {}  # {codigo_completo: {'carpeta': ruta, 'archivos': [archivos]}}
    facturas_sin_carpeta = []
    facturas_sin_furips = []
    archivos_ya_copiados = set()  # Conjunto para rastrear archivos ya copiados (evitar duplicados)
    facturas_compartidas = {}  # {ruta_archivo: [codigos que comparten ese archivo]}
    
    # 4. Buscar carpetas por cada código de factura
    for codigo_info in codigos_factura:
        codigo_completo = codigo_info['completo']
        numero_factura = codigo_info['numero']
        
        print(f"\n🔍 Buscando carpeta para factura: {codigo_completo} (número: {numero_factura})")
        
        carpeta_encontrada = None
        
        # Recorrer todas las carpetas en la ruta origen
        for raiz, directorios, archivos in os.walk(ruta_origen):
            for directorio in directorios:
                # Verificar si el nombre de la carpeta COMIENZA con el número de factura
                # Esto permite encontrar carpetas como "265447 NO" o "265447 adres"
                if directorio.startswith(numero_factura):
                    carpeta_encontrada = os.path.join(raiz, directorio)
                    print(f"  ✓ Carpeta encontrada: {carpeta_encontrada}")
                    break
            
            if carpeta_encontrada:
                break
        
        if not carpeta_encontrada:
            print(f"  ✗ No se encontró carpeta con el número: {numero_factura}")
            facturas_sin_carpeta.append(codigo_completo)
            continue
        
        # 5. Buscar todos los archivos Excel que contengan "furips" en la CARPETA PADRE
        # (al mismo nivel que la carpeta del número de factura)
        carpeta_padre = os.path.dirname(carpeta_encontrada)
        print(f"  📁 Buscando FURIPS en: {carpeta_padre}")
        
        archivos_furips = []
        
        try:
            for archivo in os.listdir(carpeta_padre):
                ruta_archivo = os.path.join(carpeta_padre, archivo)
                
                # Verificar que sea un archivo (no carpeta)
                if not os.path.isfile(ruta_archivo):
                    continue
                
                nombre_archivo_lower = archivo.lower()
                
                # Verificar si es un archivo Excel (.xlsx o .xls)
                if not (nombre_archivo_lower.endswith('.xlsx') or nombre_archivo_lower.endswith('.xls')):
                    continue
                
                # Verificar si contiene "furips"
                if 'furips' not in nombre_archivo_lower:
                    continue
                
                archivos_furips.append(archivo)
        except Exception as e:
            print(f"  ✗ Error al listar archivos en carpeta padre: {e}")
        
        if not archivos_furips:
            print(f"  ⚠ No se encontraron archivos FURIPS en la carpeta padre")
            facturas_sin_furips.append(codigo_completo)
            continue
        
        print(f"  ✓ Encontrados {len(archivos_furips)} archivo(s) FURIPS")
        
        # 6. Copiar todos los archivos FURIPS encontrados (solo si no se han copiado antes)
        archivos_copiados = []
        
        for archivo in archivos_furips:
            ruta_completa_origen = os.path.join(carpeta_padre, archivo)
            
            # Verificar si este archivo ya fue copiado
            if ruta_completa_origen in archivos_ya_copiados:
                print(f"    ⏭ Omitido (ya copiado): {archivo}")
                # Registrar que esta factura comparte el archivo
                if ruta_completa_origen not in facturas_compartidas:
                    facturas_compartidas[ruta_completa_origen] = []
                facturas_compartidas[ruta_completa_origen].append(codigo_completo)
                continue
            
            # Lógica para evitar sobrescribir (Renombrar si existe)
            nombre_base, extension = os.path.splitext(archivo)
            ruta_completa_destino = os.path.join(ruta_destino, archivo)
            
            contador = 1
            while os.path.exists(ruta_completa_destino):
                nuevo_nombre = f"{nombre_base}_{contador}{extension}"
                ruta_completa_destino = os.path.join(ruta_destino, nuevo_nombre)
                contador += 1
            
            try:
                # Copiar el archivo
                shutil.copy2(ruta_completa_origen, ruta_completa_destino)
                
                nombre_final = os.path.basename(ruta_completa_destino)
                print(f"    ✓ Copiado: {archivo} → {nombre_final}")
                
                archivos_copiados.append({
                    'original': archivo,
                    'destino': nombre_final,
                    'ruta_origen': ruta_completa_origen
                })
                
                # Marcar este archivo como ya copiado
                archivos_ya_copiados.add(ruta_completa_origen)
                
                # Registrar la primera factura que usa este archivo
                if ruta_completa_origen not in facturas_compartidas:
                    facturas_compartidas[ruta_completa_origen] = []
                facturas_compartidas[ruta_completa_origen].append(codigo_completo)
                
                archivos_copiados_total += 1
                
            except Exception as e:
                print(f"    ✗ ERROR al copiar {archivo}: {e}")
        
        if archivos_copiados:
            facturas_con_furips[codigo_completo] = {
                'carpeta_padre': carpeta_padre,
                'archivos': archivos_copiados
            }

    # Resumen final
    print("\n" + "=" * 70)
    print("RESUMEN DEL PROCESO")
    print("=" * 70)
    print(f"Total de facturas buscadas:      {len(codigos_factura)}")
    print(f"Facturas CON carpeta y FURIPS:   {len(facturas_con_furips)}")
    print(f"Facturas SIN carpeta:            {len(facturas_sin_carpeta)}")
    print(f"Facturas SIN archivos FURIPS:    {len(facturas_sin_furips)}")
    print(f"Total archivos únicos copiados:  {archivos_copiados_total}")
    
    if facturas_sin_carpeta:
        print("\n" + "-" * 70)
        print("⚠ FACTURAS SIN CARPETA ENCONTRADA:")
        print("-" * 70)
        for codigo in facturas_sin_carpeta:
            numero = ''.join(filter(str.isdigit, codigo))
            print(f"  • {codigo} (buscando carpeta que comience con: {numero})")
    
    if facturas_sin_furips:
        print("\n" + "-" * 70)
        print("⚠ FACTURAS CON CARPETA PERO SIN ARCHIVOS FURIPS:")
        print("-" * 70)
        for codigo in facturas_sin_furips:
            print(f"  • {codigo}")
    
    # Mostrar archivos compartidos por múltiples facturas
    archivos_compartidos = {ruta: codigos for ruta, codigos in facturas_compartidas.items() if len(codigos) > 1}
    if archivos_compartidos:
        print("\n" + "-" * 70)
        print("📋 ARCHIVOS FURIPS COMPARTIDOS POR MÚLTIPLES FACTURAS:")
        print("-" * 70)
        for ruta_archivo, codigos in archivos_compartidos.items():
            nombre_archivo = os.path.basename(ruta_archivo)
            print(f"\n  Archivo: {nombre_archivo}")
            print(f"  Ubicación: {os.path.dirname(ruta_archivo)}")
            print(f"  Compartido por {len(codigos)} factura(s):")
            for codigo in codigos:
                print(f"    • {codigo}")
    
    if facturas_con_furips:
        print("\n" + "-" * 70)
        print("✓ DETALLE DE ARCHIVOS COPIADOS:")
        print("-" * 70)
        for codigo, info in facturas_con_furips.items():
            print(f"\n  Factura: {codigo}")
            print(f"  Carpeta FURIPS: {info['carpeta_padre']}")
            print(f"  Archivos copiados:")
            for archivo in info['archivos']:
                print(f"    • {archivo['original']} → {archivo['destino']}")
                print(f"      Origen: {archivo['ruta_origen']}")
    
    print(f"\n{'=' * 70}")
    print(f"Ubicación de destino: {ruta_destino}")
    print("=" * 70)
    input("\nPresione Enter para salir...")

if __name__ == "__main__":
    buscar_y_copiar_furips()