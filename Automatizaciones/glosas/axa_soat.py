# AutomatizadorSOAT/Automatizaciones/glosas/axa_soat.py

import re
import time
import traceback
from pathlib import Path
from datetime import datetime # Necesario para la fecha de hoy
from playwright.sync_api import Page, expect, TimeoutError as PlaywrightTimeoutError

try:
    from Configuracion.constantes import *
    from Core.utilidades import encontrar_y_validar_pdfs, buscar_y_guardar_radicado_email
except ImportError as e:
    raise ImportError(f"ERROR CRITICO: No se pudieron importar constantes: {e}")

# Estados consistentes con otros módulos
ESTADO_EXITO = "EXITO"
ESTADO_FALLO = "FALLO"
ESTADO_OMITIDO_RADICADO = "OMITIDO_RADICADO"
ESTADO_OMITIDO_DUPLICADA = "OMITIDO_DUPLICADA"

def check_server_error(page: Page) -> bool:
    """Verifica si la página actual muestra un error de servidor '502 Bad Gateway'."""
    try:
        # is_visible() no espera el timeout completo si lo encuentra, es rápido.
        # Le damos un timeout muy corto. Si no lo encuentra, no es un error, significa que la página está OK.
        if page.locator(AXASOAT_SELECTOR_SERVER_ERROR_H1).is_visible(timeout=1000):
            return True
    except PlaywrightTimeoutError:
        # Esto es lo esperado si el elemento no existe (la página está bien).
        pass
    return False


def login(page: Page) -> tuple[bool, str]:
    """Realiza el login en AXA, maneja el pop-up y ahora verifica si el sitio está caído."""
    logs = ["Iniciando login en AXA SOAT..."]
    try:
        page.goto(AXASOAT_LOGIN_URL, timeout=60000)
        logs.append(f"  Página cargada: {AXASOAT_LOGIN_URL}")

        # --- AÑADIDO: Verificación de página caída ---
        logs.append("  Verificando estado del servidor...")
        if check_server_error(page):
            error_msg = "ERROR CRÍTICO: El servidor de AXA (claimonline.com.co) parece estar caído (Error 502)."
            logs.append(error_msg)
            return False, "\n".join(logs)
        logs.append("  - Servidor OK.")
        
        # El resto del login es igual
        page.locator(AXASOAT_SELECTOR_TIPO_RECLAMANTE).select_option(label=AXASOAT_TIPO_RECLAMANTE_LOGIN)
        logs.append(f"  - Tipo Reclamante: '{AXASOAT_TIPO_RECLAMANTE_LOGIN}'")
        page.locator(AXASOAT_SELECTOR_DOCUMENTO).fill(AXASOAT_DOCUMENTO_LOGIN)
        logs.append(f"  - Documento: '{AXASOAT_DOCUMENTO_LOGIN}'")
        page.locator(AXASOAT_SELECTOR_BOTON_LOGIN).click()
        logs.append("  - Clic en 'Login'.")

        try:
            logs.append("  - Esperando posible pop-up de notificación...")
            page.locator(AXASOAT_SELECTOR_MODAL_ACEPTAR).click(timeout=5000)
            logs.append("  - Pop-up de notificación cerrado.")
        except PlaywrightTimeoutError:
            logs.append("  - Pop-up no apareció, continuando.")

        expect(page.locator(AXASOAT_SELECTOR_FORMULARIO_VERIFY)).to_be_enabled(timeout=30000)
        logs.append("Login exitoso, formulario de radicación cargado.")
        
        return True, "\n".join(logs)
    except Exception as e:
        error_msg = f"ERROR inesperado durante el login en AXA SOAT: {e}"
        logs.append(error_msg); traceback.print_exc()
        page.screenshot(path="error_login_axa.png")
        return False, "\n".join(logs)


def llenar_formulario(page: Page, codigo_factura: str) -> tuple[bool, str]:
    """Llena los campos del formulario de radicación de AXA."""
    logs = ["Llenando formulario de radicación..."]
    try:
        # Llenar NIT Ramo SOAT Colpatria
        page.locator(AXASOAT_SELECTOR_NIT_RAMO).fill(AXASOAT_NIT_RAMO_FORM)
        logs.append(f"  - NIT Ramo SOAT: {AXASOAT_NIT_RAMO_FORM}")

        # Seleccionar Tipo de Cuenta
        page.locator(AXASOAT_SELECTOR_TIPO_CUENTA).select_option(label=AXASOAT_TIPO_CUENTA_FORM_RESPUESTA_OBJECION)
        logs.append(f"  - Tipo de cuenta: '{AXASOAT_TIPO_CUENTA_FORM_RESPUESTA_OBJECION}'")
        
        # Llenar Fecha de Atención
        today_str = datetime.now().strftime("%Y-%m-%d")
        page.locator(AXASOAT_SELECTOR_FECHA_ATENCION).fill(today_str)
        logs.append(f"  - Fecha de Atención: {today_str}")

        # ---- NUEVO: Llenar el N° de Factura con el código extraído ----
        page.locator(AXASOAT_SELECTOR_NUMERO_FACTURA).fill(codigo_factura)
        logs.append(f"  - N° Factura: {codigo_factura}")
        # ----------------------------------------------------------------

        # ---- AÑADIDO: Manejar modal de confirmación de factura ----
        try:
            logs.append("  - Esperando modal de confirmación de factura...")
            page.locator(AXASOAT_SELECTOR_MODAL_FACTURA_ACEPTAR).click(timeout=5000)
            logs.append("  - Modal 'Aceptar' cerrado.")
        except PlaywrightTimeoutError:
            logs.append("  - Modal de confirmación no apareció, continuando.")
        # -----------------------------------------------------------------
        
        # 1. Desactivar el checkbox de carga de archivos RIPS
        # Usamos .uncheck() que es el método específico y seguro para esto.
        page.locator(AXASOAT_SELECTOR_CHECKBOX_RIPS).uncheck()
        logs.append("  - Checkbox 'Desea cargar archivos RIPS' desactivado.")
        
        # 2. Llenar el correo electrónico
        page.locator(AXASOAT_SELECTOR_CORREO).fill(AXASOAT_CORREO_FORM)
        logs.append(f"  - Correo Electrónico: {AXASOAT_CORREO_FORM}")

        # 3. Llenar el usuario que registra
        page.locator(AXASOAT_SELECTOR_USUARIO_REGISTRA).fill(AXASOAT_USUARIO_REGISTRA_FORM)
        logs.append(f"  - Usuario que Registra: {AXASOAT_USUARIO_REGISTRA_FORM}")
        logs.append("Formulario llenado con éxito.")
        return True, "\n".join(logs)

    except Exception as e:
        error_msg = f"ERROR inesperado al llenar el formulario de AXA: {e}"
        logs.append(error_msg); traceback.print_exc()
        page.screenshot(path="error_formulario_axa.png")
        return False, "\n".join(logs)
    
def navegar_a_inicio(page: Page) -> tuple[bool, str]:
    return True, "Navegación a inicio no es necesaria para AXA, se omite este paso."

def asegurar_extension_pdf_minuscula(pdf_path: Path) -> tuple[Path, str]:
    """
    Verifica si un archivo PDF tiene la extensión en mayúsculas (.PDF)
    y, si es así, lo renombra a minúsculas (.pdf).
    
    Devuelve la ruta final (ya sea la original o la nueva) y un log.
    """
    logs = [f"  Verificando extensión del archivo: {pdf_path.name}..."]
    if not pdf_path.is_file():
        return pdf_path, f"  ERROR: El archivo de respuesta no existe en la ruta {pdf_path}."

    if pdf_path.suffix == ".PDF":
        nuevo_path = pdf_path.with_suffix(".pdf")
        try:
            pdf_path.rename(nuevo_path)
            logs.append(f"  -> Renombrado: '{pdf_path.name}' -> '{nuevo_path.name}'")
            return nuevo_path, "\n".join(logs)
        except OSError as e:
            error_msg = f"  -> ERROR al renombrar el archivo: {e}"
            logs.append(error_msg)
            return pdf_path, "\n".join(logs) # Devolvemos la ruta original en caso de error
    else:
        logs.append("  -> Extensión ya es minúscula. No se requiere acción.")
        return pdf_path, "\n".join(logs)

def subir_archivo_respuesta(page: Page, pdf_path: Path) -> tuple[bool, str]:
    """Sube el archivo de respuesta de glosa al formulario."""
    logs = [f"  Subiendo archivo de respuesta: {pdf_path.name}..."]
    try:
        page.locator(AXASOAT_SELECTOR_INPUT_FILE).set_input_files(pdf_path)
        # Podríamos añadir una espera aquí si la subida tarda
        # expect(page.locator("algun-indicador-de-exito")).to_be_visible()
        logs.append("  -> Archivo adjuntado correctamente.")
        return True, "\n".join(logs)
    except Exception as e:
        error_msg = f"  -> ERROR al subir el archivo: {e}"
        logs.append(error_msg); traceback.print_exc()
        page.screenshot(path="error_subida_archivo_axa.png")
        return False, "\n".join(logs)

def procesar_carpeta(page: Page, subfolder_path: Path, subfolder_name: str) -> tuple[str, str | None, str | None, str]:
    """Orquestador principal para AXA, con verificaciones previas e integración de email."""
    logs = [f"--- Iniciando procesamiento para AXA | Carpeta: '{subfolder_name}' ---"]
    try:
        # 1. Verificaciones Previas
        if any(p in subfolder_name.upper() for p in PALABRAS_EXCLUSION_CARPETAS) or \
           any(f.name.lower().endswith("-recibido.pdf") for f in subfolder_path.iterdir() if f.is_file()):
            logs.append("OMITIENDO: Carpeta excluida por nombre o ya radicada.")
            return ESTADO_OMITIDO_RADICADO, None, None, "\n".join(logs)

        # 2. Búsqueda y preparación de archivos
        codigo_factura, pdf_path, pdf_log = encontrar_y_validar_pdfs(subfolder_path, subfolder_name, AXASOAT_NOMBRE_EN_PDF)
        logs.append(pdf_log)
        if not (codigo_factura and pdf_path): return ESTADO_FALLO, None, None, "\n".join(logs)
        path_pdf_final, rename_log = asegurar_extension_pdf_minuscula(pdf_path); logs.append(rename_log)

        # 3. Interacción Web
        form_ok, form_log = llenar_formulario(page, codigo_factura); logs.append(form_log)
        if not form_ok: return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)

        upload_ok, upload_log = subir_archivo_respuesta(page, path_pdf_final); logs.append(upload_log)
        if not upload_ok: return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)
            
        radicado_final, final_log = enviar_y_finalizar_radicado(page); logs.append(final_log)
        if not radicado_final: return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)
            
        # 4. Integración Externa (Email)
        logs.append(f"Proceso web OK (Radicado: {radicado_final}). Buscando email...")
        email_ok, email_log = buscar_y_guardar_radicado_email(radicado_final, subfolder_path)
        logs.append(email_log)
        if not email_ok: logs.append(f"ADVERTENCIA: No se pudo obtener el PDF del email.")

        return ESTADO_EXITO, radicado_final, codigo_factura, "\n".join(logs)

    except Exception as e:
        error_msg = f"ERROR CRÍTICO en AXA/procesar_carpeta: {e}"; traceback.print_exc()
        return ESTADO_FALLO, None, None, "\n".join(logs + [error_msg])

def enviar_y_finalizar_radicado(page: Page) -> tuple[str | None, str]:
    """
    Confirma la subida del archivo, maneja el modal intermedio, envía el formulario,
    extrae el radicado final y cierra el proceso.
    """
    logs = ["  Finalizando el proceso de radicación..."]
    radicado_extraido = None
    try:
        # 1. Esperar a que la carga del archivo se complete (aparece "100%")
        expect(page.locator(AXASOAT_SELECTOR_UPLOAD_COMPLETE)).to_be_visible(timeout=60000)
        logs.append("  -> Carga de archivo completada al 100%.")

        # --- NUEVO BLOQUE DE CÓDIGO AÑADIDO PARA MANEJAR EL MODAL ---
        # 2. Antes de enviar, manejamos el modal de confirmación de factura
        try:
            logs.append("  -> Esperando modal intermedio '¿Desea Continuar?'...")
            page.locator(AXASOAT_SELECTOR_MODAL_POST_UPLOAD_ACEPTAR).click(timeout=10000)
            logs.append("  -> Clic en 'Aceptar' en el modal intermedio.")
        except PlaywrightTimeoutError:
            # Si el modal no aparece, no es un error. Puede que lo quiten en el futuro.
            logs.append("  -> ADVERTENCIA: No apareció el modal intermedio '¿Desea Continuar?'. El proceso continúa.")
        # --- FIN DEL NUEVO BLOQUE ---

        # 3. Hacer clic en el botón "Enviar" (ahora debería estar visible y clickeable)
        page.locator(AXASOAT_SELECTOR_BOTON_ENVIAR).click()
        logs.append("  -> Clic en 'Enviar'.")
        
        # 4. Esperar el modal final y extraer el radicado (sin cambios)
        modal_final = page.locator(AXASOAT_SELECTOR_MODAL_FINAL_TEXTO)
        expect(modal_final).to_be_visible(timeout=60000)
        logs.append("  -> Modal de confirmación final detectado.")
        
        texto_popup = modal_final.inner_text()
        match = re.search(r"reclamacion registrada correctamente\s*-\s*(\d+)", texto_popup, re.IGNORECASE)
        if match:
            radicado_extraido = match.group(1)
            logs.append(f"  -> ¡ÉXITO! Radicado extraído: {radicado_extraido}")
        else:
            logs.append("  -> ADVERTENCIA: No se pudo extraer el número de radicado del texto del modal.")

        # 5. Cerrar el modal final (sin cambios)
        page.locator(AXASOAT_SELECTOR_MODAL_FINAL_ACEPTAR).click()
        expect(page.locator(AXASOAT_SELECTOR_FORMULARIO_VERIFY)).to_be_enabled(timeout=20000)
        logs.append("  -> Modal final cerrado. Formulario listo para la siguiente iteración.")
        
        return radicado_extraido, "\n".join(logs)
            
    except Exception as e:
        error_msg = f"  -> ERROR en la finalización: {e}"; traceback.print_exc()
        page.screenshot(path="error_finalizacion_axa.png")
        return None, "\n".join(logs + [error_msg])