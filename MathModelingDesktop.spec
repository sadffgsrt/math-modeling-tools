# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['sklearn.ensemble', 'sklearn.linear_model', 'sklearn.cluster', 'sklearn.svm', 'sklearn.tree', 'statsmodels.tsa.arima.model', 'statsmodels.tsa.statespace', 'clr_loader', 'pythonnet']
hiddenimports += collect_submodules('modules')


a = Analysis(
    ['desktop_app.py'],
    pathex=[],
    binaries=[],
    datas=[('config', 'config')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'pytest', 'tensorflow', 'torch'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MathModelingDesktop',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MathModelingDesktop',
)
