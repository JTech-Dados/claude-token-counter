# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('F:/PTVPE/count_tokens/py/v4/ui.html', '.')]
binaries = []
hiddenimports = ['claude_usage', 'api', 'oauth', 'token_store', 'winpos', 'pystray._win32']
tmp_ret = collect_all('webview')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('clr_loader')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pythonnet')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['F:/PTVPE/count_tokens/py/v4/app.py'],
    pathex=['F:/PTVPE/count_tokens/py', 'F:/PTVPE/count_tokens/py/v4', 'F:/PTVPE/count_tokens/py/v5'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    a.binaries,
    a.datas,
    [],
    name='Contador de Tokens',
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
    version='F:\\PTVPE\\count_tokens\\packaging_v4\\version_info.txt',
    icon=['F:\\PTVPE\\count_tokens\\packaging_v4\\claude.ico'],
)
