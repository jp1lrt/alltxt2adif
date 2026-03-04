# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for alltxt2adif_gui
# Usage: pyinstaller alltxt2adif_gui.spec

block_cipher = None

a = Analysis(
    ['alltxt2adif_gui.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('convert_all_to_adif.py', '.'),  # core script bundled alongside
        ('icon.ico', '.'),                # window icon
    ],
    hiddenimports=['PIL', 'PIL.Image', 'PIL.ImageTk'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='alltxt2adif',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,         # GUIアプリ: コンソール非表示
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)
