# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_all

datas = [
    ('config.yaml', '.'),
]

if os.path.exists('.env'):
    datas.append(('.env', '.'))

# Collect all customtkinter assets (fonts, themes, binaries, hidden imports)
ctk_datas, ctk_binaries, ctk_hiddenimports = collect_all('customtkinter')

datas += ctk_datas
binaries = ctk_binaries
hiddenimports = ctk_hiddenimports + [
    'schedule', 
    'anthropic', 
    'praw', 
    'feedparser', 
    'yaml', 
    'pydantic', 
    'dotenv',
    'requests',
    'src.collectors.reddit_collector',
    'src.collectors.web_collector',
    'src.processors.filter',
    'src.processors.claude_synthesizer',
    'src.storage.memory_manager',
    'src.formatters.markdown_builder',
    'src.formatters.html_builder'
]

block_cipher = None

a = Analysis(
    ['gui.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name='TrailheadEngine',
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TrailheadEngine',
)
