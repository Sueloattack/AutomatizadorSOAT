# AutomatizadorSOAT/main.py (versión final optimizada)
import sys
import os
from PySide6 import QtWidgets, QtCore, QtGui

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from InterfazUsuario.Ventana_principal import VentanaPrincipal
    from Core.utilidades import resource_path
except ImportError as e:
    app_temp = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    QtWidgets.QMessageBox.critical(None, "Error Crítico de Importación", f"No se pudo iniciar:\n{e}")
    sys.exit(1)

def _setup_global_icon(app):
    """
    Intenta encontrar y establecer el icono global de la aplicación.
    Busca en una lista de rutas priorizadas (.ico primero).
    """
    # Lista de posibles rutas para el icono, en orden de preferencia.
    icon_paths_to_try = [
        "Recursos/Icons/pingu.ico",
        "Recursos/Icons/pingu.png" # Corregida la ruta a mayúsculas como en tu estructura
    ]

    for relative_path in icon_paths_to_try:
        full_path = resource_path(relative_path)
        if os.path.exists(full_path):
            print(f"DEBUG: Intentando usar icono desde: {full_path}")
            global_icon = QtGui.QIcon(full_path)
            if not global_icon.isNull():
                app.setWindowIcon(global_icon)
                print(f"DEBUG: Icono global establecido con éxito.")
                return # Salimos de la función en cuanto encontramos uno válido
            else:
                print(f"ADVERTENCIA: El archivo {full_path} no es un icono válido.")

    print("ADVERTENCIA: No se pudo encontrar o establecer un icono de aplicación válido.")

def main():
    """Función principal para lanzar la aplicación."""
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    try:
        # Llamada única y limpia a nuestra nueva función.
        _setup_global_icon(app)
    except Exception as e:
        # Este `try/except` es una salvaguarda por si algo muy raro pasa.
        print(f"ADVERTENCIA: Falló el proceso de configuración del icono: {e}")

    try:
        window = VentanaPrincipal()
        window.show()
    except Exception as e_init:
        QtWidgets.QMessageBox.critical(None, "Error al Iniciar", f"No se pudo crear la ventana principal:\n{e_init}")
        sys.exit(1)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()