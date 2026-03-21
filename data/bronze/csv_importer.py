"""
Módulo de Importação de CSV (Bronze Layer).

Realiza o processamento de lotes de ativos exportados (ex: GLPI),
aplicando normalização e ingestão atômica no banco de dados.
"""

# ==============================================================================
# 1. IMPORTS E DEPENDÊNCIAS
# ==============================================================================
import csv
import os
from typing import Tuple

from data.gold.database import _get_connection, init_db

# --- 1.1. Infraestrutura de Camadas (Silver → Gold) ---
from data.silver.data_cleaner import normalize_item

# ==============================================================================
# 2. MOTOR DE INGESTÃO CSV
# ==============================================================================


def import_csv_batch(csv_path: str) -> Tuple[int, int]:
    """Importa um arquivo CSV estruturado para o estoque de ativos.

    Realiza o fluxo ETL: Lida com delimitadores, normaliza nomes de tipos
    e fabricantes e insere/atualiza registros no SQLite.

    Args:
        csv_path (str): Caminho físico para o arquivo CSV.

    Returns:
        Tuple[int, int]: Quantidade de sucessos e falhas processadas.
    """
    if not os.path.exists(csv_path):
        return 0, 1

    sucessos = 0
    erros = 0
    dados_proc = []

    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")

            # --- 2.1. Varredura Iterativa das Linhas ---
            for row in reader:
                raw_patrimonio = row.get("Nome", "").strip()

                # --- 2.2. Filtragem de Linhas Sem Índice Chave ---
                if not raw_patrimonio:
                    erros += 1
                    continue

                # --- 2.3. Mapeamento do Dicionário Bruto ---
                dict_raw = {
                    "patrimonio": raw_patrimonio,
                    "tipo": row.get("Tipo", "").strip(),
                    "fabricante": row.get("Fabricante", "").strip(),
                    "modelo": row.get("Modelo", "").strip(),
                    "serial": row.get("Número de série", "").strip(),
                }

                # --- 2.4. Normalização via Silver Layer ---
                dict_clean = normalize_item(dict_raw)

                dados_proc.append(
                    (
                        dict_clean["patrimonio"].upper(),
                        dict_clean.get("tipo"),
                        dict_clean.get("fabricante"),
                        dict_clean.get("modelo"),
                        dict_clean.get("serial"),
                    )
                )

        if not dados_proc:
            return 0, erros

        # --- 2.5. Persistência Relacional ---
        init_db()
        with _get_connection() as conn:
            cursor = conn.cursor()

            cursor.executemany(
                """
                INSERT INTO tb_ativos (patrimonio, tipo, fabricante, modelo, serial)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(patrimonio) DO UPDATE SET
                    tipo=excluded.tipo,
                    fabricante=excluded.fabricante,
                    modelo=excluded.modelo,
                    serial=excluded.serial,
                    data_atualizacao=CURRENT_TIMESTAMP
                """,
                dados_proc,
            )
            conn.commit()

        sucessos = len(dados_proc)

    except Exception as e:
        print(f"❌ Erro Crítico no Módulo Bronze ETL de CSV: {e}")
        return 0, 1

    return sucessos, erros
