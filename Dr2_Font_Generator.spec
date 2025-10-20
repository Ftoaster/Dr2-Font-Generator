# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

# 아이콘 경로 설정 (SPECPATH는 spec 파일이 있는 디렉토리)
icon_path = os.path.join(SPECPATH, 'icon.ico')

a = Analysis(
    ['Dr2 Font Generator.py'],
    pathex=[],
    binaries=[
        ('msdf-atlas-gen.exe', '.'),
        ('texconv.exe', '.'),
    ],
    datas=[
        ('original_texture', 'original_texture'),
        ('separated_libraries_raw', 'separated_libraries_raw'),
        ('json_to_xml.py', '.'),
        ('l_merge_libraries.py', '.'),
        ('coordinate_comparator.py', '.'),
        ('icon.ico', '.'),  # 창 아이콘용
    ],
    hiddenimports=[],
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
    name='Dr2 Font Generator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI 프로그램이므로 콘솔 숨김
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,  # 프로그램 아이콘
)

