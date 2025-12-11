# Core/trabajador_automatizacion.py - Refactorizado con Strategy Pattern

import os
import time
import traceback
from pathlib import Path
from PySide6 import QtCore
import json

from Core.fabrica_automatizaciones import FabricaAutomatizaciones
from Core.utilidades import consolidar_radicados_pdf
from .trabajador_email import EmailListenerWorker
from Configuracion.constantes import (
    MUNDIAL_ESCOLAR_ID,
    MUNDIAL_ESCOLAR_SEDE1_USER,
    MUNDIAL_ESCOLAR_SEDE1_PASS,
    MUNDIAL_ESCOLAR_SEDE2_USER,
    MUNDIAL_ESCOLAR_SEDE2_PASS
)


class TrabajadorAutomatizacion(QtCore.QObject):
    """
    Worker thread que ejecuta la automatización usando el patrón Strategy.
    Refactorizado para usar FabricaAutomatizaciones en lugar de imports directos.
    """
    
    progreso_update = QtCore.Signal(str)
    finalizado = QtCore.Signal(int, int, int, int, int)  # exitosos, fallos, omitidos, email_exitosos, email_fallos
    error_critico = QtCore.Signal(str)
    
    def __init__(self, area_id, aseguradora_id, carpeta_contenedora, modo_headless):
        super().__init__()
        self.area_id = area_id
        self.aseguradora_id = aseguradora_id
        self.carpeta_contenedora = Path(carpeta_contenedora)
        self.modo_headless = modo_headless
        
        # Resultados estructurados
        self.resultados_exitosos = []
        self.reporte_fallos = []  # Diccionarios estructurados
        self.reporte_omitidos = []  # Diccionarios estructurados
        self.email_final_failures = []
        
        # Email listener
        self.email_worker = None
        self.email_thread = None
    
    def handle_email_failures(self, failed_jobs):
        """Slot que recibe la lista de fallos definitivos del hilo de email."""
        self.email_final_failures = failed_jobs
    
    def _iniciar_email_listener_si_es_necesario(self):
        """Inicia el hilo de escucha de email solo para aseguradoras que lo requieren."""
        if self.aseguradora_id == MUNDIAL_ESCOLAR_ID:
            self.email_thread = QtCore.QThread()
            self.email_worker = EmailListenerWorker()
            self.email_worker.moveToThread(self.email_thread)
            
            self.email_thread.started.connect(self.email_worker.run)
            self.email_worker.finished.connect(self.email_thread.quit)
            self.email_worker.finished.connect(self.email_worker.deleteLater)
            self.email_thread.finished.connect(self.email_thread.deleteLater)
            self.email_worker.failures_final.connect(self.handle_email_failures)
            
            self.email_thread.start()
    
    def _formatear_tiempo(self, total_segundos: float) -> str:
        """Formatea segundos en un string legible (horas, minutos, segundos)."""
        horas = int(total_segundos // 3600)
        minutos = int((total_segundos % 3600) // 60)
        segundos = int(total_segundos % 60)
        
        if horas > 0:
            return f"{horas}h {minutos}m {segundos}s"
        elif minutos > 0:
            return f"{minutos}m {segundos}s"
        else:
            return f"{segundos}s"
    
    def run_automation(self):
        """
        Método principal que orquesta todo el proceso de automatización.
        Refactorizado para usar el patrón Strategy.
        """
        start_time = time.time()
        
        try:
            self.progreso_update.emit(f"=== Iniciando Automatización ===")
            self.progreso_update.emit(f"Área: {self.area_id}")
            self.progreso_update.emit(f"Aseguradora: {self.aseguradora_id}")
            self.progreso_update.emit(f"Carpeta: {self.carpeta_contenedora}")
            
            # Crear estrategia usando la fábrica
            estrategia = FabricaAutomatizaciones.crear_estrategia(self.aseguradora_id, self.area_id)
            
            if not estrategia:
                raise Exception(f"No se encontró estrategia para {self.aseguradora_id} en área {self.area_id}")
            
            self.progreso_update.emit(f"✓ Estrategia cargada: {estrategia.__class__.__name__}")
            
            # Ejecutar estrategia genérica
            self._ejecutar_estrategia_generica(estrategia)
            
        except Exception as e:
            self.error_critico.emit(f"ERROR CRÍTICO:\n{e}\n{traceback.format_exc()}")
        
        finally:
            total_time = time.time() - start_time
            tiempo_formateado = self._formatear_tiempo(total_time)
            
            exitosos = len(self.resultados_exitosos)
            fallos = len(self.reporte_fallos)
            omitidos = len(self.reporte_omitidos)
            
            summary = (
                f"\n{'='*50}\n"
                f"RESUMEN FINAL\n"
                f"{'='*50}\n"
                f"✓ Exitosos: {exitosos}\n"
                f"✗ Fallos: {fallos}\n"
                f"⊘ Omitidos: {omitidos}\n"
                f"⏱ Tiempo Total: {tiempo_formateado}\n"
                f"{'='*50}"
            )
            self.progreso_update.emit(summary)
            
            # CRÍTICO: Emitir reporte_fallos (diccionarios) NO resumen_fallos (strings)
            self.finalizado.emit(
                exitosos,
                fallos,
                omitidos,
                0,  # email_exitosos (legacy)
                0   # email_fallos (legacy)
            )
    
    def _ejecutar_estrategia_generica(self, estrategia):
        """
        Ejecuta una estrategia de automatización genérica.
        Compatible con cualquier EstrategiaAseguradora.
        """
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            # Configurar navegador
            browser = p.chromium.launch(headless=self.modo_headless)
            context = browser.new_context(viewport={'width': 1920, 'height': 1080})
            page = context.new_page()
            
            try:
                # Paso 1: Iniciar sesión
                self.progreso_update.emit("\n--- Iniciando Sesión ---")
                exito_login, log_login = estrategia.iniciar_sesion(page, None)
                self.progreso_update.emit(log_login)
                
                if not exito_login:
                    raise Exception("Fallo en inicio de sesión")
                
                # Paso 2: Navegar al formulario
                self.progreso_update.emit("\n--- Navegando al Formulario ---")
                exito_nav, log_nav = estrategia.navegar_a_formulario(page, None)
                self.progreso_update.emit(log_nav)
                
                if not exito_nav:
                    raise Exception("Fallo en navegación al formulario")
                
                # Paso 3: Procesar carpetas
                self.progreso_update.emit("\n--- Procesando Carpetas ---")
                carpetas = [d for d in self.carpeta_contenedora.iterdir() if d.is_dir()]
                total = len(carpetas)
                
                for idx, carpeta in enumerate(carpetas, 1):
                    self.progreso_update.emit(f"\n>>> Procesando {idx}/{total}: '{carpeta.name}'")
                    
                    glosa = {
                        'ruta_carpeta': carpeta,
                        'nombre_carpeta': carpeta.name,
                        'contexto': 'default'
                    }
                    
                    exito, log = estrategia.procesar_factura(page, None, glosa, self.carpeta_contenedora)
                    self.progreso_update.emit(log)
                    
                    # Clasificar resultado
                    if exito:
                        self.resultados_exitosos.append({
                            'referencia': glosa.get('factura_detectada', carpeta.name),
                            'radicado': glosa.get('radicado_obtenido', 'N/A'),
                            'ruta': str(carpeta)
                        })
                    else:
                        # Detectar si es omitido o fallo
                        if "OMITIDO" in log.upper() or "DUPLICADO" in log.upper() or "YA RADICADO" in log.upper():
                            self.reporte_omitidos.append({
                                'referencia': glosa.get('factura_detectada', carpeta.name),
                                'motivo': self._extraer_motivo_omision(log),
                                'ruta': str(carpeta),
                                'log': log
                            })
                        else:
                            self.reporte_fallos.append({
                                'referencia': glosa.get('factura_detectada', carpeta.name),
                                'error': self._extraer_error(log),
                                'ruta': str(carpeta),
                                'log': log
                            })
            
            finally:
                browser.close()
    
    def _extraer_motivo_omision(self, log: str) -> str:
        """Extrae el motivo de omisión del log."""
        log_upper = log.upper()
        if "DUPLICADO" in log_upper or "CAMPO BORRADO" in log_upper:
            return "Duplicado/Campo Borrado"
        elif "YA RADICADO" in log_upper or "RAD.PDF" in log_upper:
            return "Ya Radicado"
        elif "EXCLUIDA" in log_upper:
            return "Carpeta Excluida"
        else:
            return "Omitido"
    
    def _extraer_error(self, log: str) -> str:
        """Extrae el mensaje de error del log."""
        lines = log.split('\n')
        for line in reversed(lines):
            if "ERROR" in line.upper() or "FALLO" in line.upper():
                return line.strip()
        return "Error desconocido"
