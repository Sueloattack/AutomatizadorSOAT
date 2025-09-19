import sys
import os
from PySide6 import QtWidgets, QtGui

if __name__ == "__main__":
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