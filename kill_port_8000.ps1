# Script PowerShell pour liberer le port 8000
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Liberation du Port 8000" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$connections = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue

if ($connections) {
    foreach ($conn in $connections) {
        $pid = $conn.OwningProcess
        $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
        
        if ($process) {
            Write-Host "Processus trouve : $($process.Name) (PID: $pid)" -ForegroundColor Yellow
            Write-Host "Arret du processus..." -ForegroundColor Red
            
            Stop-Process -Id $pid -Force
            Write-Host "OK Processus arrete !" -ForegroundColor Green
        }
    }
} else {
    Write-Host "OK Aucun processus sur le port 8000" -ForegroundColor Green
}

Write-Host ""
Write-Host "Port 8000 libre !" -ForegroundColor Green
Write-Host ""
Write-Host "Vous pouvez maintenant lancer : python main.py" -ForegroundColor Cyan
Write-Host ""
pause
