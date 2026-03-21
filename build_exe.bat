@echo off
:: --- SCRIPT CONFIGURATION ---
title Build - GDT Gerenciador de Termos
color 0B
cls

echo ========================================================
echo GDT - GERENCIADOR DE TERMOS - BUILD SYSTEM v3.0 (MVC)
echo ========================================================
echo.

:: 1. DEPENDENCY VERIFICATION
echo [1/4] Verificando dependencias instaladas...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    color 0C
    echo.
    echo [ERRO] Falha ao instalar as bibliotecas. Verifique o requirements.txt
    pause
    exit /b
)
echo.

:: 2. CLEANUP BUILD ARTIFACTS
echo [2/4] Limpando cache de builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del *.spec
echo.

:: 3. COMPILATION (PYINSTALLER)
echo [3/4] Iniciando motor PyInstaller...
echo       Compilando a nova arquitetura MVC. Aguarde...
echo.

:: As pastas views, controllers, core e data sao reconhecidas nativamente nos imports pelo pyinstaller
:: --add-data "data/silver/cleaning_rules.json;data/silver" e usado para levar as regras estaticas
pyinstaller --noconfirm --onefile --windowed --clean ^
--name "GDT_Termos_NTI" ^
--icon "assets/app_icone.ico" ^
--add-data "assets;assets" ^
--add-data "data/silver/cleaning_rules.json;data/silver" ^
--hidden-import=keyring.backends.Windows ^
--hidden-import=win32ctypes ^
--hidden-import=flet ^
--hidden-import=google.generativeai ^
main.py

if %errorlevel% neq 0 (
    color 0C
    echo.
    echo ========================================================
    echo       ERRO FATAL NA COMPILACAO!
    echo ========================================================
    pause
    exit /b
)

:: 4. FINALIZE
echo.
echo [4/4] Processo finalizado com exito!
echo.
color 0A
echo ========================================================
echo       SUCESSO! O EXECUTAVEL ESTA DISPONIVEL NO 'dist/'
echo ========================================================
echo.
pause