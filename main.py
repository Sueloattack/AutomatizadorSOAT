import sys
import os
import time
from pathlib import Path
from PySide6 import QtWidgets, QtGui

def limpiar_capturas_antiguas(dias_limite=10):
    """
    Revisa la carpeta 'Errores' y elimina capturas de pantalla que sean más
    antiguas que el límite de días especificado.
    """
    try:
        project_root = Path(__file__).resolve().parent
        error_dir = project_root / "Errores"
        
        if not error_dir.is_dir():
            # Si la carpeta no existe, no hay nada que hacer.
            return

        limite_tiempo = time.time() - (dias_limite * 24 * 60 * 60)
        
        print(f"--- Iniciando limpieza de capturas antiguas (límite: {dias_limite} días) ---")
        
        for item in error_dir.iterdir():
            if item.is_file() and "error_screenshot" in item.name:
                try:
                    if item.stat().st_mtime < limite_tiempo:
                        item.unlink()
                        print(f"  - Eliminado archivo antiguo: {item.name}")
                except Exception as e_file:
                    print(f"  - ERROR: No se pudo procesar o eliminar {item.name}: {e_file}")
        
        print("--- Limpieza finalizada ---")

    except Exception as e:
        # Imprimir el error pero no detener la ejecución de la app principal.
        print(f"ERROR CRÍTICO en la función de limpieza de capturas: {e}")


if __name__ == "__main__":
    # Limpiar capturas antiguas al iniciar la aplicación
    limpiar_capturas_antiguas()

    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    from InterfazUsuario.Ventana_principal import VentanaPrincipal
    from Core.utilidades import resource_path
        
    def _setup_global_icon(app):
        icon_paths_to_try = ["Recursos/Icons/pingu.ico", "Recursos/Icons/pingu.png"]
        for relative_path in icon_paths_to_try:
            full_path = resource_path(relative_path)
            if os.path.exists(full_path):
                global_icon = QtGui.QIcon(full_path)
                if not global_icon.isNull():
                    app.setWindowIcon(global_icon)
                    return

    app = QtWidgets.QApplication(sys.argv)
    _setup_global_icon(app)
    app.setQuitOnLastWindowClosed(False) 
    
    main_window = VentanaPrincipal()
    main_window.show()
    
    sys.exit(app.exec())
