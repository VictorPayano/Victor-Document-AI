@echo off
setlocal
title Instalar Victor Document AI

set "PROJECT=%~dp0"
set "PYTHON="

where py >nul 2>&1
if not errorlevel 1 set "PYTHON=py -3"

if "%PYTHON%"=="" (
    where python >nul 2>&1
    if not errorlevel 1 set "PYTHON=python"
)

if "%PYTHON%"=="" (
    echo.
    echo No se encontro Python 3.
    echo Instala Python desde https://www.python.org/downloads/ y marca
    echo la opcion "Add Python to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)

echo.
echo Creando el entorno local de Victor Document AI...
call %PYTHON% -m venv "%PROJECT%.venv"
if errorlevel 1 goto :error

echo Instalando los componentes necesarios. Esto puede tardar unos minutos...
call "%PROJECT%.venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :error
call "%PROJECT%.venv\Scripts\python.exe" -m pip install -r "%PROJECT%requirements.txt"
if errorlevel 1 goto :error

echo.
echo Instalacion terminada.
echo Ahora puedes abrir "Abrir Victor Document AI.vbs".
pause
exit /b 0

:error
echo.
echo La instalacion no pudo completarse. Comprueba la conexion a Internet
echo y que Python 3 este instalado correctamente.
pause
exit /b 1
