"""
Módulo de Controle do Histórico (Controller Layer).

Gerencia a recuperação, filtragem e manutenção (CRUD) dos registros
de termos gerados e armazenados no banco de dados Gold.
"""

# ==============================================================================
# 1. IMPORTS E DEPENDÊNCIAS
# ==============================================================================

from typing import Any, Dict, List, Optional, Tuple

from data.gold.database import (
    delete_history_record,
    get_available_dates,
    get_history,
    update_history_record,
)

# ==============================================================================
# 2. CONTROLADOR DE PESQUISAS
# ==============================================================================


class HistoryController:
    """Controlador que orquestra e gerencia as pesquisas e manutenção do histórico."""

    def __init__(self) -> None:
        """Inicializa o controlador com as dimensões temporais da base.
        """
        self.years_db, self.months_db = get_available_dates()

    # --- 2.1. Recuperação e Leitura de Dados ---

    def load_history_data(
        self,
        filter_mode: str,
        month: Optional[str],
        year: Optional[str],
        search_term: str,
        op_type: str,
        limit: int = 100,
    ) -> List[Tuple[Any, ...]]:
        """Busca registros no histórico aplicando filtros multicritério.

        Args:
            filter_mode (str): Modo de filtragem (Ex: 'ano_atual').
            month (Optional[str]): Mês do filtro.
            year (Optional[str]): Ano do filtro.
            search_term (str): Texto para busca livre.
            op_type (str): Tipo de operação.
            limit (int): Limite de resultados (Padrão: 100).

        Returns:
            List[Tuple[Any, ...]]: Lista de tuplas com os dados do histórico.
        """
        raw_rows = get_history(
            filter_mode=filter_mode,
            month=month,
            year=year,
            search_term=search_term,
            op_type=op_type,
            limit=limit,
        )
        return raw_rows

    # --- 2.2. Manutenção e Atualização ---

    def update_record(self, record_id: int, new_data: Dict[str, Any]) -> bool:
        """Atualiza um registro persistido no histórico.

        Args:
            record_id (int): Identificador único do registro.
            new_data (Dict[str, Any]): Dicionário com os novos valores.

        Returns:
            bool: Verdadeiro se a atualização foi bem-sucedida.
        """
        try:
            return update_history_record(record_id, new_data)
        except Exception:
            return False

    # --- 2.3. Exclusão e Limpeza ---

    def delete_record(self, record_id: int, docx_path: str) -> bool:
        """Exclui um registro do histórico e o arquivo físico associado.

        Args:
            record_id (int): Identificador do registro no banco.
            docx_path (str): Caminho absoluto do documento Word gerado.

        Returns:
            bool: Verdadeiro se a exclusão física e lógica foi concluída.
        """
        try:
            delete_history_record(record_id, docx_path=docx_path)
            return True
        except Exception:
            return False
