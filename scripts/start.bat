@echo off
REM ============================================================
REM Start RedTrust Worker - with venv and dynamic IP detection
REM ============================================================

echo Setting PowerShell execution policy to Bypass for this session...
powershell -Command "Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force"

REM Navigate to project

cd /d "%USERPROFILE%\Documents\workspace\redtrust-automation"


REM Activate virtual environment
call .\.venv\Scripts\activate.bat

REM Obtener la Dirección IPv4 usando PowerShell para la subred 192.168.184.*
FOR /F "usebackq delims=" %%A IN (`powershell -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like '192.168.184.*' } | Select-Object -ExpandProperty IPAddress"`) DO (
    SET NODE_IP=%%A
    GOTO :continue
)
:continue
REM Quitar espacios en blanco
SET NODE_IP=%NODE_IP: =%

echo Worker started on IP: %NODE_IP%

REM Lanzar worker con Celery usando la IP detectada
celery -A api.worker worker ^
    --concurrency=1 ^
    --hostname=%NODE_IP%@%COMPUTERNAME% ^
    --pool=solo ^
    -Q robot_tasks ^
    -E ^
    --loglevel=info ^
    -n %NODE_IP%@%COMPUTERNAME%

echo.
echo ============================================================
echo Worker has stopped or encountered an error.
echo ============================================================
pause
