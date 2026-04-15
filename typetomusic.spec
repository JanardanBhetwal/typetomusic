# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for TypeToMusic
# Build with: pyinstaller typetomusic.spec

import os
import sys

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[
        # Include libfluidsynth shared library if present
        ('/usr/lib/x86_64-linux-gnu/libfluidsynth.so.3', '.'),
    ],
    datas=[
        # Bundle the default SoundFont if it exists
        ('/usr/share/sounds/sf2/FluidR3_GM.sf2',   'assets/soundfonts/'),
        ('/usr/share/soundfonts/FluidR3_GM.sf2',    'assets/soundfonts/'),
    ],
    hiddenimports=[
        'PyQt5.sip',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'pynput.keyboard._xorg',
        'pynput.mouse._xorg',
        'fluidsynth',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Remove SoundFont paths that don't exist on the build machine
a.datas = [(dest, src, typ) for dest, src, typ in a.datas
           if not src.startswith('/usr/share') or os.path.isfile(src)]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='typetomusic',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,       # No terminal window
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TypeToMusic',
)
