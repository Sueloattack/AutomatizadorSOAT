"""
Interfaces base para el patrón Strategy en automatizaciones.
Define el contrato que todas las estrategias de aseguradoras deben cumplir.
"""
from abc import ABC, abstractmethod
from typing import Tuple, Optional
from pathlib import Path
from playwright.sync_api import Page, FrameLocator


class EstrategiaAseguradora(ABC):
    """
    Interfaz base para todas las estrategias de automatización de aseguradoras.
    
    Cada aseguradora debe implementar estos métodos para integrarse con el sistema.
    El patrón Strategy permite agregar nuevas aseguradoras sin modificar el código existente.
    """
    
    @abstractmethod
    def iniciar_sesion(self, page: Page, contexto: Optional[FrameLocator]) -> Tuple[bool, str]:
        """
        Inicia sesión en la plataforma de la aseguradora.
        
        Args:
            page: Página de Playwright para interactuar con el navegador
            contexto: Frame locator si la plataforma usa iframes (puede ser None)
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje_log)
        """
        pass
    
    @abstractmethod
    def navegar_a_formulario(self, page: Page, contexto: Optional[FrameLocator]) -> Tuple[bool, str]:
        """
        Navega al formulario de radicación/carga de documentos.
        
        Args:
            page: Página de Playwright
            contexto: Frame locator si aplica
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje_log)
        """
        pass
    
    @abstractmethod
    def procesar_factura(self, page: Page, contexto: Optional[FrameLocator], 
                        glosa: dict, carpeta_salida: Path) -> Tuple[bool, str]:
        """
        Procesa una factura/glosa individual.
        
        Este es el método principal que orquesta todo el flujo de radicación:
        - Validación de archivos
        - Llenado de formulario
        - Subida de documentos
        - Confirmación y extracción de radicado
        
        Args:
            page: Página de Playwright
            contexto: Frame locator si aplica
            glosa: Diccionario con información de la factura/glosa
                   Debe contener al menos: 'ruta_carpeta', 'nombre_carpeta'
                   Puede actualizarse con: 'radicado_obtenido', 'factura_detectada'
            carpeta_salida: Path a la carpeta de salida (puede no usarse en todas las estrategias)
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje_log_detallado)
        """
        pass
