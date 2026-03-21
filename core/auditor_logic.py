"""
Módulo de Auditoria e Extração de Documentos.

Prové a lógica para extração de texto bruto de arquivos .docx, processamento
heurístico de datas e detecção de discrepâncias entre o banco de dados
e os registros físicos dos termos.
"""

# ==============================================================================
# 1. IMPORTS E DEPENDÊNCIAS
# ==============================================================================

import os
import sqlite3
from typing import Any, Callable, Dict, List, Optional

from core.utils import extract_docx_text, standardize_iso_date

# --- 1.1. Infraestrutura de Persistência ---
try:
    from data.gold.database import _get_connection
except ImportError:

    def _get_connection() -> sqlite3.Connection:
        """Fallback dinâmico para conexão em ambientes isolados ou de teste."""
        from data.gold.database import _get_db_path

        return sqlite3.connect(_get_db_path())


# ==============================================================================
# 2. MOTOR DE AUDITORIA
# ==============================================================================


def scan_for_divergences(
    limit: int = 100, progress_callback: Optional[Callable[[str], None]] = None
) -> List[Dict[str, Any]]:
    """Varre o histórico para identificar discrepâncias de data nos arquivos.

    Args:
        limit (int): Máximo de discrepâncias a rastrear.
        progress_callback (Optional[Callable]): Callback para atualização da UI.

    Returns:
        List[Dict[str, Any]]: Lista de discrepâncias encontradas.
    """
    divergences: List[Dict[str, Any]] = []

    try:
        conn = _get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, data_registro, caminho_docx, arquivo_origem "
            "FROM tb_termos ORDER BY id DESC"
        )
        rows = cursor.fetchall()

        count = 0
        for row in rows:
            if count >= limit:
                break

            id_termo, data_db, doc_path, nome_arquivo = row

            if not doc_path or not os.path.exists(doc_path):
                continue

            if progress_callback:
                progress_callback(f"Analisando: {str(nome_arquivo)}...")

            full_text = extract_docx_text(doc_path)
            data_encontrada = standardize_iso_date(full_text)

            if data_encontrada:
                data_db_iso = str(data_db).split(" ")[0] if data_db else ""

                if data_db_iso != data_encontrada:
                    divergences.append(
                        {
                            "id": id_termo,
                            "nome_arquivo": nome_arquivo,
                            "data_db": data_db_iso,
                            "data_encontrada": data_encontrada,
                            "caminho_docx": doc_path,
                        }
                    )
                    count += 1

        conn.close()
    except Exception as e:
        if progress_callback:
            progress_callback(f"Erro no Scanner: {e}")

    return divergences
