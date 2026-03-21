"""
Módulo de Orquestração de Backups (Controller Layer).

Gerencia a replicação do banco de dados para segurança contra corrupção
ou perda acidental, implementando política de retenção rotativa.
"""

# ==============================================================================
# 1. IMPORTS E DEPENDÊNCIAS
# ==============================================================================

import os
import shutil
import traceback
from datetime import datetime
from typing import List

from data.gold.database import _get_db_path

# ==============================================================================
# 2. CONSTANTES E REGRAS DE RETENÇÃO
# ==============================================================================

MAX_BACKUPS_COUNT: int = 10
"""Número máximo de backups mantidos (Padrão: 10)."""


# ==============================================================================
# 3. SERVIÇOS DE BACKUP
# ==============================================================================


# --- 3.1. Operação Principal de Salvamento ---
def perform_auto_backup() -> bool:
    """Gera uma cópia do banco de dados SQLite ativo.

    Executa o backup na subpasta 'backups' e aciona a rotação FIFO
    para manter o limite de arquivos configurado.

    Returns:
        bool: True se o backup foi concluído com sucesso.
    """
    try:
        source_path: str = _get_db_path()

        if not os.path.exists(source_path):
            return False

        backup_dir: str = os.path.join(os.path.dirname(source_path), "backups")
        os.makedirs(backup_dir, exist_ok=True)

        timestamp: str = datetime.now().strftime("%Y-%m-%d_%H-%M")
        backup_name: str = f"backup_{timestamp}.db"
        dest_path: str = os.path.join(backup_dir, backup_name)

        shutil.copy2(source_path, dest_path)
        print(f"📦 Backup realizado: {backup_name}")

        _rotate_backups(backup_dir)

        return True

    except Exception as e:
        print(f"❌ Erro Crítico no Serviço de Backup: {e}")
        traceback.print_exc()
        return False


# --- 3.2. Manutenção e Rotação FIFO ---
def _rotate_backups(backup_dir: str) -> None:
    """Aplica algoritmo FIFO de poda de arquivos de backup excedentes.

    Identifica os backups pelo timestamp de modificação assegurando que
    o limite de retenção não seja ultrapassado.

    Args:
        backup_dir (str): Endereço físico da pasta de backups.
    """
    try:
        backup_files: List[str] = [
            os.path.join(backup_dir, f)
            for f in os.listdir(backup_dir)
            if f.endswith(".db") and f.startswith("backup_")
        ]

        sorted_backups: List[str] = sorted(backup_files, key=os.path.getmtime)

        while len(sorted_backups) > MAX_BACKUPS_COUNT:
            old_file: str = sorted_backups.pop(0)
            try:
                os.remove(old_file)
                print(f"🗑️ Limpeza de rotação: {os.path.basename(old_file)}")
            except OSError as e:
                print(f"⚠️ Falha ao deletar backup antigo: {e}")

    except Exception as ex:
        print(f"⚠️ Erro durante lógica de rotação: {ex}")


if __name__ == "__main__":
    perform_auto_backup()
