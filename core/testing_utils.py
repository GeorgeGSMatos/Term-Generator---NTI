"""
Módulo de Utilitários de Teste (Core Layer).

Fornece ferramentas para configuração de ambientes controlados e isolados,
utilizados principalmente pelas camadas de simulação e testes automatizados.
"""

# ==============================================================================
# 1. IMPORTS E DEPENDÊNCIAS
# ==============================================================================

import os
import shutil

# ==============================================================================
# 2. GERENCIAMENTO DE AMBIENTE DE TESTES
# ==============================================================================


def setup_test_environment(folder_name: str = "SIMULACAO_TEMP") -> str:
    """Configura um sandbox local isolado e limpo destinado a simulações.

    Remove instâncias prévias da pasta caso existam, garantindo um ambiente
    fresco e sem contaminação de sessões anteriores.

    Args:
        folder_name (str): Nome do diretório do sandbox. Padrão: "SIMULACAO_TEMP".

    Returns:
        str: Caminho absoluto apontando para o sandbox recém-criado.
    """
    path: str = os.path.join(os.getcwd(), folder_name)

    # --- 2.1. Limpeza de Execuções Anteriores ---
    if os.path.exists(path):
        try:
            shutil.rmtree(path)
        except OSError as e:
            print(f"⚠️ Aviso: Não foi possível limpar '{folder_name}': {e}")

    # --- 2.2. Criação da Estrutura Limpa ---
    os.makedirs(path, exist_ok=True)
    return path
