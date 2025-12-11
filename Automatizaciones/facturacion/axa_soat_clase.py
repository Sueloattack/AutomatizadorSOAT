from typing import Tuple, Optional
from pathlib import Path
from playwright.sync_api import Page, FrameLocator

from Core.interfaces import EstrategiaAseguradora
from Automatizaciones.facturacion import axa_soat


class EstrategiaAxaSoatFacturacion(EstrategiaAseguradora):
    """
    Estrategia para automatización de AXA SOAT en modo FACTURACIÓN.
    Wrapper sobre la lógica legacy de axa_soat.py
    """
    
    def iniciar_sesion(self, page: Page, contexto: Optional[FrameLocator]) -> Tuple[bool, str]:
        """Inicia sesión en AXA SOAT."""
        try:
            exito, log = axa_soat.iniciar_sesion_axa(page)
            return exito, log
        except Exception as e:
            return False, f"Error en inicio de sesión AXA: {e}"
    
    def navegar_a_formulario(self, page: Page, contexto: Optional[FrameLocator]) -> Tuple[bool, str]:
        """Navega al formulario de AXA SOAT."""
        try:
            exito, log = axa_soat.navegar_a_formulario_axa(page)
            return exito, log
        except Exception as e:
            return False, f"Error navegando al formulario AXA: {e}"
    
    def procesar_factura(self, page: Page, contexto: Optional[FrameLocator], 
                        glosa: dict, carpeta_salida: Path) -> Tuple[bool, str]:
        """Procesa una factura de AXA SOAT (facturación)."""
        subfolder_path = glosa.get('ruta_carpeta')
        subfolder_name = glosa.get('nombre_carpeta')
        
        if not subfolder_path:
            return False, "Error: Ruta de carpeta no proporcionada."
        
        try:
            estado, radicado, factura, logs = axa_soat.procesar_carpeta(
                page, subfolder_path, subfolder_name
            )
            
            if estado == "EXITO":
                glosa['radicado_obtenido'] = radicado
                glosa['factura_detectada'] = factura
                return True, logs
            else:
                if factura:
                    glosa['factura_detectada'] = factura
                return False, logs
                
        except Exception as e:
            return False, f"Error procesando AXA SOAT Facturación: {e}"
