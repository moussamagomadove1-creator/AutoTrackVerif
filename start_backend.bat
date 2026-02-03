@echo off
title AutoTrack - Lancement Backend
color 0A

echo ========================================
echo    AutoTrack Backend - Demarrage
echo ========================================
echo.

echo [1/3] Verification de Python...
python --version
if errorlevel 1 (
    echo ERREUR: Python n'est pas installe ou n'est pas dans le PATH
    pause
    exit /b 1
)
echo.

echo [2/3] Verification du port 8001...
netstat -ano | findstr :8001 > nul
if not errorlevel 1 (
    echo AVERTISSEMENT: Le port 8001 est deja utilise
    echo Voulez-vous le liberer ? (O/N)
    set /p choice=
    if /i "%choice%"=="O" (
        for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001') do (
            taskkill /PID %%a /F
        )
    )
)
echo.

echo [3/3] Lancement du backend...
echo.
echo Backend disponible sur : http://localhost:8001
echo Documentation API      : http://localhost:8001/docs
echo.
echo Appuyez sur CTRL+C pour arreter le serveur
echo.

python main.py

pause
