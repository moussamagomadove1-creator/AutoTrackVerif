@echo off
echo ========================================
echo    Liberation du Port 8000
echo ========================================
echo.

echo Recherche du processus sur le port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do (
    echo Processus trouve : PID %%a
    echo Arret du processus...
    taskkill /PID %%a /F
    echo.
)

echo.
echo OK Port 8000 libere !
echo.
echo Vous pouvez maintenant lancer : python main.py
echo.
pause
