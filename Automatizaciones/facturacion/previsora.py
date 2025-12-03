# Automatizaciones/facturacion/previsora.py
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
    from Core.utilidades import encontrar_documentos_facturacion, guardar_screenshot_de_error
except ImportError:
    raise ImportError("ERROR CRITICO: No se pudieron importar módulos.")

from ..glosas.previsora import login, navegar_a_inicio, guardar_confirmacion_previsora, _verificar_pagina_activa

# Estados
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

# --- FUNCIONES ESPECIALIZADAS PARA FACTURACIÓN ---
def llenar_formulario_facturacion(page: Page, codigo_factura: str) -> tuple[str, str]:
    """
    Llena el formulario de Facturación con esperas dinámicas y manejo de errores robusto.
    NOTA: Ya no toma screenshots en caso de fallo, deja que el orquestador lo haga si es el último intento.
    """
    logs = [f"  Llenando formulario de Facturación (Factura: {codigo_factura})..."]
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
        # Esperar a que la opción aparezca (animación del dropdown)
        expect(opcion_ciudad).to_be_visible(timeout=5000)
        opcion_ciudad.click()
        logs.append("    - Ciudad OK.")

        # Llenado de campos de texto
        factura_input.fill(codigo_factura)
        # Disparar validación (Tab o click fuera)
        page.keyboard.press("Tab")
        
        # --- VERIFICACIÓN DE DUPLICADOS (LÓGICA REFINADA) ---
        # Esperamos un momento (1s) para que el sitio procese y muestre el popup si es necesario.
        page.wait_for_timeout(1000)

        popup_duplicado = page.locator("div.jconfirm-content:has-text('ya ha sido ingresada')")
        try:
            if popup_duplicado.is_visible(timeout=1000):
                logs.append("    -> DETECTADO POPUP: Aviso de factura ingresada.")
                # Usamos el selector estricto también aquí
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
        
        # Selección de Ramo (Select)
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

        # Completar resto del formulario
        page.locator(f"#{PREVISORA_ID_AMPAROS_FORM}").select_option(value=PREVISORA_VALUE_AMPARO_FORM)
        page.locator(f"#{PREVISORA_ID_TIPO_CUENTA_FORM}").select_option(value=PREVISORA_VALUE_TIPO_CUENTA_FACTURACION)
        logs.append("    - Amparos y Tipo de Cuenta OK.")
        
        return ESTADO_EXITO, "\n".join(logs)

    except Exception as e:
        error_msg = f"ERROR al llenar formulario: {e}"
        logs.append(error_msg)
        # No tomamos screenshot aquí para no llenar la carpeta de errores en reintentos.
        return ESTADO_FALLO, "\n".join(logs)

def subir_archivos_facturacion(page: Page, documentos: dict[str, Path]) -> tuple[str, str]:
    """Sube los archivos con validación de visibilidad."""
    logs = [f"  Subiendo archivos de facturación..."]
    try:
        # Asegurar que el input de archivo esté presente
        input_factura = page.locator(f"#{PREVISORA_ID_INPUT_FACTURA}")
        expect(input_factura).to_be_attached(timeout=10000)
        
        ruta_hc = documentos["hc"]
        
        # Subida de archivos
        page.locator(f"#{PREVISORA_ID_INPUT_FURIPS}").set_input_files(documentos["furips"])
        page.locator(f"#{PREVISORA_ID_INPUT_FACTURA}").set_input_files(documentos["factura"])
        page.locator(f"#{PREVISORA_ID_INPUT_HC}").set_input_files(ruta_hc)
        page.locator(f"#{PREVISORA_ID_INPUT_SOPORTES_HC}").set_input_files(ruta_hc)
        logs.append("    - Archivos seleccionados en los inputs.")

        # Manejar cualquier popup que bloquee el botón de enviar
        manejar_popups_intrusivos(page, logs)

        btn_enviar = page.locator(f"#{PREVISORA_ID_BOTON_ENVIAR_FACTURACION}")
        expect(btn_enviar).to_be_visible(timeout=5000)
        btn_enviar.click()
        logs.append("    - Clic en el botón 'Enviar'.")
        
        # Manejo del popup de confirmación "Sí, continuar"
        popup_si = page.locator(PREVISORA_XPATH_POPUP_ENVIO_SI_CONTINUAR)
        expect(popup_si).to_be_visible(timeout=15000)
        popup_si.click(no_wait_after=True)
        logs.append("    - Pop-up 'Sí, continuar' confirmado.")
        
        return ESTADO_EXITO, "\n".join(logs)

    except Exception as e:
        error_msg = f"ERROR al subir archivos: {e}"
        logs.append(error_msg)
        return ESTADO_FALLO, "\n".join(logs)

# --- ORQUESTADOR PRINCIPAL ---
def procesar_carpeta(page: Page, subfolder_path: Path, subfolder_name: str, context: str = 'default') -> tuple[str, str | None, str | None, str]:
    """
    Orquestador para Facturación con estrategia de reintento y limpieza de errores.
    """
    logs = [f"--- Iniciando FACTURACIÓN (Previsora) para: '{subfolder_name}' ---"]
    
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
            
            # --- VIGÍA DE ERROR DE CONECTIVIDAD ---
            # Antes de cualquier cosa, verificamos si estamos en la pantalla de error
            manejar_error_conectividad(page, logs)

            if attempt > 1:
                logs.append("   -> Fallo previo. Recargando página...")
                try:
                    page.reload(wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(2000) # Espera de estabilización
                    # Volvemos a chequear error de conectividad tras recarga
                    manejar_error_conectividad(page, logs)
                except Exception as e_reload:
                    logs.append(f"   -> Error al recargar: {e_reload}")

            # Verificar estado inicial
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
            
            # PASO 1: Llenado de Formulario
            estado_llenado, log_llenado = llenar_formulario_facturacion(page, codigo_factura)
            logs.append(log_llenado)
            
            if estado_llenado == ESTADO_OMITIDO_DUPLICADA:
                return ESTADO_OMITIDO_DUPLICADA, None, codigo_factura, "\n".join(logs)
            
            if estado_llenado != ESTADO_EXITO:
                raise Exception("Fallo en llenado de formulario.")

            # PASO 2: Subida de Archivos
            estado_subida, log_subida = subir_archivos_facturacion(page, documentos)
            logs.append(log_subida)
            if estado_subida != ESTADO_EXITO:
                raise Exception("Fallo en subida de archivos.")

            # PASO 3: Guardado de Confirmación
            # Nota: guardar_confirmacion_previsora ya tiene su propia lógica de espera y screenshot en error
            # pero como es compartida, si falla ahí, también queremos capturarlo.
            pdf_path, radicado, log_confirmacion = guardar_confirmacion_previsora(page, subfolder_path)
            logs.append(log_confirmacion)
            
            if not radicado:
                raise Exception("Fallo en guardado de confirmación.")

            return ESTADO_EXITO, radicado, codigo_factura, "\n".join(logs)

        except Exception as e:
            logs.append(f"ADVERTENCIA: Fallo en intento #{attempt}: {e}")
            
            # Solo tomar screenshot si es el ÚLTIMO intento
            if attempt == MAX_ATTEMPTS:
                logs.append("ERROR: Se agotaron los reintentos.")
                try:
                    screenshot_path = guardar_screenshot_de_error(page, f"error_final_facturacion_{codigo_factura}")
                    logs.append(f"Screenshot final guardado: {screenshot_path}")
                except:
                    pass
    
    return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)