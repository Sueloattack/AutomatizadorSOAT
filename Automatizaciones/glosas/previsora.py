# Automatizaciones/playwright_previsora.py
import time
import traceback
from pathlib import Path
import re

from Core.utilidades import encontrar_y_validar_pdfs
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
        logs.append(error_msg); traceback.print_exc(); page.screenshot(path="error_login.png")
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
        logs.append(error_msg); traceback.print_exc(); page.screenshot(path="error_navegacion.png")
        return False, "\n".join(logs)

def llenar_formulario_previsora(page: Page, codigo_factura: str) -> tuple[str, str]:
    """Llena el formulario con los datos de la factura."""
    logs = [f"  Llenando formulario (Factura: {codigo_factura})..."]
    try:
        dropdown_ciudad_container = page.locator(f"//input[@id='{PREVISORA_ID_CIUDAD_HIDDEN_FORM}']/..")
        opcion_ciudad = page.locator(PREVISORA_XPATH_CIUDAD_OPCION)
        factura_input = page.locator(f"#{PREVISORA_ID_FACTURA_FORM}")
        
        logs.append("    - Abriendo dropdown de Ciudad...")
        dropdown_ciudad_container.click()
        logs.append(f"    - Seleccionando '{PREVISORA_CIUDAD_FORM_NOMBRE}'...")
        opcion_ciudad.click()
        logs.append("    - Ciudad OK.")

        factura_input.fill(codigo_factura)
        page.locator(f"#{PREVISORA_ID_CORREO_FORM}").fill(PREVISORA_CORREO_FORM)
        page.locator(f"#{PREVISORA_ID_USUARIO_REGISTRA_FORM}").fill(PREVISORA_USUARIO_REGISTRA_FORM)
        page.locator(f"#{PREVISORA_ID_RAMO_FORM}").select_option(label=PREVISORA_RAMO_FORM)
        logs.append("    - Campos principales llenados.")
        
        try:
            page.locator(PREVISORA_XPATH_POPUP_FACTURA_CONTINUAR).click(timeout=10000)
            logs.append("    - Pop-up de factura existente manejado.")
        except PlaywrightTimeoutError:
            logs.append("    - Pop-up de factura no apareció, continuando.")

        time.sleep(0.5)
        if not factura_input.input_value():
            logs.append("    -> CAMPO FACTURA VACÍO. Omitiendo por duplicado.")
            return ESTADO_OMITIDO_DUPLICADA, "\n".join(logs)

        page.locator(f"#{PREVISORA_ID_AMPAROS_FORM}").select_option(value=PREVISORA_VALUE_AMPARO_FORM)
        page.locator(f"#{PREVISORA_ID_TIPO_CUENTA_FORM}").select_option(value=PREVISORA_VALUE_TIPO_CUENTA_FORM)
        logs.append("    - Amparos y Tipo de Cuenta OK.")
        return ESTADO_EXITO, "\n".join(logs)
    except Exception as e:
        error_msg = f"ERROR inesperado al llenar formulario: {e}"
        logs.append(error_msg); traceback.print_exc(); page.screenshot(path=f"error_formulario_{codigo_factura}.png")
        return ESTADO_FALLO, "\n".join(logs)

# --- ESTA FUNCIÓN HA SIDO MODIFICADA ---
def subir_y_enviar_previsora(page: Page, pdf_path: Path) -> tuple[str, str]:
    """Carga el PDF y maneja el primer pop-up de confirmación."""
    logs = [f"  Subiendo archivo: {pdf_path.name}..."]
    try:
        page.locator(f"#{PREVISORA_ID_INPUT_FILE_FORM}").set_input_files(pdf_path)
        logs.append("    - Archivo adjuntado.")
        
        page.locator(f"#{PREVISORA_ID_BOTON_ENVIAR_FORM}").click()
        logs.append("    - Clic en 'Enviar'.")

        # Clic en el primer pop-up sin esperar a que la página navegue
        page.locator(PREVISORA_XPATH_POPUP_ENVIO_SI_CONTINUAR).click(timeout=15000, no_wait_after=True)
        logs.append("    - Pop-up 'Sí, continuar' confirmado.")
        
        # EL PASO "CONTINUAR Y GUARDAR" SE HACE EN LA SIGUIENTE FUNCIÓN
        
        return ESTADO_EXITO, "\n".join(logs)
    except Exception as e:
        error_msg = f"ERROR inesperado al subir o enviar: {e}"
        page.screenshot(path=f"error_screenshot_subida_{pdf_path.stem}_{time.strftime('%H%M%S')}.png")
        logs.append(error_msg); traceback.print_exc()
        return ESTADO_FALLO, "\n".join(logs)

# --- ESTA FUNCIÓN HA SIDO MODIFICADA ---
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
        page.screenshot(path=f"error_screenshot_confirmacion_{output_folder.name}_{time.strftime('%H%M%S')}.png")
        logs.append(error_msg); traceback.print_exc()
        return None, None, "\n".join(logs)

# --- FUNCIÓN DE AYUDA PARA MANEJAR EL LLENADO CON REINTENTO ---
def _intentar_llenar_formulario(page: Page, codigo_factura: str) -> tuple[str, str]:
    """
    Intenta llenar el formulario. Si falla por un timeout (el "dropdown tímido"),
    recarga la página y lo intenta una vez más. Evita generar screenshots
    para este fallo común y esperado.
    """
    logs = []
    MAX_ATTEMPTS = 3
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            # Esta es la función que SÍ puede fallar
            return llenar_formulario_previsora(page, codigo_factura)
        except PlaywrightTimeoutError as e:
            # ¡Capturamos SOLO el TimeoutError!
            logs.append(f"ADVERTENCIA: Falló el llenado en intento #{attempt} (Timeout). Razón: {str(e).splitlines()[0]}")
            if attempt < MAX_ATTEMPTS:
                logs.append("  -> Recargando la página para reintentar...")
                page.reload(wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(2000)
            else:
                logs.append("ERROR: Se alcanzó el número máximo de reintentos para el llenado.")
                # Forzar la creación de un screenshot SOLO en el último fallo
                page.screenshot(path=f"error_final_formulario_{codigo_factura}_{time.strftime('%H%M%S')}.png")
                return ESTADO_FALLO, "\n".join(logs)
    
    # Esto no debería alcanzarse, pero es una salvaguarda
    return ESTADO_FALLO, "\n".join(logs)

def procesar_carpeta(page: Page, subfolder_path: Path, subfolder_name: str) -> tuple[str, str | None, str | None, str]:
    """Orquestador para Previsora, que ahora delega la lógica de reintento de llenado."""
    logs = [f"--- Iniciando Playwright/Previsora para: '{subfolder_name}' ---"]
    
    # Verificaciones previas
    palabras_encontradas = [p for p in PALABRAS_EXCLUSION_CARPETAS if p in subfolder_name.upper()]
    if palabras_encontradas:
        return ESTADO_OMITIDO_RADICADO, None, None, f"OMITIENDO: Nombre de carpeta contiene exclusión: '{', '.join(palabras_encontradas)}'."
    if (subfolder_path / "RAD.pdf").is_file():
        return ESTADO_OMITIDO_RADICADO, None, None, "OMITIENDO: Ya existe RAD.pdf."

    codigo_factura, pdf_path, pdf_log = encontrar_y_validar_pdfs(subfolder_path, subfolder_name, PREVISORA_NOMBRE_EN_PDF)
    logs.append(pdf_log)
    if not (codigo_factura and pdf_path):
        return ESTADO_FALLO, None, None, "\n".join(logs)
    
    # --- PROCESO WEB PRINCIPAL ---
    # Delegamos el llenado a la función de reintento inteligente.
    logs.append("\n--- PASO 1: Llenado de Formulario ---")
    estado_llenado, log_llenado = _intentar_llenar_formulario(page, codigo_factura)
    logs.append(log_llenado)

    # Si el llenado falla definitivamente, lo contamos como duplicado u otro fallo y paramos.
    if estado_llenado == ESTADO_OMITIDO_DUPLICADA:
        return ESTADO_OMITIDO_DUPLICADA, None, codigo_factura, "\n".join(logs)
    if estado_llenado != ESTADO_EXITO:
        return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)

    try:
        # Los pasos siguientes son críticos; si fallan, son un error definitivo.
        logs.append("\n--- PASO 2: Subida de Archivos ---")
        estado_subida, log_subida = subir_y_enviar_previsora(page, pdf_path)
        logs.append(log_subida)
        if estado_subida != ESTADO_EXITO: raise Exception("Fallo en la subida de archivos.")

        logs.append("\n--- PASO 3: Guardado de Confirmación ---")
        pdf_final_path, radicado_final, log_confirmacion = guardar_confirmacion_previsora(page, subfolder_path)
        logs.append(log_confirmacion)
        if not pdf_final_path: raise Exception("Fallo al guardar la confirmación final.")
            
        logs.append(f"\n--- ÉXITO COMPLETO! Carpeta '{subfolder_name}' procesada. Radicado: {radicado_final} ---")
        return ESTADO_EXITO, radicado_final, codigo_factura, "\n".join(logs)

    except Exception as e:
        logs.append(f"\nERROR CRÍTICO después del llenado: {e}")
        return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)