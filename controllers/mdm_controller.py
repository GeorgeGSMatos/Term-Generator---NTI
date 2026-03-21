"""
Módulo Controlador do MDM (Controller Layer).

Atua como o orquestrador central das operações administrativas,
conectando a interface às camadas de persistência, inteligência e auditoria.
"""

# ==============================================================================
# 1. IMPORTS E DEPENDÊNCIAS
# ==============================================================================

import asyncio
import random
import sqlite3
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from core.auditor_logic import scan_for_divergences

# --- 1.1. Configurações e Core ---
from core.settings import (
    get_gemini_api_key,
    load_setting,
    set_gemini_api_key,
)

# --- 1.2. Ingestores e Workers ---
from data.bronze.csv_importer import import_csv_batch
from data.bronze.data_importer import run_smart_sync_generator

# --- 1.3. Acesso a Dados (Gold Layer) ---
from data.gold.database import (
    _get_db_path,
    get_available_dates,
    init_db,
    mdm_create_backup,
    mdm_delete_by_month_year,
    mdm_delete_duplicates,
    mdm_delete_record,
    mdm_execute_vacuum,
    mdm_export_csv,
    mdm_factory_reset,
    mdm_get_physical_tables,
    mdm_get_table_data,
    mdm_get_tables,
    mdm_reindex,
    mdm_run_diagnostics,
    mdm_run_optimize,
    mdm_search_table,
    mdm_truncate_table,
    mdm_update_record,
)

# --- 1.4. Limpeza e Regras (Silver Layer) ---
from data.silver.data_cleaner import mdm_add_rule, mdm_delete_rule, mdm_get_rules

# ==============================================================================
# 2. CONTROLADOR CENTRAL MDM
# ==============================================================================


class MDMController:
    """Orquestrador Central das Operações Administrativas e Auditoria."""

    def __init__(self) -> None:
        """Inicializa o controlador do Master Data Management."""
        pass

    # --- 2.1. Segurança e Configurações de IA ---

    def verify_admin_password(self, typed_pass: str) -> Tuple[bool, str]:
        """Compara a senha fornecida com a configurada no ambiente.

        Args:
            typed_pass (str): Senha digitada pelo usuário na UI.

        Returns:
            Tuple[bool, str]: Validação (True/False) e mensagem de erro se houver.
        """
        config: Dict[str, Any] = load_setting()
        real_pass: Optional[str] = config.get("senha_admin")

        if not real_pass:
            return False, "Senha Admin não configurada ou erro nas configurações."

        if typed_pass == real_pass:
            init_db()
            return True, ""

        return False, "Senha incorreta"

    def get_gemini_key(self) -> str:
        """Recupera a chave de API do Gemini das configurações seguras.

        Returns:
            str: A chave da API configurada.
        """
        return get_gemini_api_key()

    def save_gemini_key(self, key: str) -> None:
        """Persiste a chave de API do Gemini nas configurações do sistema.

        Args:
            key (str): Nova chave de API fornecida pelo usuário.
        """
        set_gemini_api_key(key)

    # --- 2.2. Gestão de Tabelas e Dados ---

    def get_all_tables(self) -> List[str]:
        """Obtém todas as tabelas (físicas e virtuais) disponíveis no catálogo.

        Returns:
            List[str]: Lista de nomes de tabelas de metadados e dados.
        """
        return mdm_get_tables()

    def get_physical_tables(self) -> List[str]:
        """Obtém puramente as tabelas físicas persistidas no SQLite.

        Returns:
            List[str]: Lista de nomes das tabelas físicas (ex: tb_termos).
        """
        return mdm_get_physical_tables()

    def get_table_data(
        self, table_name: str, limit: int, offset: int
    ) -> Tuple[List[str], List[Tuple[Any, ...]]]:
        """Recupera registros de uma tabela com suporte a paginação.

        Args:
            table_name (str): Nome da tabela no banco.
            limit (int): Número de registros.
            offset (int): Deslocamento (página).

        Returns:
            Tuple[List[str], List[Tuple[Any, ...]]]: Nomes das colunas e dados.
        """
        return mdm_get_table_data(table_name, limit, offset)

    def search_table(
        self, table_name: str, search_term: str, limit: int, offset: int
    ) -> Tuple[List[str], List[Tuple[Any, ...]]]:
        """Realiza busca textual em todas as colunas de uma tabela.

        Args:
            table_name (str): Nome da tabela.
            search_term (str): Texto de busca.
            limit (int): Limite de resultados.
            offset (int): Paginação.

        Returns:
            Tuple[List[str], List[Tuple[Any, ...]]]: Colunas e resultados filtrados.
        """
        return mdm_search_table(table_name, search_term, limit, offset)

    def update_record(
        self, table: str, pk_col: str, pk_val: Any, data: Dict[str, Any]
    ) -> bool:
        """Atualiza um registro específico em qualquer tabela do catálogo.

        Args:
            table (str): Nome da tabela física.
            pk_col (str): Nome da coluna Primary Key.
            pk_val (Any): Valor atual da Primary Key.
            data (Dict[str, Any]): Dicionário {coluna: valor} com as mudanças.

        Returns:
            bool: True se a alteração foi persistida com sucesso.
        """
        return mdm_update_record(table, pk_col, pk_val, data)

    def delete_record(self, table: str, pk_col: str, pk_val: Any) -> bool:
        """Deleta atomicamente um registro em uma tabela administrativa.

        Args:
            table (str): Nome da tabela desejada.
            pk_col (str): Nome da coluna identificadora.
            pk_val (Any): ID literal do registro a apagar.

        Returns:
            bool: Verdadeiro se deletou sem violações de integridade.
        """
        return mdm_delete_record(table, pk_col, pk_val)

    def export_table_csv(self, table: str, dest_path: str) -> bool:
        """Exporta os dados integrais de uma tabela para formato CSV.

        Args:
            table (str): Nome da tabela física ou virtual.
            dest_path (str): Caminho físico absoluto para salvar o arquivo.

        Returns:
            bool: True em sucesso na exportação.
        """
        return mdm_export_csv(table, dest_path)

    async def import_csv_async(self, file_path: str) -> Tuple[int, int]:
        """Orquestra a importação em lotes de CSV em thread secundária.

        Args:
            file_path (str): Caminho físico para o arquivo CSV de origem.

        Returns:
            Tuple[int, int]: Quantidade de sucessos e falhas detectadas.
        """
        return await asyncio.to_thread(import_csv_batch, file_path)

    # --- 2.3. Manutenção, Saúde e Diagnóstico ---

    def run_diagnostics(self) -> str:
        """Gera relatório de sanidade técnica do motor SQL.

        Returns:
            str: Resumo textual de logs e integridade do banco.
        """
        return mdm_run_diagnostics()

    def optimize_indexes(self) -> bool:
        """Executa comandos de otimização de índices (ANALYZE) para performance.

        Returns:
            bool: Verdadeiro se otimizado.
        """
        return mdm_run_optimize()

    def reindex_db(self) -> bool:
        """Reconstrói índices corrompidos ou fragmentados.

        Returns:
            bool: Verdadeiro se a reindexação foi concluída.
        """
        return mdm_reindex()

    def execute_vacuum(self) -> bool:
        """Libera espaço bloqueado no disco e desfragmenta o arquivo .db.

        Returns:
            bool: True se o vácuo físico foi finalizado.
        """
        return mdm_execute_vacuum()

    def create_backup(self) -> str:
        """Gera snapshot imediato do banco de dados oficial.

        Returns:
            str: Caminho do arquivo gerado ou mensagem de erro.
        """
        return mdm_create_backup()

    def delete_duplicates(self) -> Dict[str, int]:
        """Varre tabelas em busca de duplicatas lógicas.

        Returns:
            Dict[str, int]: Contagem de remoções por entidade.
        """
        return mdm_delete_duplicates()

    def factory_reset(self) -> bool:
        """Realiza limpeza total e reset de esquemas da aplicação.

        Returns:
            bool: True se o sistema foi resetado com sucesso.
        """
        return mdm_factory_reset()

    def get_dates_for_filter(self) -> Tuple[List[str], List[str]]:
        """Recupera metadados temporais para filtros de deleção em lote.

        Returns:
            Tuple[List[str], List[str]]: Anos e meses mapeados no banco.
        """
        return get_available_dates()

    def delete_by_period(self, month: str, year: str) -> int:
        """Exclui massivamente registros dentro de um período fiscal/calendário.

        Args:
            month (str): Nome do mês conforme calendário.
            year (str): Ano correspondente.

        Returns:
            int: Quantidade de registros eliminados.
        """
        return mdm_delete_by_month_year(month, year)

    def truncate_table(self, table: str) -> bool:
        """Limpa sumariamente todos os dados e sequências de uma tabela.

        Args:
            table (str): Nome da tabela para truncagem.

        Returns:
            bool: Verdadeiro se limpa.
        """
        return mdm_truncate_table(table)

    # --- 2.4. Gestão de Regras de Padronização ---

    def get_rules(self) -> List[Dict[str, str]]:
        """Lê metadados de substituição (De-Para) da camada de limpeza.

        Returns:
            List[Dict[str, str]]: Lista de dicionários representando as regras.
        """
        return mdm_get_rules()

    def add_rule(self, target: str, search: str, replace: str) -> bool:
        """Define nova regra de normalização automática no fluxo de ETL.

        Args:
            target (str): Alvo lógico (Coluna ou Entidade).
            search (str): Valor original (sujo).
            replace (str): Valor padronizado (limpo).

        Returns:
            bool: True se a regra for salva.
        """
        return mdm_add_rule(target, search, replace)

    def delete_rule(self, target: str, search: str) -> bool:
        """Remove regra de normalização ativa.

        Args:
            target (str): Contexto da regra.
            search (str): Filtro 'De' da regra.

        Returns:
            bool: True se deletada.
        """
        return mdm_delete_rule(target, search)

    # --- 2.5. Motor de Sincronização e Ingestão ---

    async def run_sync_generator(
        self, years: List[str], months: List[str], state: Dict[str, bool]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Emite fluxos de progresso da sincronização inteligente via IA.

        Args:
            years (List[str]): Filtro de anos para escaneamento.
            months (List[str]): Filtro de meses para escaneamento.
            state (Dict[str, bool]): Flags de controle (pause/cancel).

        Yields:
            Dict[str, Any]: Status granular do pipeline de ingestão.
        """
        async for status in run_smart_sync_generator(years, months, state):
            yield status

    # --- 2.6. Auditoria Técnica de Dados ---

    async def run_date_auditor_generator(
        self, limit: int = 50
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Executa auditoria de datas verificando Word vs Banco.

        Args:
            limit (int): Teto de discrepâncias para análise.

        Yields:
            Dict[str, Any]: Logs e resultados de auditoria para a UI.
        """
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def callback(msg: str) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, {"type": "log", "msg": msg})

        async def run_scan() -> None:
            try:
                results = await loop.run_in_executor(
                    None, scan_for_divergences, limit, callback
                )
                await queue.put({"type": "done", "results": results})
            except Exception as e:
                await queue.put({"type": "error", "msg": str(e)})

        asyncio.create_task(run_scan())

        while True:
            item = await queue.get()
            yield item
            if item["type"] in ["done", "error"]:
                break

    def apply_date_fixes(self, fixes: List[Dict[str, Any]]) -> bool:
        """Persiste correções de data validadas manualmente pelo Auditor.

        Args:
            fixes (List[Dict[str, Any]]): Lista de correções {id, action, ...}.

        Returns:
            bool: Sucesso na aplicação do lote de correções.
        """
        db_path = _get_db_path()
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")

            for fix in fixes:
                termo_id = fix["id"]
                action = fix["action"]

                if action == "correct":
                    nova_data = f"{fix['data_encontrada']} 12:00:00"
                    cursor.execute(
                        "UPDATE tb_termos SET data_registro = ? WHERE id = ?",
                        (nova_data, termo_id),
                    )
                elif action == "delete":
                    cursor.execute("DELETE FROM tb_termos WHERE id = ?", (termo_id,))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Erro ao aplicar correções: {e}")
            return False

    # --- 2.7. Ferramentas de Simulação e Stress ---

    def _run_mock_injection_sync(self, qtd: int) -> bool:
        """Injeta dados sintéticos para testes de carga e renderização.

        Método utilitário para ambiente de desenvolvimento/homologação.

        Args:
            qtd (int): Quantidade de tuplas complexas a gerar.

        Returns:
            bool: Sucesso na injeção de carga sintética.
        """
        nomes: List[str] = [
            "Ana Silva",
            "Carlos Souza",
            "Mariana Santos",
            "João Oliveira",
            "Fernanda Costa",
            "Pedro Lima",
            "Rafael Alves",
            "Juliana Mendes",
        ]
        setores: List[str] = [
            "Tecnologia",
            "Recursos Humanos",
            "Financeiro",
            "Diretoria",
            "Marketing",
            "Operações",
            "Comercial",
        ]
        ops: List[str] = ["Entrega", "Devolução", "Empréstimo"]
        tipos: List[str] = ["Notebook", "Desktop", "Monitor", "Smartphone"]
        fabricantes: List[str] = ["Dell", "HP", "Lenovo", "Apple", "Samsung"]

        db_path = _get_db_path()
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")

            for _ in range(qtd):
                nome: str = random.choice(nomes)
                setor: str = random.choice(setores)
                op: str = random.choice(ops)

                cursor.execute(
                    "INSERT INTO tb_colaboradores (nome, area) VALUES (?, ?) "
                    "ON CONFLICT(nome) DO UPDATE SET area=COALESCE(excluded.area, area)",
                    (nome, setor),
                )
                cursor.execute("SELECT id FROM tb_colaboradores WHERE nome=?", (nome,))
                colab_id: int = cursor.fetchone()[0]

                dias_atras: int = random.randint(0, 730)
                data_op: datetime = datetime.now() - timedelta(days=dias_atras)
                data_str: str = data_op.strftime("%Y-%m-%d %H:%M:%S")

                patrimonio: str = f"SIM-{random.randint(10000, 99999)}"
                tipo_ativo: str = random.choice(tipos)
                fab: str = random.choice(fabricantes)
                path: str = (
                    f"C:/Simulacao/MOCK_{nome.replace(' ', '')}_"
                    f"{random.randint(100, 999)}.docx"
                )
                chamado: str = f"MOCK-{random.randint(1000, 9999)}"

                cursor.execute(
                    """
                    INSERT INTO tb_ativos (patrimonio, tipo, fabricante, modelo, serial)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(patrimonio) DO UPDATE SET tipo=excluded.tipo
                    """,
                    (patrimonio, tipo_ativo, fab, "Modelo Simulado", "SN-MOCK"),
                )

                cursor.execute(
                    """
                    INSERT INTO tb_termos
                    (data_registro, tipo_operacao, chamado, colaborador_id, observacoes, 
                    caminho_docx, arquivo_origem)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (data_str, op, chamado, colab_id, "Mock Stress", path, "Simula"),
                )
                termo_id: int = cursor.lastrowid

                cursor.execute(
                    "INSERT INTO tb_termo_ativo (termo_id, patrimonio, qtd) VALUES (?, ?, ?)",
                    (termo_id, patrimonio, 1),
                )

            conn.commit()
            conn.close()
            return True
        except Exception as ex:
            print(f"Erro ao injetar mocks: {ex}")
            return False

    async def inject_mock_data_async(self, qtd: int) -> bool:
        """Injeta dados sintéticos fora da thread de interface.

        Args:
            qtd (int): Volume de dados a injetar.

        Returns:
            bool: Sucesso global da operação paralela.
        """
        return await asyncio.to_thread(self._run_mock_injection_sync, qtd)
