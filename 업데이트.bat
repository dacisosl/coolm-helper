@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==========================================
echo   쿨 일정 도우미 - 업데이트 (더블클릭용)
echo ==========================================
echo.

echo [1/5] 실행 중인 프로그램 닫는 중...
taskkill /im CoolmHelper.exe /f >nul 2>&1

echo [2/5] 최신 코드 받는 중...
git pull
if errorlevel 1 (
    echo.
    echo (!) 최신 코드를 받지 못했어요. 인터넷 연결을 확인하거나,
    echo     Claude Code에 "업데이트.bat이 git pull에서 실패했어"라고 물어보세요.
    pause
    exit /b 1
)

echo [3/5] 등록해 둔 일정 백업 중...
if exist "dist\CoolmHelper\store\events.json" (
    copy /y "dist\CoolmHelper\store\events.json" "%TEMP%\coolm_events_backup.json" >nul
)

echo [4/5] 프로그램 새로 만드는 중... (몇 분 걸릴 수 있어요)
python build.py
if errorlevel 1 (
    echo.
    echo (!) 빌드에 실패했어요. Claude Code에 "업데이트.bat 빌드가 실패했어"라고 물어보세요.
    pause
    exit /b 1
)

echo [5/5] 백업해 둔 일정 되돌리는 중...
if exist "%TEMP%\coolm_events_backup.json" (
    if not exist "dist\CoolmHelper\store" mkdir "dist\CoolmHelper\store"
    copy /y "%TEMP%\coolm_events_backup.json" "dist\CoolmHelper\store\events.json" >nul
)

echo.
echo ✅ 업데이트 완료! 바탕화면의 펭귄 아이콘으로 실행하세요.
echo.
pause
