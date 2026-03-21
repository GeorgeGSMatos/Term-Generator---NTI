@echo off
:: --- SCRIPT CONFIGURATION ---
title Instalador de Dependencias - GDT
color 0B
cls

echo ========================================================
echo GDT - SETUP DE AMBIENTE (MVC ARCHITECTURE)
echo ========================================================
echo.

:: 1. CHECK PYTHON ENVIRONMENT
echo [1/3] Detectando interpretador Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo.
    echo [ERRO CRITICO] O interpretador Python nao foi encontrado nas Variaveis de Ambiente.
    echo Instale o Python 3.10+ e marque a opcao "Add Python to PATH" durante o setup.
    echo.
    pause
    exit /b
)
echo       Interpretador OK.
echo.

:: 2. UPGRADE PIP PIPELINE
echo [2/3] Sincronizando gerenciador de pacotes...
python -m pip install --upgrade pip >nul
echo       Pip atualizado.
echo.

:: 3. INSTALL REQUIRED PACKAGES
echo [3/3] Instalando pipeline de bibliotecas...
if not exist requirements.txt (
    color 0C
    echo [ERRO] O arquivo base 'requirements.txt' nao esta presente no diretorio.
    pause
    exit /b
)

pip install -r requirements.txt

if %errorlevel% neq 0 (
    color 0C
    echo.
    echo ========================================================
    echo       FALHA DE SINCRONIZACAO DE PACOTES!
    echo ========================================================
    echo Verifique suas permissoes administrativas ou conexao via Proxy.
    pause
    exit /b
)

color 0A
cls
echo ========================================================
echo       AMBIENTE GDT NTI PRONTO PARA DESENVOLVIMENTO
echo ========================================================
echo.
echo A arquitetura esta apta a rodar via 'python main.py'.
echo.
pause