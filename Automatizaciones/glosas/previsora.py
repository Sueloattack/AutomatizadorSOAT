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
    """Carga el PDF y maneja SOLAMENTE los pop-ups INTERMEDIOS."""
    logs = [f"  Subiendo archivo: {pdf_path.name}..."]
    try:
        page.locator(f"#{PREVISORA_ID_INPUT_FILE_FORM}").set_input_files(pdf_path)
        logs.append("    - Archivo adjuntado.")
        
        page.locator(f"#{PREVISORA_ID_BOTON_ENVIAR_FORM}").click()
        logs.append("    - Clic en 'Enviar'.")

        page.locator(PREVISORA_XPATH_POPUP_ENVIO_SI_CONTINUAR).click(timeout=15000)
        logs.append("    - Pop-up 'Sí, continuar' confirmado.")
        
        # *** ELIMINADO ***
        # El clic en "Continuar y Guardar" ahora lo hará la siguiente función.
        # Esto asegura que no nos quedemos esperando aquí por una navegación que no ocurrirá.

        return ESTADO_EXITO, "\n".join(logs)
    except Exception as e:
        error_msg = f"ERROR inesperado al subir o enviar: {e}"
        logs.append(error_msg); traceback.print_exc(); page.screenshot(path="error_subida_archivo.png")
        return ESTADO_FALLO, "\n".join(logs)

# --- ESTA FUNCIÓN HA SIDO MODIFICADA ---
def guardar_confirmacion_previsora(page: Page, output_folder: Path) -> tuple[str | None, str | None, str]:
    """Hace el clic final, espera el pop-up, extrae datos, guarda PDF y limpia la pantalla."""
    logs = ["  Esperando pop-up de confirmación final..."]
    try:
        # *** AÑADIDO: Ahora esta función hace el clic final ***
        logs.append("    - Haciendo clic en 'Continuar y guardar'...")
        # El no_wait_after=True le dice a Playwright: "haz clic y no esperes a que la página navegue".
        page.locator(PREVISORA_XPATH_POPUP_CONTINUAR_GUARDAR).click(no_wait_after=True)
        logs.append("    - Clic realizado. Ahora esperando el pop-up de 'Registro Generado'.")

        popup_final = page.locator(PREVISORA_XPATH_FINAL_CONFIRMATION_POPUP_CONTAINER)
        expect(popup_final).to_be_visible(timeout=90000)
        logs.append("    - Pop-up final detectado.")
        
        texto_popup = popup_final.inner_text()
        radicado_match = re.search(r"Tu codigo es:\s*'(\d+)'", texto_popup, re.IGNORECASE)
        radicado_extraido = radicado_match.group(1) if radicado_match else "Extracción Fallida"
        logs.append(f"    - Código de radicado extraído: {radicado_extraido}")
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        temp_png_path = output_folder / f"temp_confirmacion_{timestamp}.png"
        rad_pdf_path = output_folder / "RAD.pdf"
        
        popup_final.screenshot(path=temp_png_path)
        
        with Image.open(temp_png_path) as img:
            img.convert("RGB").save(rad_pdf_path)
        temp_png_path.unlink()
        logs.append(f"    - Confirmación guardada como {rad_pdf_path.name}")
        
        # Este paso es CRÍTICO para limpiar la pantalla para la siguiente iteración
        page.locator(PREVISORA_XPATH_BOTON_NUEVA_RECLAMACION).click()
        expect(page.locator(f"#{PREVISORA_ID_FACTURA_FORM}")).to_be_enabled(timeout=20000)
        logs.append("    - Clic en 'Nueva Reclamación'. Pantalla limpia para la siguiente.")
        
        return str(rad_pdf_path), radicado_extraido, "\n".join(logs)
    except Exception as e:
        error_msg = f"ERROR inesperado en la confirmación final: {e}"
        logs.append(error_msg); traceback.print_exc(); page.screenshot(path="error_confirmacion.png")
        return None, None, "\n".join(logs)

def procesar_carpeta(page: Page, subfolder_path: Path, subfolder_name: str) -> tuple[str, str | None, str | None, str]:
    """Orquestador principal para Previsora, con verificaciones previas robustas."""
    logs = [f"--- Iniciando Playwright/Previsora para: '{subfolder_name}' ---"]
    try:
        # --- BLOQUE DE VERIFICACIONES PREVIAS (PRE-FLIGHT CHECKS) ---

        # 1. Verificar si el nombre de la carpeta contiene palabras de exclusión.
        nombre_mayus = subfolder_name.upper()
        if any(palabra in nombre_mayus for palabra in PALABRAS_EXCLUSION_CARPETAS):
            msg = f"OMITIENDO: El nombre de la carpeta contiene una palabra de exclusión."
            logs.append(msg)
            return ESTADO_OMITIDO_RADICADO, None, None, "\n".join(logs)

        # 2. Verificar si ya existe un RAD.pdf (prueba de radicación para Previsora).
        if (subfolder_path / "RAD.pdf").is_file():
            msg = "OMITIENDO: Ya existe un archivo RAD.pdf en esta carpeta."
            logs.append(msg)
            return ESTADO_OMITIDO_RADICADO, None, None, "\n".join(logs)

        # --- FIN DE VERIFICACIONES ---
        
        codigo_factura, pdf_path, pdf_log = encontrar_y_validar_pdfs(
            subfolder_path, subfolder_name, PREVISORA_NOMBRE_EN_PDF
        )
        logs.append(pdf_log)
        if not (codigo_factura and pdf_path):
            return ESTADO_FALLO, None, None, "\n".join(logs)
        
        estado_llenado, log_llenado = llenar_formulario_previsora(page, codigo_factura)
        logs.append(log_llenado)
        if estado_llenado != ESTADO_EXITO:
            return estado_llenado, None, codigo_factura, "\n".join(logs)

        estado_subida, log_subida = subir_y_enviar_previsora(page, pdf_path)
        logs.append(log_subida)
        if estado_subida != ESTADO_EXITO:
            return estado_subida, None, codigo_factura, "\n".join(logs)
            
        pdf_final_path, radicado_final, log_confirmacion = guardar_confirmacion_previsora(page, subfolder_path)
        logs.append(log_confirmacion)

        if pdf_final_path:
            return ESTADO_EXITO, radicado_final, codigo_factura, "\n".join(logs)
        else:
            return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)

    except Exception as e:
        error_msg = f"ERROR CRÍTICO en Previsora/procesar_carpeta para '{subfolder_name}': {e}"
        traceback.print_exc()
        return ESTADO_FALLO, None, None, "\n".join(logs + [error_msg])