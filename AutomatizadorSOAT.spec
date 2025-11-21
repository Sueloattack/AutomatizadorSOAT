# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=['Automatizaciones'],
    binaries=[],
    datas=[('InterfazUsuario/dark_theme.qss', 'InterfazUsuario'), ('InterfazUsuario/light_theme.qss', 'InterfazUsuario'), ('Recursos/Icons/pingu.ico', 'Recursos/Icons'), ('Recursos/Icons/pingu.png', 'Recursos/Icons')],
    hiddenimports=['PySide6', 'shiboken6', 'playwright', 'PySide6.QtWebEngineWidgets', 'Automatizaciones.glosas.previsora'],
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
