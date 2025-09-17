import traceback
from pathlib import Path
import time
import re

from playwright.sync_api import Page, expect, TimeoutError as PlaywrightTimeoutError
try:
    from PIL import Image
except ImportError:
    raise ImportError("Falta Pillow. pip install Pillow")

try:
    from Configuracion.constantes import *
    from Core.utilidades import encontrar_documentos_facturacion
except ImportError:
    raise ImportError("ERROR CRITICO: No se pudieron importar módulos.")

from ..glosas.previsora import login, navegar_a_inicio, guardar_confirmacion_previsora, _verificar_pagina_activa

# Estados
ESTADO_EXITO = "EXITO"
ESTADO_FALLO = "FALLO"
ESTADO_OMITIDO_RADICADO = "OMITIDO_RADICADO"
ESTADO_OMITIDO_DUPLICADA = "OMITIDO_DUPLICADA"

# --- FUNCIONES ESPECIALIZADAS PARA FACTURACIÓN ---
def llenar_formulario_facturacion(page: Page, codigo_factura: str) -> tuple[str, str]:
    """
    Llena el formulario de Facturación, REPLICANDO la lógica robusta de
    manejo de pop-ups y verificación de duplicados del módulo de Glosas.
    """
    logs = [f"  Llenando formulario de Facturación (Factura: {codigo_factura})..."]
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
        page.locator(f"#{PREVISORA_ID_TIPO_CUENTA_FORM}").select_option(value=PREVISORA_VALUE_TIPO_CUENTA_FACTURACION)
        logs.append("    - Amparos y Tipo de Cuenta OK.")
        return ESTADO_EXITO, "\n".join(logs)
    except Exception as e:
        error_msg = f"ERROR inesperado al llenar formulario de facturación: {e}"
        logs.append(error_msg); 
        traceback.print_exc(); 
        page.screenshot(path=f"error_form_facturacion_{codigo_factura}.png")
        return ESTADO_FALLO, "\n".join(logs + [error_msg])

def subir_archivos_facturacion(page: Page, documentos: dict[str, Path]) -> tuple[str, str]:
    """Sube los 4 archivos y hace clic en el primer pop-up de confirmación."""
    logs = [f"  Subiendo archivos de facturación..."]
    try:
        expect(page.locator(f"#{PREVISORA_ID_INPUT_FACTURA}")).to_be_visible(timeout=10000)
        
        ruta_hc = documentos["hc"]
        page.locator(f"#{PREVISORA_ID_INPUT_FURIPS}").set_input_files(documentos["furips"])
        page.locator(f"#{PREVISORA_ID_INPUT_FACTURA}").set_input_files(documentos["factura"])
        page.locator(f"#{PREVISORA_ID_INPUT_HC}").set_input_files(ruta_hc)
        page.locator(f"#{PREVISORA_ID_INPUT_SOPORTES_HC}").set_input_files(ruta_hc)
        logs.append("    - Archivos adjuntados.")

        page.locator(f"#{PREVISORA_ID_BOTON_ENVIAR_FACTURACION}").click()
        logs.append("    - Clic en el botón 'Enviar'.")
        
        page.locator(PREVISORA_XPATH_POPUP_ENVIO_SI_CONTINUAR).click(timeout=15000, no_wait_after=True)
        logs.append("    - Pop-up 'Sí, continuar' confirmado.")
        
        return ESTADO_EXITO, "\n".join(logs)
    except Exception as e:
        error_msg = f"ERROR inesperado al subir archivos de facturación: {e}"
        page.screenshot(path=f"error_subida_facturacion.png")
        logs.append(error_msg); traceback.print_exc()
        return ESTADO_FALLO, "\n".join(logs + [error_msg])

# --- ORQUESTADOR PRINCIPAL (RÉPLICA DE LA LÓGICA DE GLOSAS) ---
def procesar_carpeta(page: Page, subfolder_path: Path, subfolder_name: str) -> tuple[str, str | None, str | None, str]:
    """
    Orquestador para Facturación con la estrategia de reintento proactiva.
    """
    logs = [f"--- Iniciando Proceso de FACTURACIÓN (Previsora) para: '{subfolder_name}' ---"]
    
    # Verificaciones previas
    if any(p in subfolder_name.upper() for p in PALABRAS_EXCLUSION_CARPETAS) or (subfolder_path / "RAD.pdf").is_file():
        return ESTADO_OMITIDO_RADICADO, None, None, f"OMITIENDO: Carpeta excluida por nombre o ya radicada."

    codigo_factura, documentos, docs_log = encontrar_documentos_facturacion(subfolder_path, subfolder_name)
    logs.append(docs_log)
    if not (codigo_factura and documentos):
        return ESTADO_FALLO, None, None, "\n".join(logs)
        
    MAX_ATTEMPTS = 3
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            logs.append(f"\n--- Intento de radicación #{attempt}/{MAX_ATTEMPTS} ---")
            
            if attempt > 1:
                logs.append("   -> Fallo en intento anterior. Recargando la página...")
                page.reload(wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(3000)
            
            _verificar_pagina_activa(page)
            
            # PASO 1: Llenado de Formulario
            estado_llenado, log_llenado = llenar_formulario_facturacion(page, codigo_factura)
            logs.append(log_llenado)
            if estado_llenado == ESTADO_OMITIDO_DUPLICADA:
                return ESTADO_OMITIDO_DUPLICADA, None, codigo_factura, "\n".join(logs)
            if estado_llenado != ESTADO_EXITO:
                raise Exception("El llenado de formulario de facturación falló.")

            _verificar_pagina_activa(page)

            # PASO 2: Subida de Archivos
            estado_subida, log_subida = subir_archivos_facturacion(page, documentos)
            logs.append(log_subida)
            if estado_subida != ESTADO_EXITO:
                raise Exception("La subida de archivos de facturación falló.")

            # PASO 3: Guardado de Confirmación (reutilizada de Glosas)
            pdf_path, radicado, log_confirmacion = guardar_confirmacion_previsora(page, subfolder_path)
            logs.append(log_confirmacion)
            if not radicado:
                 raise Exception("El guardado de confirmación de facturación falló.")

            return ESTADO_EXITO, radicado, codigo_factura, "\n".join(logs)

        except Exception as e:
            logs.append(f"ADVERTENCIA: Ocurrió un error en el intento #{attempt}: {e}")
            if attempt == MAX_ATTEMPTS:
                logs.append("ERROR: Se alcanzó el número máximo de reintentos.")
                try: page.screenshot(path=f"error_final_facturacion_{codigo_factura}.png")
                except: pass
    
    return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)