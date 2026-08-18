# PyInstaller spec for the ARKlight Installer.
#
# Produces a single standalone executable that bundles its own Python
# interpreter, so the installer runs on a machine that has no system Python
# at all. Built via: pyinstaller installer/gui/arklight_installer.spec
#
# This is deliberately the *same* spec file referenced by every platform's
# packaging step (installer/linux, installer/windows, installer/macos);
# only the surrounding archive format (.deb/.rpm/AppImage vs .exe vs .app)
# differs per OS.

# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['arklight_installer/__main__.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=['tkinter'],
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
    name='arklight-installer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
