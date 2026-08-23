# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

added_files = [
    ('../resources', 'resources'),
]

# Collect customtkinter json assets and fonts
try:
    added_files += collect_data_files('customtkinter')
except Exception:
    pass

hidden_imports = [
    'customtkinter',
    'sqlalchemy',
    'sqlalchemy.sql.default_comparator',
    'sqlalchemy.ext.baked',
    'cryptography',
    'googleapiclient',
    'google_auth_oauthlib',
    'google.auth',
    'openai',
    'pydantic',
]

a = Analysis(
    ['../run.py'],
    pathex=['..'],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
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
    name='GmailAI Assistant',
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
