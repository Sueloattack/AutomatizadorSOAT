# Automatizaciones/glosas/previsora.py
import time
import traceback
from pathlib import Path
import re
import os
import fitz

from Core.utilidades import encontrar_y_validar_pdfs, guardar_screenshot_de_error
from playwright.sync_api import Page, expect, TimeoutError as PlaywrightTimeoutError
try:
    from PIL import Image
except ImportError:
    raise ImportError("Falta Pillow. pip install Pillow")

try:
    from Configuracion.constantes import *
except ImportError as e:
    raise ImportError(f"ERROR CRITICO: No se pudieron importar constantes: {e}")

ESTADO_EXITO = "EXITO"
ESTADO_FALLO = "FALLO"
ESTADO_OMITIDO_RADICADO = "OMITIDO_RADICADO"
ESTADO_OMITIDO_DUPLICADA = "OMITIDO_DUPLICADA"

def manejar_popups_intrusivos(page: Page, logs: list) -> bool:
    """
    Intenta detectar y cerrar pop-ups genéricos o de error que bloquean la UI.
    Retorna True si cerró algo, False si no.
    """
    # Lista de selectores de botones de cierre/aceptar en popups conocidos
    # USAMOS TEXTO EXACTO O REGEX PARA EVITAR FALSOS POSITIVOS (ej. "Sí, continuar")
    selectores_cierre = [
        "button:has-text('Aceptar')",
        "button:has-text('Cerrar')",
        "button:has-text('Entendido')",
        # Selector estricto para "CONTINUAR" (evita "Sí, continuar")
        "button:text-is('CONTINUAR')", 
        PREVISORA_XPATH_POPUP_FACTURA_CONTINUAR, # El específico de "Factura ya existe"
        "div.ui-dialog-buttonset button" # Botones genéricos de diálogos jQuery UI
    ]
    
    accion_realizada = False
    for selector in selectores_cierre:
        try:
            # Verificación rápida (200ms) para no ralentizar el flujo normal
            if page.locator(selector).is_visible(timeout=200):
                page.locator(selector).click()
                logs.append(f"    [POPUP] Cerrado popup con selector: {selector}")
                accion_realizada = True
                # Pequeña espera para que la animación de cierre termine
                page.wait_for_timeout(500)
        except:
            pass
    return accion_realizada

def manejar_error_conectividad(page: Page, logs: list) -> bool:
    """
    Detecta si apareció la página de 'ERROR DE CONECTIVIDAD' y trata de recuperarse.
    Retorna True si se detectó y se intentó recuperar, False si no.
    """
    try:
        # Buscamos el botón 'Volver a Intentar' o el texto de error
        btn_volver = page.locator(PREVISORA_XPATH_BOTON_VOLVER_INTENTAR)
        if btn_volver.is_visible(timeout=1000):
            logs.append("    [ALERTA] Detectada página de 'ERROR DE CONECTIVIDAD'.")
            logs.append("    -> Intentando recuperar sesión con botón 'Volver a Intentar'...")
            btn_volver.click()
            
            # Esperar a que la página intente recargar y volver al formulario
            try:
                # Esperamos que aparezca el input de factura como señal de éxito
                expect(page.locator(f"#{PREVISORA_ID_FACTURA_FORM}")).to_be_visible(timeout=30000)
                logs.append("    -> Recuperación exitosa. Formulario visible nuevamente.")
                return True
            except:
                logs.append("    -> Falló la recuperación automática. Se intentará recarga completa en el siguiente ciclo.")
                return True # Retornamos True porque SÍ detectamos el error, aunque la recuperación fallara
    except:
        pass
    return False

def _verificar_pagina_activa(page: Page):
    """
    Verifica rápidamente si los elementos clave del formulario de radicación están presentes.
    Si no lo están, lanza una excepción para indicar que la página se ha caído o es incorrecta.
    """
    # Usamos un selector clave. Si el campo "Nº factura" no existe, asumimos que la página está mal.
    # `is_visible` con un timeout muy corto es extremadamente rápido.
    if not page.locator(f"#{PREVISORA_ID_FACTURA_FORM}").is_visible(timeout=1000):
        raise Exception("Página inválida. El elemento clave del formulario no fue encontrado. Posible caída del sitio.")

# --- Las funciones login_previsora y navegar_a_inicio_previsora NO CAMBIAN ---
def login(page: Page) -> tuple[bool, str]:
    """Realiza el login en Previsora usando Playwright."""
    logs = ["Iniciando login con Playwright..."]
    try:
        page.goto(PREVISORA_LOGIN_URL, timeout=60000)
        logs.append("  Página cargada.")
        page.locator(f"#{PREVISORA_ID_TIPO_RECLAMANTE_LOGIN}").select_option(label=PREVISORA_TIPO_RECLAMANTE_LOGIN)
        logs.append("  - Tipo Reclamante OK.")
        try:
            page.locator(PREVISORA_XPATH_POPUP_LOGIN_ENTENDIDO).click(timeout=5000)
            logs.append("  - Pop-up 'Entendido' inicial cerrado.")
        except PlaywrightTimeoutError:
            logs.append("  - Pop-up 'Entendido' no apareció, continuando.")
        page.locator(f"#{PREVISORA_ID_DOCUMENTO_LOGIN}").fill(PREVISORA_NO_DOCUMENTO_LOGIN)
        logs.append("  - Documento OK.")
        page.locator(PREVISORA_XPATH_BOTON_LOGIN).click()
        logs.append("  - Clic en 'Iniciar Sesión'.")
        expect(page.locator(PREVISORA_XPATH_INICIO_LINK)).to_be_visible(timeout=30000)
        logs.append("Login exitoso, página principal cargada.")
        return True, "\n".join(logs)
    except Exception as e:
        error_msg = f"ERROR inesperado durante el login: {e}"
        log_screenshot = guardar_screenshot_de_error(page, "previsora_glosas_login")
        logs.append(error_msg)
        logs.append(log_screenshot) # <-- Añadimos la ruta al log
        traceback.print_exc()
        return False, "\n".join(logs)

def navegar_a_inicio(page: Page) -> tuple[bool, str]:
    """Navega a la sección de 'Inicio' de la pagina."""
    logs = ["Navegando a la sección 'Inicio' (Recepción Reclamación)..."]
    try:
        page.locator(PREVISORA_XPATH_INICIO_LINK).click()
        elemento_clave_visible = page.locator(f"#{PREVISORA_ID_FACTURA_FORM}")
        expect(elemento_clave_visible).to_be_enabled(timeout=30000)
        logs.append("Navegación a 'Inicio' correcta. Formulario listo.")
        return True, "\n".join(logs)
    except Exception as e:
        error_msg = f"ERROR inesperado al navegar a 'Inicio': {e}"
        log_screenshot = guardar_screenshot_de_error(page, "previsora_glosas_inicio")
        logs.append(error_msg)
        logs.append(log_screenshot) # <-- Añadimos la ruta al log
        traceback.print_exc()
        return False, "\n".join(logs)

def llenar_formulario_previsora(page: Page, codigo_factura: str, context: str = 'default') -> tuple[str, str]:
    """Llena el formulario con los datos de la factura."""
    logs = [f"  Llenando formulario (Factura: {codigo_factura})..."]
    try:
        # 1. LIMPIEZA INICIAL: Cerrar cualquier popup residual de intentos anteriores
        manejar_popups_intrusivos(page, logs)
        
        # Si hay un popup de "Confirmación" (Sí, continuar) residual, lo cerramos con CANCELAR para no enviar nada
        btn_cancelar_residual = page.locator("button:has-text('cancel')")
        if btn_cancelar_residual.is_visible(timeout=500):
            btn_cancelar_residual.click()
            logs.append("    [LIMPIEZA] Cerrado popup residual de Confirmación (Cancel).")
            page.wait_for_timeout(500)

        dropdown_ciudad_container = page.locator(f"//input[@id='{PREVISORA_ID_CIUDAD_HIDDEN_FORM}']/..")
        opcion_ciudad = page.locator(PREVISORA_XPATH_CIUDAD_OPCION)
        factura_input = page.locator(f"#{PREVISORA_ID_FACTURA_FORM}")
        
        # Esperar a que el formulario sea interactuable
        expect(dropdown_ciudad_container).to_be_visible(timeout=20000)

        logs.append("    - Abriendo dropdown de Ciudad...")
        dropdown_ciudad_container.click()
        logs.append(f"    - Seleccionando '{PREVISORA_CIUDAD_FORM_NOMBRE}'...")
        # Esperar a que la opción aparezca
        expect(opcion_ciudad).to_be_visible(timeout=5000)
        opcion_ciudad.click()
        logs.append("    - Ciudad OK.")

        factura_input.fill(codigo_factura)
        # Disparar validación (Tab)
        page.keyboard.press("Tab")

        # --- VERIFICACIÓN DE DUPLICADOS (LÓGICA REFINADA) ---
        # Esperamos un momento (1s) para que el sitio procese y muestre el popup si es necesario.
        page.wait_for_timeout(1000)

        popup_duplicado = page.locator("div.jconfirm-content:has-text('ya ha sido ingresada')")
        try:
            if popup_duplicado.is_visible(timeout=1000):
                logs.append("    -> DETECTADO POPUP: Aviso de factura ingresada.")
                # Usamos el selector estricto
                btn_continuar = page.locator("button:text-is('CONTINUAR')")
                if btn_continuar.is_visible():
                    btn_continuar.click()
                    logs.append("    -> Popup cerrado con botón CONTINUAR.")
                
                # --- CRUCIAL: Verificar si el sistema borró el campo ---
                page.wait_for_timeout(500) # Esperar a que el JS del sitio actúe
                valor_actual = factura_input.input_value()
                if not valor_actual:
                    logs.append("    -> EL SISTEMA BORRÓ EL CAMPO FACTURA. Es un duplicado real.")
                    return ESTADO_OMITIDO_DUPLICADA, "\n".join(logs)
                else:
                    logs.append("    -> El campo factura persiste. Falsa alarma o advertencia no bloqueante. CONTINUANDO.")
        except:
            pass # Si no aparece, seguimos

        page.locator(f"#{PREVISORA_ID_CORREO_FORM}").fill(PREVISORA_CORREO_FORM)
        page.locator(f"#{PREVISORA_ID_USUARIO_REGISTRA_FORM}").fill(PREVISORA_USUARIO_REGISTRA_FORM)
        page.locator(f"#{PREVISORA_ID_RAMO_FORM}").select_option(label=PREVISORA_RAMO_FORM)
        logs.append("    - Campos principales llenados.")
        
        # Manejo de Popup "Factura ya existe" o similares (revisión final antes de seguir)
        page.wait_for_timeout(500) 
        
        # Re-verificación por si acaso saltó tarde
        if popup_duplicado.is_visible(timeout=1000):
            logs.append("    -> DETECTADO POPUP (Tardío): Aviso de factura ingresada.")
            btn_continuar = page.locator("button:text-is('CONTINUAR')")
            if btn_continuar.is_visible():
                btn_continuar.click()
            
            page.wait_for_timeout(500)
            if not factura_input.input_value():
                logs.append("    -> EL SISTEMA BORRÓ EL CAMPO FACTURA. Es un duplicado real.")
                return ESTADO_OMITIDO_DUPLICADA, "\n".join(logs)

        manejar_popups_intrusivos(page, logs)

        # Verificación final de campo vacío (por si acaso)
        if not factura_input.input_value():
            logs.append("    -> CAMPO FACTURA VACÍO. Posible duplicado o error de carga.")
            return ESTADO_OMITIDO_DUPLICADA, "\n".join(logs)

        page.locator(f"#{PREVISORA_ID_AMPAROS_FORM}").select_option(value=PREVISORA_VALUE_AMPARO_FORM)
        
        # Lógica condicional para el tipo de cuenta basado en el contexto
        if context == "aceptadas":
            tipo_cuenta_valor = "5"  # Valor para carpetas 'aceptadas'
            logs.append("    - Contexto 'aceptadas' detectado. Usando Tipo de Cuenta '5'.")
        else:
            tipo_cuenta_valor = PREVISORA_VALUE_TIPO_CUENTA_FORM  # Valor por defecto
            logs.append(f"    - Usando Tipo de Cuenta por defecto '{tipo_cuenta_valor}'.")

        page.locator(f"#{PREVISORA_ID_TIPO_CUENTA_FORM}").select_option(value=tipo_cuenta_valor)
        logs.append("    - Amparos y Tipo de Cuenta OK.")
        return ESTADO_EXITO, "\n".join(logs)
    except Exception as e:
        error_msg = f"ERROR inesperado al llenar formulario: {e}"
        # No tomamos screenshot aquí para no llenar la carpeta de errores en reintentos.
        logs.append(error_msg)
        traceback.print_exc()
        return ESTADO_FALLO, "\n".join(logs)

def subir_y_enviar_previsora(page: Page, pdf_path: Path) -> tuple[str, str]:
    """Carga el PDF y maneja el primer pop-up de confirmación."""
    logs = [f"  Subiendo archivo: {pdf_path.name}..."]
    try:
        page.locator(f"#{PREVISORA_ID_INPUT_FILE_FORM}").set_input_files(pdf_path)
        logs.append("    - Archivo adjuntado.")
        
        # Manejar cualquier popup que bloquee el botón de enviar
        manejar_popups_intrusivos(page, logs)

        page.locator(f"#{PREVISORA_ID_BOTON_ENVIAR_FORM}").click()
        logs.append("    - Clic en 'Enviar'.")

        # Clic en el primer pop-up sin esperar a que la página navegue
        page.locator(PREVISORA_XPATH_POPUP_ENVIO_SI_CONTINUAR).click(timeout=15000, no_wait_after=True)
        logs.append("    - Pop-up 'Sí, continuar' confirmado.")
        
        # EL PASO "CONTINUAR Y GUARDAR" SE HACE EN LA SIGUIENTE FUNCIÓN
        
        return ESTADO_EXITO, "\n".join(logs)
    except Exception as e:
        error_msg = f"ERROR inesperado al subir o enviar: {e}"
        # No tomamos screenshot aquí para no llenar la carpeta de errores en reintentos.
        logs.append(error_msg)
        traceback.print_exc()
        return ESTADO_FALLO, "\n".join(logs)

def guardar_confirmacion_previsora(page: Page, output_folder: Path) -> tuple[str | None, str | None, str]:
    """
    Maneja el guardado final de forma adaptativa, reconociendo si el sitio
    presenta el pop-up intermedio "Continuar y Guardar" o salta directamente
    al pop-up final de "Registro Generado".
    """
    logs = ["  Manejando fase de confirmación final (lógica adaptativa)..."]
    try:
        # 1. Esperar a que la página se estabilice (sin cambios)
        logs.append("    - Esperando a que la página se estabilice...")
        page.wait_for_load_state("load", timeout=30000)
        logs.append("    - Página estabilizada.")

        # --- LÓGICA ADAPTATIVA: BUSCAR QUÉ CAMINO TOMÓ LA WEB ---
        # Definimos los localizadores para ambos posibles pop-ups
        popup_intermedio_boton = page.locator(PREVISORA_XPATH_POPUP_CONTINUAR_GUARDAR)
        popup_final_confirmacion = page.locator(PREVISORA_XPATH_FINAL_CONFIRMATION_POPUP_CONTAINER)
        
        logs.append("    - Detectando siguiente paso del flujo (Intermedio o Final)...")
        
        # Esperamos un máximo de 3 minutos a que ALGUNO de los dos aparezca.
        # Esto lo logramos con un bucle de espera manual.
        popup_final = None # Definimos la variable fuera del bucle
        found_path = False
        for _ in range(180): # Intentar cada segundo por 3 minutos (180 segundos)
            # Primero, revisar si ya tenemos el resultado final.
            if popup_final_confirmacion.is_visible():
                logs.append("    -> DETECTADO: El pop-up final 'Registro Generado' apareció directamente.")
                popup_final = popup_final_confirmacion
                found_path = True
                break
            
            # Si no, revisar si tenemos el paso intermedio.
            if popup_intermedio_boton.is_visible():
                logs.append("    -> DETECTADO: El pop-up intermedio 'Continuar y Guardar' está visible.")
                popup_intermedio_boton.click(no_wait_after=True)
                logs.append("    -> Clic en 'Continuar y Guardar'. Ahora esperando el pop-up final...")
                # Ahora que hicimos clic, podemos esperar con `expect` de forma segura
                expect(popup_final_confirmacion).to_be_visible(timeout=180000)
                popup_final = popup_final_confirmacion
                found_path = True
                break
            
            page.wait_for_timeout(1000) # Esperar 1 segundo antes de volver a comprobar

        if not found_path or not popup_final:
            raise Exception("Timeout: No se detectó ni el pop-up intermedio ni el final después de 3 minutos.")
        
        # --- Si llegamos aquí, 'popup_final' tiene el elemento correcto ---
        
        # El resto del código para extraer y guardar la evidencia no cambia.
        texto_popup = popup_final.inner_text()
        radicado_match = re.search(r"Tu codigo es:\s*'(\d+)'", texto_popup, re.IGNORECASE)
        radicado_extraido = radicado_match.group(1) if radicado_match else "Extracción Fallida"
        logs.append(f"    - Código de radicado extraído: {radicado_extraido}")
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        temp_png_path = output_folder / f"temp_confirmacion_{timestamp}.png"
        rad_pdf_path = output_folder / "RAD.pdf"
        
        popup_final.screenshot(path=temp_png_path)
        with Image.open(temp_png_path) as img: img.convert("RGB").save(rad_pdf_path)
        temp_png_path.unlink()
        logs.append(f"    - Confirmación guardada como {rad_pdf_path.name}")
        
        page.locator(PREVISORA_XPATH_BOTON_NUEVA_RECLAMACION).click()
        expect(page.locator(f"#{PREVISORA_ID_FACTURA_FORM}")).to_be_enabled(timeout=20000)
        logs.append("    - Clic en 'Nueva Reclamación'. Pantalla limpia.")
        
        return str(rad_pdf_path), radicado_extraido, "\n".join(logs)

    except Exception as e:
        error_msg = f"ERROR inesperado en la confirmación final: {e}"
        log_screenshot = guardar_screenshot_de_error(page, f"error_screenshot_confirmacion_{output_folder.name}_{time.strftime('%H%M%S')}.png")
        logs.append(error_msg)
        logs.append(log_screenshot) 
        traceback.print_exc()
        return None, None, "\n".join(logs)

def procesar_carpeta(page: Page, subfolder_path: Path, subfolder_name: str, context: str = 'default') -> tuple[str, str | None, str | None, str]:
    """
    Orquestador para Previsora con una estrategia de reintento proactiva:
    si un intento falla, recarga la página antes de volver a intentarlo.
    """
    logs = [f"--- Iniciando Playwright/Previsora para: '{subfolder_name}' ---"]
    
    # Verificaciones previas de nombre y RAD.pdf
    if any(p in subfolder_name.upper() for p in PALABRAS_EXCLUSION_CARPETAS) or (subfolder_path / "RAD.pdf").is_file():
        return ESTADO_OMITIDO_RADICADO, None, None, f"OMITIENDO: Carpeta excluida por nombre o ya radicada."

    # 1. Encontrar los archivos
    codigo_factura, pdf_path, pdf_log = encontrar_y_validar_pdfs(subfolder_path, subfolder_name, PREVISORA_NOMBRE_EN_PDF)
    logs.append(pdf_log)
    if not (codigo_factura and pdf_path):
        return ESTADO_FALLO, None, None, "\n".join(logs)
        
    # 2. Verificar y comprimir el archivo si es necesario
    try:
        file_size = pdf_path.stat().st_size
        logs.append(f"[INFO] Tamaño inicial del archivo '{pdf_path.name}': {file_size / (1024*1024):.2f} MB")

        if file_size > PREVISORA_MAX_FILE_SIZE_BYTES:
            logs.append(f"ADVERTENCIA: El archivo supera los {PREVISORA_MAX_FILE_SIZE_BYTES / (1024*1024):.0f} MB.")
            
            original_pdf_path = pdf_path.with_name(f"{pdf_path.stem}-original.pdf")
            
            # Si el backup ya existe, significa que ya intentamos comprimir este archivo y fallamos.
            if original_pdf_path.exists():
                error_msg = (
                    f"ERROR: Se detectó un intento de compresión anterior ('{original_pdf_path.name}' existe). "
                    f"El archivo sigue siendo demasiado grande. Esta carpeta será omitida para evitar bucles."
                )
                logs.append(error_msg)
                return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)

            # Si no hay backup, es el primer intento. Procedemos a comprimir.
            logs.append("Intentando comprimir por primera vez...")
            pdf_path.rename(original_pdf_path) # Renombrar para crear el backup
            logs.append(f"  - Original renombrado a: {original_pdf_path.name}")

            try:
                # Comprimir el PDF
                with fitz.open(original_pdf_path) as doc:
                    doc.save(str(pdf_path), garbage=4, deflate=True, clean=True)
                
                new_size = pdf_path.stat().st_size
                logs.append(f"  - Compresión completa. Nuevo tamaño: {new_size / (1024*1024):.2f} MB")

                # Verificar si la compresión fue suficiente
                if new_size > PREVISORA_MAX_FILE_SIZE_BYTES:
                    error_msg = (
                        f"ERROR: El archivo sigue siendo demasiado grande después de la compresión "
                        f"({new_size / (1024*1024):.2f} MB > {PREVISORA_MAX_FILE_SIZE_BYTES / (1024*1024):.0f} MB). "
                        f"Esta carpeta será omitida."
                    )
                    logs.append(error_msg)
                    # No restauramos el nombre, dejamos el -original.pdf como evidencia del fallo.
                    return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)
                
                # Si la compresión fue exitosa, el proceso continúa con el nuevo pdf_path
                logs.append("  - El archivo ahora está dentro del límite de tamaño.")

            except Exception as e:
                logs.append(f"ERROR CRÍTICO durante la compresión del PDF: {e}")
                # Si la compresión falla, restauramos el nombre original para poder intentarlo de nuevo en otra ejecución.
                if original_pdf_path.exists():
                    original_pdf_path.rename(pdf_path)
                    logs.append(f"  - Se restauró el nombre del archivo original: {pdf_path.name}")
                return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)

    except FileNotFoundError:
        logs.append(f"ERROR: No se pudo encontrar el archivo {pdf_path} para verificar su tamaño.")
        return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)    
    
    MAX_ATTEMPTS = 5 # Aumentamos a 5 para más robustez (solicitud usuario)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            logs.append(f"\n--- Intento de radicación #{attempt}/{MAX_ATTEMPTS} ---")
            
            # --- VIGÍA DE ERROR DE CONECTIVIDAD ---
            # Antes de cualquier cosa, verificamos si estamos en la pantalla de error
            manejar_error_conectividad(page, logs)

            # --- LÓGICA DE RECARGA PROACTIVA ---
            # A partir del SEGUNDO intento, siempre recargamos la página primero.
            if attempt > 1:
                logs.append("   -> Fallo en intento anterior. Recargando la página para empezar de nuevo...")
                page.reload(wait_until="domcontentloaded", timeout=45000)
                # Opcional: una pequeña espera tras la recarga puede ayudar a estabilizar
                page.wait_for_timeout(3000) 
                # Volvemos a chequear error de conectividad tras recarga
                manejar_error_conectividad(page, logs)
            
            # VERIFICACIÓN DEL VIGÍA #1: ¿La página está bien ANTES de empezar a llenar?
            try:
                _verificar_pagina_activa(page)
            except Exception as e_active:
                logs.append(f"   -> Página no activa/válida: {e_active}")
                # Si falla la verificación, intentamos ver si es por el error de conectividad
                if manejar_error_conectividad(page, logs):
                    logs.append("   -> Se recuperó del error de conectividad. Reintentando verificación...")
                    _verificar_pagina_activa(page) # Reintentamos verificación
                else:
                    raise # Si no era eso, forzamos reintento normal
            
            # --- PASO 1: Llenado de Formulario ---
            logs.append("\n--- PASO 1: Llenado de Formulario ---")
            estado_llenado, log_llenado = llenar_formulario_previsora(page, codigo_factura, context)
            logs.append(log_llenado)
            if estado_llenado == ESTADO_OMITIDO_DUPLICADA: 
                return ESTADO_OMITIDO_DUPLICADA, None, codigo_factura, "\n".join(logs)
            if estado_llenado != ESTADO_EXITO: 
                raise Exception("El llenado de formulario falló.") # Provoca el 'except' para el reintento

            # --- PASO 2: Subida de Archivos ---
            logs.append("\n--- PASO 2: Subida de Archivos ---")
            estado_subida, log_subida = subir_y_enviar_previsora(page, pdf_path)
            logs.append(log_subida)
            if estado_subida != ESTADO_EXITO: 
                raise Exception("La subida de archivos falló.")

            # --- PASO 3: Guardado de Confirmación ---
            logs.append("\n--- PASO 3: Guardado de Confirmación ---")
            pdf_final_path, radicado_final, log_confirmacion = guardar_confirmacion_previsora(page, subfolder_path)
            logs.append(log_confirmacion)
            if not pdf_final_path: 
                raise Exception("El guardado de la confirmación falló.")
            
            # Si todos los pasos fueron exitosos, salimos del bucle con el resultado.
            return ESTADO_EXITO, radicado_final, codigo_factura, "\n".join(logs)

        except Exception as e:
            # Capturar CUALQUIER error y prepararse para el siguiente intento.
            logs.append(f"ADVERTENCIA: Ocurrió un error en el intento #{attempt}: {e}")
            
            # Solo tomamos un screenshot si es el ÚLTIMO intento fallido.
            if attempt == MAX_ATTEMPTS:
                logs.append("ERROR: Se alcanzó el número máximo de reintentos. Tomando screenshot final.")
                log_screenshot = guardar_screenshot_de_error(page, f"error_final_intento_{codigo_factura}")
                logs.append(log_screenshot)
            # El bucle 'for' continuará con el siguiente intento (si queda alguno).
    
    # Si el bucle termina sin un 'return' exitoso, significa que todos los intentos fallaron.
    return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)