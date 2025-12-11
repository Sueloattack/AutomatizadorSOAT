from typing import Tuple, Optional, Any
from pathlib import Path
import os
import re
import traceback
import time
try:
    from PIL import Image
except ImportError:
    pass

from playwright.sync_api import Page, FrameLocator, expect, TimeoutError as PlaywrightTimeoutError

from Core.interfaces import EstrategiaAseguradora
from Core.utilidades import encontrar_documentos_facturacion, guardar_screenshot_de_error
from Configuracion.constantes import *

# Estados
ESTADO_EXITO = "EXITO"
ESTADO_FALLO = "FALLO"
ESTADO_OMITIDO_RADICADO = "OMITIDO_RADICADO"
ESTADO_OMITIDO_DUPLICADA = "OMITIDO_DUPLICADA"


class EstrategiaPrevisoraFacturacion(EstrategiaAseguradora):
    """
    Estrategia para automatización de Previsora en modo FACTURACIÓN.
    Implementa la interfaz EstrategiaAseguradora con lógica adaptada del script legacy.
    """
    
    def iniciar_sesion(self, page: Page, contexto: Optional[FrameLocator]) -> Tuple[bool, str]:
        """Inicia sesión en la plataforma de Previsora."""
        logs = ["Iniciando sesión en Previsora (Facturación)..."]
        try:
            page.goto(PREVISORA_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)
            
            page.locator(f"#{PREVISORA_ID_TIPO_RECLAMANTE_LOGIN}").select_option(label=PREVISORA_TIPO_RECLAMANTE_LOGIN)
            page.locator(f"#{PREVISORA_ID_DOCUMENTO_LOGIN}").fill(PREVISORA_NO_DOCUMENTO_LOGIN)
            page.locator(PREVISORA_XPATH_BOTON_LOGIN).click()
            
            try:
                if page.locator(PREVISORA_XPATH_POPUP_LOGIN_ENTENDIDO).is_visible(timeout=3000):
                    page.locator(PREVISORA_XPATH_POPUP_LOGIN_ENTENDIDO).click()
                    logs.append("  - Popup 'Entendido' cerrado.")
            except: pass
            
            page.wait_for_timeout(2000)
            logs.append("  - Sesión iniciada correctamente.")
            return True, "\n".join(logs)
            
        except Exception as e:
            logs.append(f"ERROR en inicio de sesión: {e}")
            return False, "\n".join(logs)
    
    def navegar_a_formulario(self, page: Page, contexto: Optional[FrameLocator]) -> Tuple[bool, str]:
        """Navega al formulario de radicación."""
        logs = ["Navegando al formulario..."]
        try:
            page.locator(PREVISORA_XPATH_INICIO_LINK).click()
            page.wait_for_selector(f"#{PREVISORA_ID_ELEMENTO_CLAVE_FORMULARIO}", timeout=15000)
            page.wait_for_timeout(1500)
            
            logs.append("  - Formulario cargado correctamente.")
            return True, "\n".join(logs)
            
        except Exception as e:
            logs.append(f"ERROR navegando al formulario: {e}")
            return False, "\n".join(logs)
    
    def procesar_factura(self, page: Page, contexto: Optional[FrameLocator], glosa: dict, carpeta_salida: Path) -> Tuple[bool, str]:
        """Procesa una factura individual."""
        subfolder_path = glosa.get('ruta_carpeta')
        subfolder_name = glosa.get('nombre_carpeta')
        
        if not subfolder_path: return False, "Error: Ruta de carpeta no proporcionada."

        estado, radicado, factura, logs = self._procesar_carpeta_interna(page, subfolder_path, subfolder_name)
        
        if estado == ESTADO_EXITO:
            glosa['radicado_obtenido'] = radicado
            glosa['factura_detectada'] = factura
            return True, logs
        else:
            return False, logs

    def _procesar_carpeta_interna(self, page: Page, subfolder_path: Path, subfolder_name: str) -> Tuple[str, Optional[str], Optional[str], str]:
        logs = [f"--- Procesando facturación: '{subfolder_name}' ---"]

        if any(p in subfolder_name.upper() for p in PALABRAS_EXCLUSION_CARPETAS) or (subfolder_path / "RAD.pdf").is_file():
             return ESTADO_OMITIDO_RADICADO, None, None, "\n".join(logs) + "\nOMITIDO."

        # 1. Encontrar documentos (lógica diferente a glosas)
        codigo_factura, documentos, docs_log = encontrar_documentos_facturacion(subfolder_path, subfolder_name)
        logs.append(docs_log)
        if not (codigo_factura and documentos):
             return ESTADO_FALLO, None, None, "\n".join(logs)

        # 2. Ciclo de intentos
        MAX_ATTEMPTS = 3
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                logs.append(f"\n--- Intento {attempt}/{MAX_ATTEMPTS} ---")
                self._manejar_error_conectividad(page, logs)
                
                if attempt > 1:
                     page.reload(timeout=45000); page.wait_for_timeout(2000)
                     self._manejar_error_conectividad(page, logs)

                # Paso 1: Formulario
                estado_llenado, log_llenado = self._llenar_formulario(page, codigo_factura, logs)
                logs.append(log_llenado)
                if estado_llenado != ESTADO_EXITO: 
                     if estado_llenado == ESTADO_OMITIDO_DUPLICADA: return ESTADO_OMITIDO_DUPLICADA, None, codigo_factura, "\n".join(logs)
                     raise Exception("Fallo llenado.")

                # Paso 2: Subida (Múltiples archivos)
                estado_subida, log_subida = self._subir_archivos(page, documentos)
                logs.append(log_subida)
                if estado_subida != ESTADO_EXITO: raise Exception("Fallo subida.")

                # Paso 3: Confirmación
                pdf_path, radicado, log_conf = self._guardar_confirmacion(page, subfolder_path)
                logs.append(log_conf)
                if not radicado: raise Exception("Fallo confirmación.")

                return ESTADO_EXITO, radicado, codigo_factura, "\n".join(logs)

            except Exception as e:
                logs.append(f"ADVERTENCIA intento {attempt}: {e}")
                if attempt == MAX_ATTEMPTS:
                    guardar_screenshot_de_error(page, f"previsora_fact_final_fail_{codigo_factura}")
        
        return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)

    def _manejar_popups_intrusivos(self, page: Page, logs: list) -> bool:
        """Detecta y cierra popups intrusivos."""
        selectores = [
            "button:has-text('Aceptar')", "button:has-text('Cerrar')", "button:has-text('Entendido')",
            "button:text-is('CONTINUAR')", "button:has-text('Sí, continuar')", "button:has-text('Si, continuar')",
            PREVISORA_XPATH_POPUP_FACTURA_CONTINUAR, "div.ui-dialog-buttonset button",
            "button.btn.btn-success:has-text('Continuar')", "button.btn-confirm", 
            # EXCLUIMOS explícitamente el botón de éxito para que no se cierre por error
            "div.jconfirm-box button.btn-green:not(:has-text('Generar una nueva reclamación'))"
        ]
        accion = False
        for _ in range(5):
            encontro = False
            for sel in selectores:
                try:
                    if page.locator(sel).is_visible(timeout=300):
                        page.locator(sel).click(force=True, timeout=1000)
                        logs.append(f"    [POPUP] Cerrado: {sel}")
                        encontro = True
                        accion = True
                        page.wait_for_timeout(800)
                        break
                except: pass
            if not encontro: break
        return accion

    def _manejar_error_conectividad(self, page: Page, logs: list) -> bool:
        """Detecta y maneja errores de conectividad."""
        try:
            if "ERROR DE CONECTIVIDAD" in page.content():
                logs.append("    [ERROR] Detectado error de conectividad. Recargando...")
                page.reload(timeout=60000)
                page.wait_for_timeout(3000)
                return True
        except: pass
        return False

    def _llenar_formulario(self, page: Page, codigo: str, logs_main: list) -> Tuple[str, str]:
        """Llena el formulario de facturación."""
        logs = []
        try:
            self._manejar_popups_intrusivos(page, logs)
            
            # Ciudad
            page.locator(f"//input[@id='{PREVISORA_ID_CIUDAD_HIDDEN_FORM}']/..").click()
            page.locator(PREVISORA_XPATH_CIUDAD_OPCION).click()
            logs.append(f"    - Ciudad '{PREVISORA_CIUDAD_FORM_NOMBRE}' seleccionada.")
            
            # Factura
            inp = page.locator(f"#{PREVISORA_ID_FACTURA_FORM}")
            inp.fill(codigo)
            page.keyboard.press("Tab")
            page.wait_for_timeout(1500)
            self._manejar_popups_intrusivos(page, logs)
            
            if not inp.input_value():
                 logs.append("    -> Campo borrado (Duplicado).")
                 return ESTADO_OMITIDO_DUPLICADA, "\n".join(logs)
            else:
                 logs.append("    - Campo factura llenado.")
            
            page.locator(f"#{PREVISORA_ID_CORREO_FORM}").fill(PREVISORA_CORREO_FORM)
            page.locator(f"#{PREVISORA_ID_USUARIO_REGISTRA_FORM}").fill(PREVISORA_USUARIO_REGISTRA_FORM)
            page.locator(f"#{PREVISORA_ID_RAMO_FORM}").select_option(label=PREVISORA_RAMO_FORM) 
            logs.append("    - Campos adicionales completados.")
             
            # Revisión final
            self._manejar_popups_intrusivos(page, logs)
            if not inp.input_value(): return ESTADO_OMITIDO_DUPLICADA, "\n".join(logs)

            page.locator(f"#{PREVISORA_ID_AMPAROS_FORM}").select_option(value=PREVISORA_VALUE_AMPARO_FORM)
            
            # TIPO CUENTA: Aquí cambia respecto a Glosas (se usa 13=FACTURACION generalmente, ajustado por constante)
            page.locator(f"#{PREVISORA_ID_TIPO_CUENTA_FORM}").select_option(value=PREVISORA_VALUE_TIPO_CUENTA_FACTURACION)
            logs.append("    - Amparos y Tipo Cuenta seleccionados.")

            return ESTADO_EXITO, "\n".join(logs)
        except Exception as e:
            return ESTADO_FALLO, f"Error llenando: {e}"

    def _subir_archivos(self, page: Page, documentos: dict) -> Tuple[str, str]:
        """Sube múltiples archivos (FURIPS, Factura, HC)."""
        logs = ["  Subiendo archivos Múltiples..."]
        try:
            page.locator(f"#{PREVISORA_ID_INPUT_FURIPS}").set_input_files(documentos["furips"])
            page.locator(f"#{PREVISORA_ID_INPUT_FACTURA}").set_input_files(documentos["factura"])
            page.locator(f"#{PREVISORA_ID_INPUT_HC}").set_input_files(documentos["hc"])
            page.locator(f"#{PREVISORA_ID_INPUT_SOPORTES_HC}").set_input_files(documentos["hc"])
            logs.append("    - Archivos (FURIPS, Factura, HC) cargados en inputs.")
            
            self._manejar_popups_intrusivos(page, logs)
            page.locator(f"#{PREVISORA_ID_BOTON_ENVIAR_FACTURACION}").click()
            logs.append("    - Click en botón Enviar.")
            
            self._manejar_popups_intrusivos(page, logs)
            try: 
                 if page.locator(PREVISORA_XPATH_POPUP_ENVIO_SI_CONTINUAR).is_visible(timeout=3000):
                     page.locator(PREVISORA_XPATH_POPUP_ENVIO_SI_CONTINUAR).click()
                     logs.append("    - Confirmación 'Sí, continuar' clickeada.")
            except: pass
            
            return ESTADO_EXITO, "\n".join(logs)
        except Exception as e:
            return ESTADO_FALLO, f"Error subida: {e}"

    def _guardar_confirmacion(self, page: Page, folder: Path) -> Tuple[Optional[Path], Optional[str], str]:
        """Maneja la confirmación final."""
        logs = ["  Manejando confirmación..."]
        try:
            page.wait_for_load_state("load", timeout=30000)
            popup_final = None
            found_path = False
            
            # Bucle de espera adaptativo (180 segundos = 3 minutos)
            for _ in range(180):
                 # 1. Chequear Final (PRIORIDAD MAXIMA)
                 if page.locator(PREVISORA_XPATH_FINAL_CONFIRMATION_POPUP_CONTAINER).is_visible():
                     logs.append("    -> DETECTADO: El pop-up final apareció.")
                     popup_final = page.locator(PREVISORA_XPATH_FINAL_CONFIRMATION_POPUP_CONTAINER)
                     found_path = True
                     break
                 
                 # 2. Chequear Intermedio
                 if page.locator(PREVISORA_XPATH_POPUP_CONTINUAR_GUARDAR).is_visible():
                     logs.append("    -> DETECTADO: Pop-up intermedio. Click 'Continuar y Guardar'.")
                     page.locator(PREVISORA_XPATH_POPUP_CONTINUAR_GUARDAR).click(no_wait_after=True)
                 
                 # 3. ELIMINADO: Cleaner intrusivo
                 
                 page.wait_for_timeout(1000)
            
            if not popup_final: return None, None, "Timeout esperando confirmación (3 min)."

            txt = popup_final.inner_text()
            rad = re.search(r"Tu codigo es:\s*'(\d+)'", txt, re.IGNORECASE)
            rad_val = rad.group(1) if rad else "N/A"
            logs.append(f"    - Código extraído: {rad_val}")
            
            tiem = time.strftime("%H%M%S")
            png = folder / f"temp_conf_{tiem}.png"
            pdf = folder / "RAD.pdf"
            popup_final.screenshot(path=png)
            with Image.open(png) as img: img.convert("RGB").save(pdf)
            png.unlink()
            logs.append(f"    - PDF generado: {pdf.name}")
            
            page.locator(PREVISORA_XPATH_BOTON_NUEVA_RECLAMACION).click()
            try:
                expect(page.locator(f"#{PREVISORA_ID_FACTURA_FORM}")).to_be_enabled(timeout=20000)
                logs.append("    - Reset exitoso (Nueva Reclamación).")
            except: pass
            
            return pdf, rad_val, "\n".join(logs)
        except Exception as e:
            return None, None, f"Error save: {e} \nLogs: " + "\n".join(logs)
