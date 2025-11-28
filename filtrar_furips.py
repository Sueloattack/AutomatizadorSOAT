import os
import glob
import pandas as pd
import re
import io
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox

# --- Funciones Auxiliares (Para interactuar con el usuario) ---

def inicializar_tk():
    """Crea una ventana raíz de Tkinter invisible para usar los diálogos."""
    root = tk.Tk()
    root.withdraw()
    return root

def seleccionar_carpeta(titulo="Seleccione una carpeta"):
    """Abre un diálogo para que el usuario seleccione una carpeta."""
    ruta = filedialog.askdirectory(title=titulo)
    if not ruta: print("Operación cancelada.")
    return ruta

def seleccionar_archivo(titulo="Seleccione un archivo", filetypes=[("Archivos de Texto", "*.txt")]):
    """Abre un diálogo para que el usuario seleccione un archivo."""
    ruta = filedialog.askopenfilename(title=titulo, filetypes=filetypes)
    if not ruta: print("Operación cancelada.")
    return ruta

def pedir_lista_glosas():
    """Pide al usuario que pegue una lista de glosas o seleccione un archivo .txt."""
    print("\n¿Cómo desea ingresar la lista de glosas?")
    print("1. Pegar la lista directamente en la terminal.")
    print("2. Seleccionar un archivo .txt.")
    choice = input("Seleccione una opción (1 o 2): ")
    glosas = []
    if choice == '1':
        print("\nPegue la lista de facturas/glosas y presione Enter dos veces:")
        contenido = []
        while True:
            linea = input()
            if not linea: break
            contenido.append(linea)
        texto_completo = " ".join(contenido)
        glosas = [g.strip() for g in re.split(r'[,\s\n]+', texto_completo) if g.strip()]
    elif choice == '2':
        ruta_archivo = filedialog.askopenfilename(title="Seleccione el archivo .txt con las glosas", filetypes=[("Text files", "*.txt")])
        if not ruta_archivo: return []
        try:
            with open(ruta_archivo, 'r', encoding='utf-8') as f: glosas = [line.strip() for line in f if line.strip()]
        except:
            with open(ruta_archivo, 'r', encoding='latin-1') as f: glosas = [line.strip() for line in f if line.strip()]
    else:
        print("Opción no válida.")
        return []
    if glosas: print(f"\nSe procesarán {len(glosas)} glosas.")
    return glosas

def pedir_numero_cuenta(titulo="Número de Cuenta de Cobro"):
    """Pide al usuario que ingrese el número para nombrar los archivos."""
    numero = simpledialog.askstring(titulo, "Por favor, ingrese el número de cuenta de cobro (ej: 618710):")
    if not numero: print("Operación cancelada.")
    return numero.strip() if numero else None

def leer_csv_con_fallback(filepath):
    """Intenta leer un archivo CSV (bien formado como RIPS) con diferentes codificaciones."""
    try:
        return pd.read_csv(filepath, sep=',', header=None, dtype=str, on_bad_lines='warn', encoding='utf-8-sig')
    except (UnicodeDecodeError, pd.errors.ParserError):
        try:
            return pd.read_csv(filepath, sep=',', header=None, dtype=str, encoding='latin-1', engine='python')
        except Exception as e:
            print(f"  - ¡ERROR! No se pudo leer '{os.path.basename(filepath)}'. Error: {e}")
            return None
    except Exception as e:
        print(f"  - ¡ERROR! No se pudo procesar '{os.path.basename(filepath)}'. Error: {e}")
        return None

def parsear_archivo_irregular(ruta_archivo, num_campos_esperados, tiene_comas_iniciales):
    """
    Lee un archivo de texto (FURIPS) línea por línea y lo parsea manualmente para
    manejar comas internas en los datos. Devuelve un DataFrame de Pandas.
    """
    print(f"  > Aplicando parseo manual a '{os.path.basename(ruta_archivo)}'...")
    texto_original = ""
    try:
        with open(ruta_archivo, 'r', encoding='utf-8-sig') as f: texto_original = f.read()
    except UnicodeDecodeError:
        with open(ruta_archivo, 'r', encoding='latin-1') as f: texto_original = f.read()

    # Normaliza saltos de línea (lógica diferente si tiene ,, al inicio)
    delimitador_registro = r'(,,COEX|,,FECR)' if tiene_comas_iniciales else r'(COEX|FECR)'
    texto_normalizado = re.sub(delimitador_registro, r'\n\1', texto_original).strip()

    lineas = texto_normalizado.split('\n')
    if not lineas: return None

    datos_parseados = []
    num_delimitadores = num_campos_esperados - 1

    for linea in lineas:
        if not linea.strip(): continue
        campos = linea.split(',', maxsplit=num_delimitadores)
        while len(campos) < num_campos_esperados:
            campos.append('')
        datos_parseados.append(campos)
    
    if not datos_parseados: return None
    return pd.DataFrame(datos_parseados)


# --- Funciones Principales ---

def unir_furips():
    print("\n--- INICIANDO UNIÓN DE FURIPS ---")
    carpeta_entrada = seleccionar_carpeta(titulo="Seleccione la carpeta con los FURIPS a unir")
    if not carpeta_entrada: return
    numero_cuenta = pedir_numero_cuenta()
    if not numero_cuenta: return
    carpeta_salida = seleccionar_carpeta(titulo="Seleccione la carpeta de SALIDA")
    if not carpeta_salida: return

    # Procesar FURIPS1
    df_f1_list = [df for f in glob.glob(os.path.join(carpeta_entrada, "FURIPS1*.txt")) if (df := parsear_archivo_irregular(f, 102, tiene_comas_iniciales=True)) is not None]
    if df_f1_list:
        df_f1_unido = pd.concat(df_f1_list, ignore_index=True)
        nombre_salida = f"FURIPS1_{numero_cuenta}.txt"
        df_f1_unido.to_csv(os.path.join(carpeta_salida, nombre_salida), sep=',', header=False, index=False, encoding='utf-8')
        print(f"- Archivo '{nombre_salida}' creado con {len(df_f1_unido)} registros.")

    # Procesar FURIPS2
    df_f2_list = [df for f in glob.glob(os.path.join(carpeta_entrada, "FURIPS2*.txt")) if (df := parsear_archivo_irregular(f, 9, tiene_comas_iniciales=False)) is not None]
    if df_f2_list:
        df_f2_unido = pd.concat(df_f2_list, ignore_index=True)
        nombre_salida = f"FURIPS2_{numero_cuenta}.txt"
        df_f2_unido.to_csv(os.path.join(carpeta_salida, nombre_salida), sep=',', header=False, index=False, encoding='utf-8')
        print(f"- Archivo '{nombre_salida}' creado.")
    messagebox.showinfo("Proceso Terminado", "La unión de archivos FURIPS ha finalizado.")

def filtrar_furips():
    print("\n--- INICIANDO FILTRADO DE UN ARCHIVO FURIP ---")
    glosas = pedir_lista_glosas()
    if not glosas: return
    archivo_entrada = seleccionar_archivo(titulo="Seleccione el archivo FURIP a filtrar")
    if not archivo_entrada: return
    print(f"  > Archivo de entrada: {archivo_entrada}")
    carpeta_salida = seleccionar_carpeta(titulo="Seleccione la CARPETA DE SALIDA")
    if not carpeta_salida: return
    print(f"  > Carpeta de salida: {carpeta_salida}")
    nombre_base = os.path.basename(archivo_entrada)
    print(f"\n--- Procesando '{nombre_base}'... ---")
    try:
        df_filtrado = None
        if "FURIPS1" in nombre_base:
            df = parsear_archivo_irregular(archivo_entrada, 102, tiene_comas_iniciales=True)
            if df is not None:
                df_filtrado = df[df.iloc[:, 2].isin(glosas)] # Filtrar por columna 2
        
        elif "FURIPS2" in nombre_base:
            df = parsear_archivo_irregular(archivo_entrada, 9, tiene_comas_iniciales=False)
            if df is not None:
                df_filtrado = df[df.iloc[:, 0].isin(glosas)] # Filtrar por columna 0
        
        else:
             print("ADVERTENCIA: No se pudo determinar el tipo. Se intentará leer como un RIPS estándar.")
             df = leer_csv_con_fallback(archivo_entrada)
             if df is not None: df_filtrado = df[df.iloc[:, 0].isin(glosas)]

        if df_filtrado is not None and not df_filtrado.empty:
            nombre_sin_ext, ext = os.path.splitext(nombre_base)
            nuevo_nombre = f"{nombre_sin_ext} - copia{ext}"
            ruta_salida = os.path.join(carpeta_salida, nuevo_nombre)
            df_filtrado.to_csv(ruta_salida, sep=',', header=False, index=False, encoding='utf-8')
            print(f"  > ¡ÉXITO! Se creó '{nuevo_nombre}' con {len(df_filtrado)} registros.")
            messagebox.showinfo("Proceso Terminado", f"Se ha creado el archivo filtrado:\n{nuevo_nombre}")
        else:
            print("  > INFO: No se encontraron registros de glosas.")
            messagebox.showinfo("Proceso Terminado", "No se encontraron registros.")
            
    except Exception as e:
        print(f"  > ¡ERROR! Ocurrió un problema: {e}")
        messagebox.showerror("Error", f"No se pudo procesar el archivo:\n{e}")

def unir_rips():
    print("\n--- INICIANDO PROCESO DE UNIR RIPS ---")
    print("\nPASO 1: Se abrirán DOS ventanas para seleccionar las carpetas de origen.")
    carpeta_1 = seleccionar_carpeta(titulo="Seleccione la carpeta de la SERIE 1 de RIPS")
    if not carpeta_1: return
    print(f"  > Carpeta Serie 1: {carpeta_1}")
    carpeta_2 = seleccionar_carpeta(titulo="Seleccione la carpeta de la SERIE 2 de RIPS")
    if not carpeta_2: return
    print(f"  > Carpeta Serie 2: {carpeta_2}")
    print("\nPASO 2: Ingrese el número de cuenta.")
    numero_cuenta = pedir_numero_cuenta()
    if not numero_cuenta: return
    print(f"  > Número de cuenta: {numero_cuenta}")
    print("\nPASO 3: Seleccione la carpeta de SALIDA.")
    carpeta_salida = seleccionar_carpeta(titulo="Seleccione la CARPETA DE SALIDA")
    if not carpeta_salida: return
    print(f"  > Carpeta de salida: {carpeta_salida}")
    print("\n--- Uniendo archivos... ---")
    tipos_rips = ['AF', 'AC', 'AD', 'AP', 'AM', 'AT', 'AH', 'AU', 'US', 'CT']
    for tipo in tipos_rips:
        archivos = glob.glob(os.path.join(carpeta_1, f"{tipo}*.txt")) + glob.glob(os.path.join(carpeta_2, f"{tipo}*.txt"))
        if not archivos: continue
        df_list = [df for f in archivos if (df := leer_csv_con_fallback(f)) is not None]
        if not df_list: continue
        df_unido = pd.concat(df_list, ignore_index=True)
        nombre_salida = f"{tipo}{numero_cuenta}.txt"
        df_unido.to_csv(os.path.join(carpeta_salida, nombre_salida), sep=',', header=False, index=False, encoding='utf-8')
        print(f"- Se generó '{nombre_salida}' con {len(df_unido)} registros.")
    messagebox.showinfo("Proceso Terminado", "La unión de archivos RIPS ha finalizado.")

def filtrar_rips():
    print("\n--- INICIANDO PROCESO DE FILTRAR RIPS ---")
    glosas = pedir_lista_glosas()
    if not glosas: return
    print("\nPASO 1: Seleccione la CARPETA con los RIPS a filtrar.")
    carpeta_entrada = seleccionar_carpeta(titulo="Seleccione la carpeta de ENTRADA de RIPS")
    if not carpeta_entrada: return
    print(f"  > Carpeta de entrada: {carpeta_entrada}")
    print("\nPASO 2: Seleccione la CARPETA para las copias filtradas.")
    carpeta_salida = seleccionar_carpeta(titulo="Seleccione la CARPETA DE SALIDA")
    if not carpeta_salida: return
    print(f"  > Carpeta de salida: {carpeta_salida}")
    print("\n--- Filtrando archivos... ---")
    tipos_rips = ['AF', 'AC', 'AD', 'AP', 'AM', 'AT', 'AH', 'AU', 'US'] 
    pacientes_filtrados = set()
    archivos_generados = 0
    archivos_a_procesar = glob.glob(os.path.join(carpeta_entrada, "*.txt"))
    for archivo_path in archivos_a_procesar:
        nombre_base = os.path.basename(archivo_path)
        tipo_actual = nombre_base[:2]
        if tipo_actual not in [t for t in tipos_rips if t != 'US']: continue
        print(f"\nProcesando '{nombre_base}'...")
        df = leer_csv_con_fallback(archivo_path)
        if df is None: continue
        df_filtrado = df[df.iloc[:, 0].isin(glosas)]
        if not df_filtrado.empty:
            if 3 < df.shape[1]: 
                pacientes_filtrados.update(df_filtrado.iloc[:, 2].fillna('') + df_filtrado.iloc[:, 3].fillna(''))
            nombre_sin_ext, ext = os.path.splitext(nombre_base)
            nuevo_nombre = f"{nombre_sin_ext} - copia{ext}"
            df_filtrado.to_csv(os.path.join(carpeta_salida, nuevo_nombre), sep=',', header=False, index=False, encoding='utf-8')
            print(f"  > ¡ÉXITO! Se creó '{nuevo_nombre}' con {len(df_filtrado)} registros.")
            archivos_generados += 1
        else:
            print(f"  > INFO: No se encontraron registros. Se omite.")
    archivos_us = [f for f in archivos_a_procesar if os.path.basename(f).startswith('US')]
    if archivos_us and pacientes_filtrados:
        for archivo_us_path in archivos_us:
            nombre_base_us = os.path.basename(archivo_us_path)
            print(f"\nProcesando '{nombre_base_us}'...")
            df_us = leer_csv_con_fallback(archivo_us_path)
            if df_us is None: continue
            id_completo_us = df_us.iloc[:, 0].fillna('') + df_us.iloc[:, 1].fillna('')
            df_us_filtrado = df_us[id_completo_us.isin(pacientes_filtrados)]
            if not df_us_filtrado.empty:
                nombre_sin_ext, ext = os.path.splitext(nombre_base_us)
                nuevo_nombre = f"{nombre_sin_ext} - copia{ext}"
                df_us_filtrado.to_csv(os.path.join(carpeta_salida, nuevo_nombre), sep=',', header=False, index=False, encoding='utf-8')
                print(f"  > ¡ÉXITO! Se creó '{nuevo_nombre}' con {len(df_us_filtrado)} usuarios.")
                archivos_generados += 1
            else: print("  > INFO: No se encontraron usuarios coincidentes. Se omite.")
    messagebox.showinfo("Proceso Terminado", f"El filtrado de RIPS ha finalizado. Se crearon {archivos_generados} archivos.")

# --- MENÚ PRINCIPAL ---
if __name__ == "__main__":
    root = inicializar_tk()
    while True:
        print("\n" + "="*50)
        print("    MENÚ PRINCIPAL DE HERRAMIENTAS PARA GLOSAS")
        print("="*50)
        print("\n--- RIPS ---\n  1. Unir RIPS (por tipo, desde dos carpetas)\n  2. Filtrar RIPS (por glosas, crea copias)")
        print("\n--- FURIPS ---\n  3. Unir FURIPS (por tipo)\n  4. Filtrar UN Archivo FURIP (individualmente)")
        print("\n--- SALIR ---\n  5. Salir")
        choice = input("\nPor favor, seleccione una opción: ")
        if choice == '1': unir_rips()
        elif choice == '2': filtrar_rips()
        elif choice == '3': unir_furips()
        elif choice == '4': filtrar_furips()
        elif choice == '5':
            print("\n¡Hasta luego!")
            break
        else: print("\nOpción no válida.")
    
    root.destroy()