# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for VideoMatrix with WebEngine bundled."""

import os
import sys
import glob

# Find PyQt6 installation path
import PyQt6
pyqt6_dir = os.path.dirname(PyQt6.__file__)
qt6_dir = os.path.join(pyqt6_dir, 'Qt6')

# Collect WebEngine binaries and data
added_files = []
added_binaries = []

# Qt6 binaries (DLLs)
qt6_bin = os.path.join(qt6_dir, 'bin')
if os.path.isdir(qt6_bin):
    for f in glob.glob(os.path.join(qt6_bin, '*')):
        if os.path.isfile(f):
            added_binaries.append((f, os.path.join('PyQt6', 'Qt6', 'bin')))

# Qt6 libraries
qt6_lib = os.path.join(qt6_dir, 'lib')
if os.path.isdir(qt6_lib):
    for f in glob.glob(os.path.join(qt6_lib, '*.dll')):
        added_binaries.append((f, os.path.join('PyQt6', 'Qt6', 'lib')))

# Qt6 resources (icudtl.dat, *.pak, etc.)
qt6_resources = os.path.join(qt6_dir, 'resources')
if os.path.isdir(qt6_resources):
    for f in glob.glob(os.path.join(qt6_resources, '*')):
        if os.path.isfile(f):
            added_files.append((f, os.path.join('PyQt6', 'Qt6', 'resources')))

# Qt6 translations
qt6_trans = os.path.join(qt6_dir, 'translations')
if os.path.isdir(qt6_trans):
    for f in glob.glob(os.path.join(qt6_trans, '*')):
        if os.path.isfile(f):
            added_files.append((f, os.path.join('PyQt6', 'Qt6', 'translations')))

# Qt6 plugins (platforms, imageformats, etc.)
qt6_plugins = os.path.join(qt6_dir, 'plugins')
if os.path.isdir(qt6_plugins):
    for dirpath, dirnames, filenames in os.walk(qt6_plugins):
        for f in filenames:
            src = os.path.join(dirpath, f)
            rel = os.path.relpath(dirpath, qt6_dir)
            dst = os.path.join('PyQt6', 'Qt6', rel)
            added_binaries.append((src, dst))

print(f"Collected {len(added_files)} data files, {len(added_binaries)} binaries")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=added_binaries,
    datas=added_files,
    hiddenimports=[
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebEngineCore',
        'PyQt6.QtWebEngineQuick',
    ],
    excludes=[
        'PyQt6.Qt3D', 'PyQt6.QtMultimedia', 'PyQt6.QtBluetooth',
        'PyQt6.QtNfc', 'PyQt6.QtPositioning', 'PyQt6.QtQuick',
        'PyQt6.QtQml', 'PyQt6.QtRemoteObjects', 'PyQt6.QtSensors',
        'PyQt6.QtSerialPort', 'PyQt6.QtSvg', 'PyQt6.QtTest',
        'PyQt6.QtHelp', 'PyQt6.QtDesigner', 'PyQt6.QtShaderTools',
        'PyQt6.QtSpatialAudio', 'PyQt6.QtHttpServer', 'PyQt6.QtPdf',
        'PyQt6.QtStateMachine', 'PyQt6.QtUiTools',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VideoMatrix',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
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
    name='VideoMatrix',
)
