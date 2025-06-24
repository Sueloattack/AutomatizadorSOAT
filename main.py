# AutomatizadorSOAT/main.py
import sys
import os

# Añadir ruta al sys.path (útil para PyInstaller y ejecución normal)
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- AÑADIR QtGui A LAS IMPORTACIONES ---
from PySide6 import QtWidgets, QtCore, QtGui  # <--- Añadir QtGui aquí

# -----------------------------------------

# Importar la clase de la ventana principal
# Asegúrate que la ruta/nombre de carpeta sea correcto
try:
    from InterfazUsuario.Ventana_principal import VentanaPrincipal
    from Core.utilidades import resource_path  # Importar para icono global
except ImportError as e:
    # Mostrar error si falla la importación inicial
    app_temp = QtWidgets.QApplication.instance()
    if app_temp is None:
        app_temp = QtWidgets.QApplication(sys.argv)
    QtWidgets.QMessageBox.critical(
        None, "Error Crítico de Importación", f"No se pudo iniciar:\n{e}"
    )
    sys.exit(1)


def main():
    """Función principal para lanzar la aplicación."""
    app = QtWidgets.QApplication(sys.argv)

    # --- NO CERRAR AL OCULTAR VENTANA ---
    app.setQuitOnLastWindowClosed(False)
    # ------------------------------------

    # --- Establecer Icono Global (Intento) ---
    global_icon = None
    try:
        icon_path_ico = resource_path(
            "Recursos/Icons/pingu.ico"
        )  # INTENTA CON .ICO PRIMERO
        if os.path.exists(icon_path_ico):
            # AHORA QtGui.QIcon FUNCIONARÁ
            global_icon = QtGui.QIcon(icon_path_ico)
            print(f"DEBUG: Usando icono global desde: {icon_path_ico}")
        else:
            print(f"DEBUG: No se encontró {icon_path_ico}, intentando .png...")
            icon_path_png = resource_path("recursos/iconos/pingu.png")
            if os.path.exists(icon_path_png):
                # AHORA QtGui.QIcon FUNCIONARÁ
                global_icon = QtGui.QIcon(icon_path_png)
                print(f"DEBUG: Usando icono global desde: {icon_path_png}")
            else:
                print(
                    f"ADVERTENCIA: No se encontró archivo de icono en {icon_path_ico} ni {icon_path_png}"
                )

        if global_icon and not global_icon.isNull():
            app.setWindowIcon(global_icon)
        else:
            print("ADVERTENCIA: No se pudo establecer icono global.")

    except Exception as e:
        print(f"ADVERTENCIA: Error estableciendo icono global: {e}")
    # -------------------------------------------

    # Crear y mostrar la ventana principal
    try:
        window = VentanaPrincipal()
        window.show()
    except Exception as e_init:
        QtWidgets.QMessageBox.critical(
            None,
            "Error al Iniciar",
            f"No se pudo crear la ventana principal:\n{e_init}",
        )
        sys.exit(1)

    # Iniciar el bucle de eventos
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
