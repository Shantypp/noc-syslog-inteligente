@echo off
REM Iniciador de todo el sistema NOC Syslog (doble clic).
REM Prepara lo necesario, detecta si estas conectado a los equipos Cisco
REM (modo red) o no (modo laboratorio), inicia el NOC y abre el navegador.
title NOC Syslog
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 iniciar.py --auto %*
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo.
    echo   No se encontro Python. Instale Python 3.12 o superior desde https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
  )
  python iniciar.py --auto %*
)
if errorlevel 1 pause
