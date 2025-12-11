from typing import Tuple, Optional
from pathlib import Path
from playwright.sync_api import Page, FrameLocator

from Core.interfaces import EstrategiaAseguradora
from Core.utilidades import encontrar_y_validar_pdfs, guardar_screenshot_de_error
from Configuracion.constantes import *


class EstrategiaMundialEscolar(EstrategiaAseguradora):
    """
    Estrategia para automatización de Mundial Escolar (solo glosas).
    Implementa la interfaz EstrategiaAseguradora.
    """
    
    def iniciar_sesion(self, page: Page, contexto: Optional[FrameLocator]) -> Tuple[bool, str]:
        """Inicia sesión en Mundial Escolar."""
        logs = ["Iniciando sesión en Mundial Escolar..."]
        try:
            # Mundial Escolar usa lógica especial con API y email
            # Por ahora retornamos éxito para compatibilidad
            logs.append("  - Mundial Escolar usa flujo especial (API + Email)")
            return True, "\n".join(logs)
        except Exception as e:
            logs.append(f"ERROR: {e}")
            return False, "\n".join(logs)
    
    def navegar_a_formulario(self, page: Page, contexto: Optional[FrameLocator]) -> Tuple[bool, str]:
        """Mundial Escolar no requiere navegación tradicional."""
        return True, "Mundial Escolar: Navegación no requerida (usa API)"
    
    def procesar_factura(self, page: Page, contexto: Optional[FrameLocator], 
                        glosa: dict, carpeta_salida: Path) -> Tuple[bool, str]:
        """
        Procesa una factura de Mundial Escolar.
        Nota: Mundial Escolar usa un flujo especial con API y email listener.
        """
        # Importar la lógica legacy de Mundial Escolar
        from Automatizaciones.glosas import mundial_escolar
        
        subfolder_path = glosa.get('ruta_carpeta')
        subfolder_name = glosa.get('nombre_carpeta')
        
        if not subfolder_path:
            return False, "Error: Ruta de carpeta no proporcionada."
        
        try:
            # Usar la función legacy (Mundial Escolar tiene lógica compleja con API)
            estado, radicado, factura, logs = mundial_escolar.procesar_carpeta(
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
            return False, f"Error procesando Mundial Escolar: {e}"
