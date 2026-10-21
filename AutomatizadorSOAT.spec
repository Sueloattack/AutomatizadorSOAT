# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

# Localizar los navegadores de Playwright instalados en la máquina
local_app_data = os.environ.get('LOCALAPPDATA', '')
playwright_browsers_src = os.path.join(local_app_data, 'ms-playwright', 'chromium-1181')

datas = [
    ('InterfazUsuario/dark_theme.qss', 'InterfazUsuario'),
    ('InterfazUsuario/light_theme.qss', 'InterfazUsuario'),
    ('Recursos/Icons/pingu.ico', 'Recursos/Icons'),
    ('Recursos/Icons/pingu.png', 'Recursos/Icons'),
]

# Si existe la carpeta del navegador chromium-1181, incluirla empaquetada dentro de la estructura de Playwright
if os.path.exists(playwright_browsers_src):
    datas.append((playwright_browsers_src, 'playwright/driver/package/.local-browsers/chromium-1181'))

a = Analysis(
    ['main.py'],
    pathex=['Automatizaciones'],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'PySide6', 
        'shiboken6', 
        'playwright', 
        'PySide6.QtWebEngineWidgets', 
        'openpyxl',
        'requests',
        'Automatizaciones.glosas.previsora',
        'Automatizaciones.glosas.axa_soat',
        'Automatizaciones.glosas.mundial_soat',
        'Automatizaciones.glosas.mundial_escolar',
        'Automatizaciones.glosas.grupo_sis',
        'Automatizaciones.glosas.sura_arl',
        'Automatizaciones.facturacion.previsora',
        'Automatizaciones.facturacion.axa_soat'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AutomatizadorSOAT',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['Recursos\\Icons\\pingu.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AutomatizadorSOAT',
)
