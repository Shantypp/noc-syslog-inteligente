@echo off
REM Doble clic para iniciar el NOC (instala lo necesario la primera vez).
REM Para recibir Syslog de los equipos de la red use: iniciar-red.bat
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 iniciar.py %*
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo.
    echo   No se encontro Python. Instale Python 3.12 o superior desde https://www.python.org/downloads/
    echo   Durante la instalacion marque la casilla "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
  )
  python iniciar.py %*
)
if errorlevel 1 pause
