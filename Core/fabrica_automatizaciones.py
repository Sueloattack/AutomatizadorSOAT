"""
Fábrica de Automatizaciones - Patrón Factory para Strategy Pattern.
Centraliza la creación de estrategias de automatización por aseguradora.
"""
from typing import Optional
from Core.interfaces import EstrategiaAseguradora
from Configuracion.constantes import (
    MUNDIAL_ESCOLAR_ID,
    PREVISORA_ID,
    AXA_SOAT_ID
)


class FabricaAutomatizaciones:
    """
    Fábrica que crea instancias de estrategias de automatización.
    
    Ventajas del patrón Factory:
    - Desacopla la creación de objetos del código cliente
    - Facilita agregar nuevas aseguradoras sin modificar código existente
    - Centraliza la lógica de selección de estrategia
    """
    
    @staticmethod
    def crear_estrategia(aseguradora_id: str, area_id: str) -> Optional[EstrategiaAseguradora]:
        """
        Crea y retorna la estrategia apropiada según la aseguradora y área.
        
        Args:
            aseguradora_id: ID de la aseguradora (ej: 'mundial_escolar', 'previsora', 'axa_soat')
            area_id: ID del área de negocio ('glosas' o 'facturacion')
            
        Returns:
            Instancia de EstrategiaAseguradora o None si no se encuentra
        """
        
        # Mundial Escolar (solo glosas)
        if aseguradora_id == MUNDIAL_ESCOLAR_ID and area_id == "glosas":
            from Automatizaciones.glosas.mundial_escolar_clase import EstrategiaMundialEscolar
            return EstrategiaMundialEscolar()
        
        # Previsora (glosas y facturación)
        elif aseguradora_id == PREVISORA_ID:
            if area_id == "glosas":
                from Automatizaciones.glosas.previsora_clase import EstrategiaPrevisoraGlosas
                return EstrategiaPrevisoraGlosas()
            elif area_id == "facturacion":
                from Automatizaciones.facturacion.previsora_clase import EstrategiaPrevisoraFacturacion
                return EstrategiaPrevisoraFacturacion()
        
        # AXA SOAT (glosas y facturación)
        elif aseguradora_id == AXA_SOAT_ID:
            if area_id == "glosas":
                from Automatizaciones.glosas.axa_soat_clase import EstrategiaAxaSoatGlosas
                return EstrategiaAxaSoatGlosas()
            elif area_id == "facturacion":
                from Automatizaciones.facturacion.axa_soat_clase import EstrategiaAxaSoatFacturacion
                return EstrategiaAxaSoatFacturacion()
        
        # Si no se encuentra, retornar None
        return None
    
    @staticmethod
    def estrategias_disponibles() -> dict:
        """
        Retorna un diccionario con todas las estrategias disponibles.
        
        Útil para debugging y validación.
        
        Returns:
            Dict con estructura: {aseguradora_id: [area_ids]}
        """
        return {
            MUNDIAL_ESCOLAR_ID: ["glosas"],
            PREVISORA_ID: ["glosas", "facturacion"],
            AXA_SOAT_ID: ["glosas", "facturacion"]
        }
