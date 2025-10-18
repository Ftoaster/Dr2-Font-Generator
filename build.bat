@echo off
chcp 65001 >nul
echo ====================================
echo Dr2 Font Generator - EXE 빌드 시작
echo ====================================
echo.

REM PyInstaller 설치 확인
echo [1/3] PyInstaller 확인 중...
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo PyInstaller가 설치되지 않았습니다. 설치 중...
    pip install pyinstaller pillow
)

echo.
echo [2/3] 이전 빌드 정리 중...
if exist build rmdir /s /q build

echo.
echo [3/3] EXE 빌드 중 (아이콘 포함)...
pyinstaller --clean Dr2_Font_Generator.spec

echo.
echo [4/4] 완료!
echo.
echo 빌드된 파일 위치: dist\Dr2 Font Generator.exe
echo.
echo 배포 시 필요한 항목:
echo - dist\Dr2 Font Generator.exe
echo - witchs_pot\ (폴더, 비어있어도 됨)
echo - witchs_gift\ (폴더, 비어있어도 됨)
echo - user_config.json (선택사항, 자동 생성됨)
echo.
pause

