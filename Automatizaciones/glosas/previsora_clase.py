from typing import Tuple, Optional, Any
from pathlib import Path
import os
import re
import traceback
import time
import fitz # PyMuPDF
try:
    from PIL import Image
except ImportError:
    pass # Se manejará en runtime

from playwright.sync_api import Page, FrameLocator, expect, TimeoutError as PlaywrightTimeoutError

from Core.interfaces import EstrategiaAseguradora
from Core.utilidades import encontrar_y_validar_pdfs, guardar_screenshot_de_error
from Configuracion.constantes import *

# Constantes locales útiles (copiadas del original)
ESTADO_EXITO = "EXITO"
ESTADO_FALLO = "FALLO"
ESTADO_OMITIDO_RADICADO = "OMITIDO_RADICADO"
ESTADO_OMITIDO_DUPLICADA = "OMITIDO_DUPLICADA"


class EstrategiaPrevisoraGlosas(EstrategiaAseguradora):
    """
    Estrategia para automatización de Previsora en modo GLOSAS.
    Implementa la interfaz EstrategiaAseguradora con lógica robusta adaptada del script legacy.
    """
    
    def iniciar_sesion(self, page: Page, contexto: Optional[FrameLocator]) -> Tuple[bool, str]:
        """Inicia sesión en la plataforma de Previsora."""
        logs = ["Iniciando sesión en Previsora..."]
        try:
            page.goto(PREVISORA_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)
            
            # Seleccionar tipo de reclamante
            page.locator(f"#{PREVISORA_ID_TIPO_RECLAMANTE_LOGIN}").select_option(label=PREVISORA_TIPO_RECLAMANTE_LOGIN)
            
            # Ingresar documento
            page.locator(f"#{PREVISORA_ID_DOCUMENTO_LOGIN}").fill(PREVISORA_NO_DOCUMENTO_LOGIN)
            
            # Click en Iniciar Sesión
            page.locator(PREVISORA_XPATH_BOTON_LOGIN).click()
            
            # Manejar popup "Entendido" si aparece
            try:
                if page.locator(PREVISORA_XPATH_POPUP_LOGIN_ENTENDIDO).is_visible(timeout=3000):
                    page.locator(PREVISORA_XPATH_POPUP_LOGIN_ENTENDIDO).click()
                    logs.append("  - Popup 'Entendido' cerrado.")
            except:
                pass
            
            # Verificar que llegamos a la página correcta
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
            # Click en "Inicio" para ir al formulario
            page.locator(PREVISORA_XPATH_INICIO_LINK).click()
            
            # Esperar a que cargue el formulario
            page.wait_for_selector(f"#{PREVISORA_ID_ELEMENTO_CLAVE_FORMULARIO}", timeout=15000)
            page.wait_for_timeout(1500)
            
            logs.append("  - Formulario cargado correctamente.")
            return True, "\n".join(logs)
            
        except Exception as e:
            logs.append(f"ERROR navegando al formulario: {e}")
            return False, "\n".join(logs)
    
    def procesar_factura(self, page: Page, contexto: Optional[FrameLocator], glosa: dict, carpeta_salida: Path) -> Tuple[bool, str]:
        """
        Procesa una factura/glosa individual.
        Orquesta el flujo completo: validación, llenado, subida y confirmación.
        """
        subfolder_path = glosa.get('ruta_carpeta')
        subfolder_name = glosa.get('nombre_carpeta')
        context = glosa.get('contexto', 'default')  # 'default' o 'aceptadas'
        
        if not subfolder_path:
            return False, "Error: Ruta de carpeta no proporcionada."
        
        # Llamar al procesador interno
        estado, radicado, factura, logs = self._procesar_carpeta_interna(page, subfolder_path, subfolder_name, context)
        
        # Actualizar el diccionario glosa con los resultados
        if estado == ESTADO_EXITO:
            glosa['radicado_obtenido'] = radicado
            glosa['factura_detectada'] = factura
            return True, logs
        else:
            # Para omitidos y fallos, también guardamos info si está disponible
            if factura:
                glosa['factura_detectada'] = factura
            return False, logs
    
    def _procesar_carpeta_interna(self, page: Page, subfolder_path: Path, subfolder_name: str, context: str) -> Tuple[str, Optional[str], Optional[str], str]:
        logs = [f"--- Procesando carpeta: '{subfolder_name}' ---"]
        
        # Validaciones de exclusión
        if any(p in subfolder_name.upper() for p in PALABRAS_EXCLUSION_CARPETAS) or (subfolder_path / "RAD.pdf").is_file():
             return ESTADO_OMITIDO_RADICADO, None, None, "\n".join(logs) + "\nOMITIDO: Carpeta excluida o ya radicada."

        # 1. Encontrar archivos
        codigo_factura, pdf_path, pdf_log = encontrar_y_validar_pdfs(subfolder_path, subfolder_name, PREVISORA_NOMBRE_EN_PDF)
        logs.append(pdf_log)
        if not (codigo_factura and pdf_path):
             return ESTADO_FALLO, None, None, "\n".join(logs)

        # 2. Gestión de archivo (Compresión)
        try:
             pdf_path = self._gestionar_tamano_archivo(pdf_path, logs, codigo_factura)
             if not pdf_path: # Si devuelve None, falló la gestión
                 return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)
        except Exception as e:
             logs.append(f"Error gestionando archivo: {e}")
             return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)

        # 3. Ciclo de reintentos
        MAX_ATTEMPTS = 5
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                logs.append(f"\n--- Intento {attempt}/{MAX_ATTEMPTS} ---")
                
                self._manejar_error_conectividad(page, logs)
                
                if attempt > 1:
                     logs.append("   -> Recargando página por reintento...")
                     page.reload(timeout=45000); page.wait_for_timeout(3000)
                     self._manejar_error_conectividad(page, logs)

                # Verificar página
                if not page.locator(f"#{PREVISORA_ID_FACTURA_FORM}").is_visible(timeout=2000):
                     raise Exception("Formulario no visible al inicio del intento.")

                # Paso 1: Formulario
                estado_llenado, log_llenado = self._llenar_formulario(page, codigo_factura, context, logs)
                if estado_llenado != ESTADO_EXITO:
                     if estado_llenado == ESTADO_OMITIDO_DUPLICADA:
                          return ESTADO_OMITIDO_DUPLICADA, None, codigo_factura, "\n".join(logs) + "\n" + log_llenado
                     raise Exception(f"Fallo llenado: {log_llenado}")
                logs.append(log_llenado)

                # Paso 2: Subida
                estado_subida, log_subida = self._subir_archivo(page, pdf_path)
                logs.append(log_subida)
                if estado_subida != ESTADO_EXITO: raise Exception("Fallo subida archivo.")

                # Paso 3: Confirmación
                pdf_final, radicado, log_conf = self._guardar_confirmacion(page, subfolder_path)
                logs.append(log_conf)
                if not pdf_final: raise Exception("Fallo confirmación final.")

                return ESTADO_EXITO, radicado, codigo_factura, "\n".join(logs)
            
            except Exception as e:
                logs.append(f"ADVERTENCIA intento {attempt}: {e}")
                if attempt == MAX_ATTEMPTS:
                     guardar_screenshot_de_error(page, f"previsora_final_fail_{codigo_factura}")
        
        return ESTADO_FALLO, None, codigo_factura, "\n".join(logs)

    def _manejar_popups_intrusivos(self, page: Page, logs: list) -> bool:
        """Detecta y cierra popups intrusivos de manera persistente."""
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

    def _gestionar_tamano_archivo(self, pdf_path: Path, logs: list, codigo: str) -> Optional[Path]:
        """Lógica de compresión para archivos >20MB."""
        if pdf_path.stat().st_size <= PREVISORA_MAX_FILE_SIZE_BYTES:
            return pdf_path
            
        logs.append(f"Archivo grande ({pdf_path.stat().st_size} bytes). Intentando comprimir...")
        original = pdf_path.with_name(f"{pdf_path.stem}-original.pdf")
        if original.exists():
            logs.append("Ya existe backup (-original), no se recomprime para evitar bucles.")
            return None
        
        try:
            pdf_path.rename(original)
            with fitz.open(original) as doc:
                doc.save(str(pdf_path), garbage=4, deflate=True, clean=True)
            if pdf_path.stat().st_size > PREVISORA_MAX_FILE_SIZE_BYTES:
                 logs.append("Compresión insuficiente.")
                 return None
            return pdf_path
        except Exception as e:
            logs.append(f"Error compresión: {e}")
            if original.exists(): original.rename(pdf_path)
            return None

    def _llenar_formulario(self, page: Page, codigo_factura: str, context: str, logs_main: list) -> Tuple[str, str]:
        """Llena el formulario con validación de duplicados."""
        logs = [f"  Llenando formulario (Factura: {codigo_factura})..."]
        try:
            self._manejar_popups_intrusivos(page, logs)
            
            # Ciudad
            page.locator(f"//input[@id='{PREVISORA_ID_CIUDAD_HIDDEN_FORM}']/..").click()
            page.locator(PREVISORA_XPATH_CIUDAD_OPCION).click()
            logs.append(f"    - Ciudad '{PREVISORA_CIUDAD_FORM_NOMBRE}' seleccionada.")
            
            # Factura
            inp = page.locator(f"#{PREVISORA_ID_FACTURA_FORM}")
            inp.fill(codigo_factura)
            page.keyboard.press("Tab")
            page.wait_for_timeout(1500)
            self._manejar_popups_intrusivos(page, logs)
            
            if not inp.input_value():
                 logs.append("    -> Campo borrado por el sistema (Duplicado).")
                 return ESTADO_OMITIDO_DUPLICADA, "\n".join(logs)
            else:
                 logs.append("    - Campo factura llenado y validado.")

            page.locator(f"#{PREVISORA_ID_CORREO_FORM}").fill(PREVISORA_CORREO_FORM)
            page.locator(f"#{PREVISORA_ID_USUARIO_REGISTRA_FORM}").fill(PREVISORA_USUARIO_REGISTRA_FORM)
            page.locator(f"#{PREVISORA_ID_RAMO_FORM}").select_option(label=PREVISORA_RAMO_FORM)
            logs.append("    - Datos básicos (Correo, Usuario, Ramo) completados.")
            
            # Revisión final duplicado
            page.wait_for_timeout(500)
            self._manejar_popups_intrusivos(page, logs)
            if not inp.input_value(): return ESTADO_OMITIDO_DUPLICADA, "\n".join(logs)

            page.locator(f"#{PREVISORA_ID_AMPAROS_FORM}").select_option(value=PREVISORA_VALUE_AMPARO_FORM)
            
            val_cuenta = "5" if context == "aceptadas" else PREVISORA_VALUE_TIPO_CUENTA_FORM
            page.locator(f"#{PREVISORA_ID_TIPO_CUENTA_FORM}").select_option(value=val_cuenta)
            logs.append(f"    - Amparos y Tipo Cuenta ('{val_cuenta}') seleccionados.")
            
            return ESTADO_EXITO, "\n".join(logs)
        except Exception as e:
            return ESTADO_FALLO, f"\n".join(logs) + f"\nError llenando: {e}"

    def _subir_archivo(self, page: Page, pdf_path: Path) -> Tuple[str, str]:
        """Sube el archivo PDF."""
        logs = ["  Subiendo archivo PDF..."]
        try:
            page.locator(f"#{PREVISORA_ID_INPUT_FILE_FORM}").set_input_files(pdf_path)
            logs.append("    - PDF cargado en input.")
            
            self._manejar_popups_intrusivos(page, logs)
            page.locator(f"#{PREVISORA_ID_BOTON_ENVIAR_FORM}").click()
            logs.append("    - Click en botón Enviar.")
            
            # Confirmación post-envio
            if not self._manejar_popups_intrusivos(page, logs):
                 try: 
                     if page.locator(PREVISORA_XPATH_POPUP_ENVIO_SI_CONTINUAR).is_visible(timeout=3000):
                         page.locator(PREVISORA_XPATH_POPUP_ENVIO_SI_CONTINUAR).click()
                         logs.append("    - Confirmación 'Sí, continuar' clickeada.")
                 except: pass
            return ESTADO_EXITO, "\n".join(logs)
        except Exception as e:
            return ESTADO_FALLO, f"Error subida: {e}"

    def _guardar_confirmacion(self, page: Page, folder: Path) -> Tuple[Optional[Path], Optional[str], str]:
        """Maneja la confirmación final y extrae el radicado."""
        logs = ["  Manejando fase de confirmación final..."]
        try:
            page.wait_for_load_state("load", timeout=30000)
            popup_final = None
            found_path = False
            
            # Bucle de espera adaptativo (180 segundos = 3 minutos)
            for _ in range(180): 
                 # 1. Chequear Final (PRIORIDAD MAXIMA)
                 if page.locator(PREVISORA_XPATH_FINAL_CONFIRMATION_POPUP_CONTAINER).is_visible():
                     logs.append("    -> DETECTADO: El pop-up final 'Registro Generado' apareció.")
                     popup_final = page.locator(PREVISORA_XPATH_FINAL_CONFIRMATION_POPUP_CONTAINER)
                     found_path = True
                     break
                 
                 # 2. Chequear Intermedio
                 if page.locator(PREVISORA_XPATH_POPUP_CONTINUAR_GUARDAR).is_visible():
                     logs.append("    -> DETECTADO: Pop-up intermedio. Clic en 'Continuar y Guardar'.")
                     page.locator(PREVISORA_XPATH_POPUP_CONTINUAR_GUARDAR).click(no_wait_after=True)
                 
                 # 3. ELIMINADO: _manejar_popups_intrusivos
                 # Ya no limpiamos intrusivos aquí para evitar cerrar el modal de éxito si el selector falla o tarda.
                 # Es más seguro que se quede pegado 3 mins a que cierre el radicado.
                 
                 page.wait_for_timeout(1000)
            
            if not popup_final: return None, None, "Timeout esperando confirmación (3 min)."

            txt = popup_final.inner_text()
            rad = re.search(r"Tu codigo es:\s*'(\d+)'", txt, re.IGNORECASE)
            rad_val = rad.group(1) if rad else "N/A"
            logs.append(f"    - Código extraído: {rad_val}")
            
            # Screenshot
            tiem = time.strftime("%H%M%S")
            png = folder / f"temp_conf_{tiem}.png"
            pdf = folder / "RAD.pdf"
            popup_final.screenshot(path=png)
            logs.append("    - Screenshot tomado.")
            with Image.open(png) as img: img.convert("RGB").save(pdf)
            png.unlink()
            logs.append(f"    - PDF generado: {pdf.name}")
            
            # Reset
            page.locator(PREVISORA_XPATH_BOTON_NUEVA_RECLAMACION).click()
            expect(page.locator(f"#{PREVISORA_ID_FACTURA_FORM}")).to_be_enabled(timeout=20000)
            logs.append("    - Ciclo reiniciado 'Nueva Reclamación'.")
            
            return pdf, rad_val, "\n".join(logs)
        except Exception as e:
            return None, None, f"Error confirmación: {e} \nLogs: " + "\n".join(logs)
