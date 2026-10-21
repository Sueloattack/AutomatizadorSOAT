# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

# Localizar los componentes de Playwright instalados en la máquina
local_app_data = os.environ.get('LOCALAPPDATA', '')
ms_pw_dir = os.path.join(local_app_data, 'ms-playwright')

datas = [
    ('InterfazUsuario/dark_theme.qss', 'InterfazUsuario'),
    ('InterfazUsuario/light_theme.qss', 'InterfazUsuario'),
    ('Recursos/Icons/pingu.ico', 'Recursos/Icons'),
    ('Recursos/Icons/pingu.png', 'Recursos/Icons'),
]

# Incluir navegadores y componentes de Playwright requeridos para modo normal y segundo plano (headless)
pw_components = [
    'chromium-1181',
    'chromium_headless_shell-1181',
    'winldd-1007',
    'ffmpeg-1011'
]

for comp in pw_components:
    comp_path = os.path.join(ms_pw_dir, comp)
    if os.path.exists(comp_path):
        datas.append((comp_path, f'playwright/driver/package/.local-browsers/{comp}'))

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
