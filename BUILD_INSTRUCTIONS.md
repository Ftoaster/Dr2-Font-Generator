# Dr2 Font Generator - EXE 빌드 가이드

## 🔧 준비사항

1. PyInstaller 설치:
```bash
pip install pyinstaller pillow
```

## 📦 빌드 방법

### 방법 1: Spec 파일 사용 (추천)
```bash
pyinstaller Dr2_Font_Generator.spec
```

### 방법 2: 명령줄에서 직접 빌드
```bash
pyinstaller --onefile --windowed ^
  --name "Dr2 Font Generator" ^
  --add-binary "msdf-atlas-gen.exe;." ^
  --add-binary "texconv.exe;." ^
  --add-data "original_texture;original_texture" ^
  --add-data "separated_libraries_raw;separated_libraries_raw" ^
  --add-data "json_to_pssg.py;." ^
  --add-data "l_merge_libraries.py;." ^
  --add-data "coordinate_comparator.py;." ^
  "Dr2 Font Generator.py"
```

## ⚠️ 중요 사항

### Subprocess 문제
현재 코드는 `subprocess`로 Python 스크립트를 실행합니다.
EXE에서는 이 방식이 작동하지 않을 수 있습니다.

**해결 방법:**
- `--onedir` 모드로 빌드 (폴더 형태)
- 또는 코드 수정 필요 (subprocess → 직접 import)

## 📁 최종 구조

빌드 후:
```
dist/
└── Dr2 Font Generator.exe  (또는 폴더)

사용자 폴더:
├── Dr2 Font Generator.exe
├── user_config.json
├── witchs_pot/
│   ├── [폰트 파일들]
│   └── charset.txt
└── witchs_gift/
    └── [생성된 파일들]
```

## 🚀 빌드 후 테스트

1. `dist/` 폴더에서 EXE 실행
2. `witchs_pot`, `witchs_gift` 폴더 생성 확인
3. 폰트 생성 기능 테스트

## 🐛 문제 해결

### "Python을 찾을 수 없습니다" 에러
→ `--onedir` 모드로 빌드하거나 코드 수정 필요

### 리소스 파일을 찾을 수 없음
→ spec 파일의 `datas` 경로 확인

### 실행 시 콘솔 창이 나타남
→ `--windowed` 또는 `console=False` 옵션 확인

