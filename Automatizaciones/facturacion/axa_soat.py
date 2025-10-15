# AutomatizadorSOAT/Automatizaciones/facturacion/axa_soat.py

"""
Módulo de automatización para el proceso de FACTURACIÓN de AXA Colpatria SOAT.

Este módulo contiene la lógica específica para:
1.  Llenar el formulario de radicación de facturas por primera vez.
2.  Manejar los pop-ups de notificación de la plataforma.
3.  Subir los 5 archivos requeridos (PDFs, JSON, XML).
4.  Enviar el formulario y extraer el número de radicado final.

Reutiliza funciones comunes como `login` del módulo de Glosas de AXA.
"""

# --- Importaciones de Sistema y Librerías Externas ---
import re
import traceback
from pathlib import Path
from datetime import datetime
from playwright.sync_api import Page, expect, TimeoutError as PlaywrightTimeoutError

# --- Importaciones Internas del Proyecto ---
try:
    from Configuracion.constantes import *
    from Core.utilidades import encontrar_documentos_facturacion_axa
except ImportError as e:
    raise ImportError(f"ERROR CRITICO: Importaciones fallaron: {e}")

# Reutilización de funciones comunes desde el módulo de glosas de AXA
from ..glosas.axa_soat import login, asegurar_extension_pdf_minuscula

# --- Definición de Estados del Proceso ---
ESTADO_EXITO = "EXITO"
ESTADO_FALLO = "FALLO"
ESTADO_OMITIDO_RADICADO = "OMITIDO_RADICADO"

# ==============================================================================
# --- FUNCIONES DE INTERACCIÓN WEB ESPECIALIZADAS PARA FACTURACIÓN ---
# ==============================================================================

def navegar_a_inicio(page: Page) -> tuple[bool, str]:
    """
    Función placeholder. Para AXA, el login lleva directamente al formulario
    necesario, por lo que no se requiere navegación adicional.
    """
    return True, "Navegación a inicio no es necesaria para AXA."


def handle_optional_popup(page: Page, timeout_ms: int = 5000) -> str:
    """
    Busca y hace clic en un pop-up genérico de "Aceptar".
    Está diseñado para no fallar si el pop-up no aparece.

    Args:
        page: La instancia de la página de Playwright.
        timeout_ms: Tiempo máximo de espera en milisegundos.

    Returns:
        Un mensaje de log indicando el resultado.
    """
    popup_selector = "div.justify-center.items-center.text-center > button:has-text('Aceptar')"
    try:
        page.locator(popup_selector).click(timeout=timeout_ms)
        return "  - Pop-up de notificación manejado."
    except PlaywrightTimeoutError:
        return "  - Pop-up de notificación no apareció."
    except Exception as e:
        return f"  - ADVERTENCIA: No se pudo procesar pop-up opcional: {e}"


def llenar_formulario(page: Page, codigo_factura: str, cuv: str) -> tuple[bool, str]:
    """
    Rellena todos los campos del formulario de radicación de facturas.
    """
    logs = ["Llenando formulario de facturación..."]
    try:
        page.locator(AXASOAT_SELECTOR_NIT_RAMO).fill(AXASOAT_NIT_RAMO_FORM)
        page.locator(AXASOAT_SELECTOR_TIPO_CUENTA).select_option(label=AXASOAT_TIPO_CUENTA_FORM_FACTURACION)
        logs.append(handle_optional_popup(page))

        today_str = datetime.now().strftime("%Y-%m-%d")
        page.locator(AXASOAT_SELECTOR_FECHA_ATENCION).fill(today_str)
        page.locator(AXASOAT_SELECTOR_NUMERO_FACTURA).fill(codigo_factura)
        logs.append(f"  - Factura: {codigo_factura}")
        logs.append(handle_optional_popup(page))

        checkbox_rips = page.locator(AXASOAT_SELECTOR_CHECKBOX_RIPS)
        if not checkbox_rips.is_checked():
            checkbox_rips.check()
            logs.append("  - Checkbox RIPS activado.")
        
        page.locator(AXASOAT_SELECTOR_CUV_INPUT).fill(cuv)
        logs.append(f"  - CUV ingresado: {cuv}")

        page.locator(AXASOAT_SELECTOR_CORREO).fill(AXASOAT_CORREO_FACTURACION)
        page.locator(AXASOAT_SELECTOR_USUARIO_REGISTRA).fill(AXASOAT_USUARIO_REGISTRA_FACTURACION)

        logs.append("Formulario llenado con éxito.")
        return True, "\n".join(logs)

    except Exception as e:
        page.screenshot(path=f"error_formulario_axa_{codigo_factura}.png")
        logs.append(f"ERROR: {e}")
        traceback.print_exc()
        return False, "\n".join(logs)


def subir_archivos_facturacion(page: Page, paths_documentos: dict[str, Path]) -> tuple[bool, str]:
    """
    Sube los 5 archivos requeridos a sus respectivos campos de carga y
    confirma que la subida fue exitosa.
    """
    logs = ["Subiendo archivos requeridos..."]
    try:
        # Mapea el tipo de documento interno al selector CSS del input de archivo.
        MAPEO_SELECTORES = {
            "factura": AXASOAT_SELECTOR_INPUT_FACTURA_FILE,
            "furips": AXASOAT_SELECTOR_INPUT_FURIPS_FILE,
            "hc": AXASOAT_SELECTOR_INPUT_HC_FILE,
            "rips": AXASOAT_SELECTOR_INPUT_RIPS_JSON,
            "fev": AXASOAT_SELECTOR_INPUT_FEV_XML
        }
        
        for doc_tipo, path in paths_documentos.items():
            # Manejar pop-ups que puedan aparecer entre subidas.
            logs.append(handle_optional_popup(page, 2000))

            selector = MAPEO_SELECTORES.get(doc_tipo)
            if not selector:
                return False, f"ERROR: Selector para '{doc_tipo}' no mapeado."
            
            logs.append(f"  -> Subiendo {doc_tipo.upper()}: {path.name}...")
            page.locator(selector).set_input_files(path)
            
            # Verificación: Esperar a que el nombre del archivo aparezca en la UI
            # y que el ícono de "eliminar" (papelera) esté visible.
            filename_locator = page.get_by_text(path.name, exact=True)
            expect(filename_locator).to_be_visible(timeout=120000) # Timeout largo por si el archivo es grande
            icono_confirmacion = filename_locator.locator("xpath=./ancestor::div[1]").locator("img[alt='img-response']")
            expect(icono_confirmacion).to_be_visible(timeout=5000)
            logs.append(f"  -> {doc_tipo.upper()} subido y confirmado OK.")
            
        return True, "\n".join(logs)
        
    except Exception as e:
        page.screenshot(path=f"error_subida_archivos_axa.png")
        logs.append(f"ERROR: {e}")
        traceback.print_exc()
        return False, "\n".join(logs)


def enviar_y_finalizar_radicado(page: Page) -> tuple[str | None, str]:
    """
    Hace clic en el botón de envío final, espera el pop-up de éxito,
    extrae el número de radicado y reinicia el formulario.
    """
    logs = ["Finalizando el proceso de radicación..."]
    radicado_extraido = None
    try:
        logs.append(handle_optional_popup(page))
        page.locator(AXASOAT_SELECTOR_BOTON_ENVIAR).click()
        logs.append("  -> Clic en 'Enviar'.")
        
        # El sitio puede mostrar diferentes mensajes de éxito. Usamos `or_()`
        # para esperar cualquiera de los dos.
        selector_exito_glosas = "p:has-text('reclamacion registrada correctamente')"
        selector_exito_facturacion = "p:has-text('Proceso exitoso')"
        
        logs.append("  -> Esperando modal de confirmación final...")
        popup_final = page.locator(selector_exito_glosas).or_(page.locator(selector_exito_facturacion))
        expect(popup_final).to_be_visible(timeout=60000)
        logs.append("  -> Modal de confirmación final detectado.")
        
        # Extraer el número de radicado del texto del pop-up.
        texto_popup = popup_final.inner_text()
        match = re.search(r"-\s*(\d+)", texto_popup)
        if match:
            radicado_extraido = match.group(1)
            logs.append(f"  -> ¡ÉXITO! Radicado extraído: {radicado_extraido}")
        else:
            logs.append(f"  -> ADVERTENCIA: No se pudo extraer el radicado del texto: '{texto_popup}'")

        # Cerrar el modal final y esperar a que la página se reinicie.
        page.locator("button:has-text('Aceptar')").click()
        expect(page.locator(AXASOAT_SELECTOR_FORMULARIO_VERIFY)).to_be_enabled(timeout=20000)
        logs.append("  -> Modal final cerrado. Formulario listo para la siguiente.")
        
        return radicado_extraido, "\n".join(logs)
    except Exception as e:
        page.screenshot(path="error_finalizacion_axa.png")
        logs.append(f"ERROR en finalización: {e}")
        traceback.print_exc()
        return None, "\n".join(logs)

# ==============================================================================
# --- FUNCIÓN ORQUESTADORA PRINCIPAL ---
# ==============================================================================

def procesar_carpeta(page: Page, subfolder_path: Path, subfolder_name: str, context: str = 'default') -> tuple[str, str | None, str | None, str]:
    """
    Orquesta el flujo completo de radicación de facturación para una carpeta.
    """
    logs = [f"--- Iniciando AXA FACTURACIÓN | Carpeta: '{subfolder_name}' ---"]
    radicado, codigo_factura = None, None
    try:
        # 1. Verificación previa de omisión
        if any(f.name.lower().endswith("-recibido.pdf") for f in subfolder_path.iterdir()):
            return ESTADO_OMITIDO_RADICADO, None, None, "\n".join(logs + ["OMITIENDO: Ya existe radicado."])
            
        # 2. Búsqueda y validación de archivos
        codigo_factura, cuv, archivos_a_subir, docs_log = encontrar_documentos_facturacion_axa(subfolder_path, subfolder_name)
        logs.append(docs_log)
        if not all([codigo_factura, cuv, archivos_a_subir]):
            return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)

        # 3. Preparación de archivos (renombrar PDFs a minúsculas)
        for tipo, path in archivos_a_subir.items():
            if path.suffix.lower() == ".pdf":
                path_final, rename_log = asegurar_extension_pdf_minuscula(path)
                archivos_a_subir[tipo] = path_final
                logs.append(rename_log)

        # 4. Proceso de llenado y subida en la web
        form_ok, form_log = llenar_formulario(page, codigo_factura, cuv)
        logs.append(form_log)
        if not form_ok:
            return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)

        logs.append(handle_optional_popup(page, 3000))
        
        upload_ok, upload_log = subir_archivos_facturacion(page, archivos_a_subir)
        logs.append(upload_log)
        if not upload_ok:
            return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)
            
        radicado, final_log = enviar_y_finalizar_radicado(page)
        logs.append(final_log)
        if not radicado:
            return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)
            
        return ESTADO_EXITO, radicado, codigo_factura, "\n".join(logs)
        
    except Exception as e:
        logs.append(f"ERROR CRÍTICO en el orquestador: {e}")
        traceback.print_exc()
        return ESTADO_FALLO, radicado, codigo_factura, "\n".join(logs)