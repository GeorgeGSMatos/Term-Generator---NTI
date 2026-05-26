"""
Módulo de Persistência Relacional (Gold Layer).

Gerencia a conexão SQLite embarcada, garantindo integridade referencial,
executando migrações DDL e provendo rotinas transacionais para o Histórico
e o Dashboard Analítico.
"""

# ==============================================================================
# 1. IMPORTS E DEPENDÊNCIAS
# ==============================================================================

import csv
import os
import re
import shutil
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# --- 1.1. Configurações e Utilitários do Núcleo ---
from core.settings import MONTH_MAP, PATH_LOCAL_USER, load_setting

# ==============================================================================
# 2. CONFIGURAÇÕES E CONSTANTES
# ==============================================================================

# --- 2.1. Nomes de Arquivo do Banco ---
FILE_DB_TEST: str = "gdt_datatest.db"
FILE_DB_PROD: str = "gdt_database.db"

# --- 2.2. Mapeamento de Meses para SQL (ISO) ---
SQL_MONTH_MAP: Dict[str, str] = {
    nome_mes: f"{num_mes:02d}" for num_mes, nome_mes in MONTH_MAP.items()
}

# --- 2.3. Tabelas Autorizadas para MDM (Master Data Management) ---
MDM_ALLOWED_TABLES: frozenset = frozenset(
    {
        "tb_colaboradores",
        "tb_ativos",
        "tb_termos",
        "tb_termo_ativo",
    }
)

# ==============================================================================
# 3. INFRAESTRUTURA INTERNA
# ==============================================================================


def _get_db_path() -> str:
    """Calcula o caminho absoluto do arquivo SQLite.

    Prioriza diretórios em rede configurados. Faz fallback para o AppData local.

    Returns:
        str: Caminho absoluto para o arquivo .db.
    """
    settings: Dict[str, Any] = load_setting()
    network_root: Optional[str] = settings.get("pasta_raiz_rede")

    target_dir = (
        network_root
        if network_root and os.path.exists(network_root)
        else PATH_LOCAL_USER
    )

    db_filename = FILE_DB_TEST if settings.get("modo_teste") else FILE_DB_PROD
    return os.path.join(target_dir, db_filename)


def _get_connection() -> sqlite3.Connection:
    """Instancia uma conexão ativa com o motor SQLite.

    Aplica PRAGMAs de performance (WAL) e integridade referencial.

    Returns:
        sqlite3.Connection: Objeto de conexão aberto.
    """
    db_path: str = _get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)

    conn.execute("PRAGMA foreign_keys = ON")
    # Para evitar arquivos temporários (.db-journal) na rede, usamos MEMORY
    conn.execute("PRAGMA journal_mode = MEMORY")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA synchronous = NORMAL")

    return conn


def _create_tables(cursor: sqlite3.Cursor) -> None:
    """Cria a estrutura de tabelas e views (Schema DDL).

    Args:
        cursor (sqlite3.Cursor): Cursor da conexão ativa.
    """
    # --- 3.1. Dimensão: Colaboradores ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tb_colaboradores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            area TEXT
        )
    """)

    # --- 3.2. Dimensão: Ativos ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tb_ativos (
            patrimonio TEXT PRIMARY KEY,
            tipo TEXT,
            fabricante TEXT,
            modelo TEXT,
            serial TEXT,
            data_atualizacao DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # --- 3.3. Fato: Termos ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tb_termos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_registro DATETIME,
            tipo_operacao TEXT,
            chamado TEXT,
            observacoes TEXT,
            caminho_docx TEXT,
            arquivo_origem TEXT,
            colaborador_id INTEGER,
            FOREIGN KEY (colaborador_id) REFERENCES tb_colaboradores (id)
        )
    """)

    # --- 3.4. Associativa: Termo <-> Ativo ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tb_termo_ativo (
            termo_id INTEGER,
            patrimonio TEXT,
            qtd INTEGER DEFAULT 1,
            FOREIGN KEY (termo_id) REFERENCES tb_termos (id) ON DELETE CASCADE,
            FOREIGN KEY (patrimonio) REFERENCES tb_ativos (patrimonio),
            PRIMARY KEY (termo_id, patrimonio)
        )
    """)

    # --- 3.5. View de Histórico Consolidado ---
    cursor.execute("""
        CREATE VIEW IF NOT EXISTS vw_historico_legado AS
        SELECT 
            t.id,
            t.data_registro,
            t.tipo_operacao,
            t.chamado,
            c.nome AS colaborador,
            c.area AS area,
            t.caminho_docx,
            (
                SELECT json_group_array(json_object(
                    'patrimonio', a.patrimonio,
                    'tipo', a.tipo,
                    'fabricante', a.fabricante,
                    'modelo', a.modelo,
                    'serial', a.serial,
                    'qtd', ta.qtd,
                    'descricao_visual', a.tipo || ' ' || a.fabricante || ' - ' || a.modelo
                ))
                FROM tb_termo_ativo ta
                JOIN tb_ativos a ON ta.patrimonio = a.patrimonio
                WHERE ta.termo_id = t.id
            ) AS ativos_json,
            t.observacoes,
            t.arquivo_origem
        FROM tb_termos t
        LEFT JOIN tb_colaboradores c ON t.colaborador_id = c.id;
    """)

    # --- 3.6. Índices de Performance ---
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_termos_data ON tb_termos(data_registro)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_termos_tipo ON tb_termos(tipo_operacao)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_termo_ativo_termo ON tb_termo_ativo(termo_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_termo_ativo_pat ON tb_termo_ativo(patrimonio)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_colab_nome ON tb_colaboradores(nome)"
    )


# ==============================================================================
# 4. API PÚBLICA: INICIALIZAÇÃO E DIAGNÓSTICO
# ==============================================================================


def init_db() -> None:
    """Inicializa o banco de dados e executa migrações de schema (DDL)."""
    try:
        with _get_connection() as conn:
            cursor = conn.cursor()

            # --- 4.1. Migração: Remoção de Coluna Legada ---
            try:
                cursor.execute("ALTER TABLE tb_ativos DROP COLUMN categoria")
            except Exception:
                pass

            # --- 4.2. Migração: Consolidação de Datas ---
            try:
                cursor.execute("PRAGMA table_info(tb_termos)")
                existing_cols = [col[1] for col in cursor.fetchall()]

                has_old_mod = "ultima_modificacao" in existing_cols
                has_old_dt = "ultima_modificacao_dt" in existing_cols

                if has_old_mod or has_old_dt:
                    parts = ["data_registro"]
                    if has_old_dt:
                        parts.append("ultima_modificacao_dt")
                    if has_old_mod:
                        parts.append("datetime(ultima_modificacao, 'unixepoch')")

                    coalesce_sql = f"COALESCE({', '.join(parts)})"

                    cursor.execute(f"""
                        UPDATE tb_termos 
                        SET data_registro = {coalesce_sql}
                        WHERE data_registro IS NULL OR data_registro = ''
                    """)

                    if has_old_mod:
                        try:
                            cursor.execute(
                                "ALTER TABLE tb_termos DROP COLUMN ultima_modificacao"
                            )
                        except Exception:
                            pass

                    if has_old_dt:
                        try:
                            cursor.execute(
                                "ALTER TABLE tb_termos DROP COLUMN ultima_modificacao_dt"
                            )
                        except Exception:
                            pass

            except Exception as migration_err:
                if "no such column" not in str(migration_err).lower():
                    print(f"⚠️ Aviso na Migração de Datas: {migration_err}")

            _create_tables(cursor)
            conn.commit()
    except Exception as e:
        print(f"❌ Falha ao Inicializar Banco: {e}")


def force_asset_update(asset_tag: str, data_dict: Dict[str, Any]) -> None:
    """Realiza o Upsert (Insert ou Update) de um ativo no banco.

    Args:
        asset_tag (str): Número do patrimônio do ativo.
        data_dict (Dict[str, Any]): Dicionário com dados (tipo, fabricante, modelo, serial).
    """
    try:
        init_db()
        with _get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
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
                (
                    asset_tag.upper(),
                    data_dict.get("tipo"),
                    data_dict.get("fabricante"),
                    data_dict.get("modelo"),
                    data_dict.get("serial"),
                ),
            )
            conn.commit()
    except Exception as e:
        print(f"❌ Erro ao atualizar ativo ({asset_tag}): {e}")


# ==============================================================================
# 5. API PÚBLICA: OPERAÇÕES DML
# ==============================================================================


def save_to_history(
    form_data: Dict[str, Any], asset_list: List[Dict[str, Any]], docx_path: str
) -> bool:
    """Salva um termo e seus ativos no histórico e na base de ativos.

    Args:
        form_data (Dict[str, Any]): Dados do formulário do termo.
        asset_list (List[Dict[str, Any]]): Lista de ativos vinculados.
        docx_path (str): Caminho para o arquivo .docx gerado.

    Returns:
        bool: True se salvo com sucesso.
    """
    try:
        init_db()

        # --- 5.1. Determinação da Operação ---
        op_type = form_data.get("tipo_operacao_db") or form_data.get(
            "operacao", "Desconhecido"
        )
        if op_type == "Desconhecido":
            if form_data.get("x_entrega", "").strip():
                op_type = "Entrega"
            elif form_data.get("x_devolucao", "").strip():
                op_type = "Devolução"
            elif form_data.get("x_emprestimo", "").strip():
                op_type = "Empréstimo"

        # --- 5.2. Extração de Metadados do Arquivo ---
        filename = os.path.basename(docx_path) if docx_path else "Manual Entry"

        nome_colab = str(form_data.get("nome") or "Desconhecido").strip()
        area_colab = str(form_data.get("area") or "").strip()

        with _get_connection() as conn:
            cursor = conn.cursor()

            # --- 5.3. Cadastro/Update de Colaborador ---
            cursor.execute(
                """
                INSERT INTO tb_colaboradores (nome, area) VALUES (?, ?)
                ON CONFLICT(nome) DO UPDATE SET 
                    area=COALESCE(NULLIF(excluded.area, ''), area)
            """,
                (nome_colab, area_colab),
            )

            cursor.execute(
                "SELECT id FROM tb_colaboradores WHERE nome=?", (nome_colab,)
            )
            colab_id = cursor.fetchone()[0]

            # --- 5.4. Verificação de Duplicidade (Idempotência) ---
            if filename != "Manual Entry" and docx_path:
                cursor.execute(
                    "SELECT id FROM tb_termos WHERE caminho_docx=?",
                    (docx_path,),
                )
                if cursor.fetchone():
                    return True

            # --- 5.5. Tratamento de Data ---
            data_raw = str(form_data.get("data_documento") or "").strip()
            match_iso = re.search(r"(\d{4}-\d{2}-\d{2})", data_raw)

            if match_iso:
                data_str = f"{match_iso.group(1)} 12:00:00"
            else:
                data_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # --- 5.6. Inserção do Termo ---
            cursor.execute(
                """
                INSERT INTO tb_termos (
                    data_registro, tipo_operacao, chamado, observacoes,
                    caminho_docx, arquivo_origem, colaborador_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    data_str,
                    op_type,
                    form_data.get("chamado"),
                    form_data.get("observacoes"),
                    docx_path,
                    filename,
                    colab_id,
                ),
            )
            termo_id = cursor.lastrowid

            # --- 5.7. Processamento da Lista de Ativos ---
            asset_dict: Dict[str, Dict[str, Any]] = {}

            for ativo in asset_list:
                if not ativo:
                    continue

                pat_raw = ativo.get("patrimonio") or "S/N"
                patrimonio = str(pat_raw).strip().upper()

                if patrimonio in ["S/N", "", "N/A"]:
                    patrimonio = f"SN-{uuid.uuid4().hex[:8].upper()}"

                if patrimonio in asset_dict:
                    try:
                        qtd_ex = int(asset_dict[patrimonio].get("qtd", 1))
                        qtd_nv = int(ativo.get("qtd", 1))
                        asset_dict[patrimonio]["qtd"] = qtd_ex + qtd_nv
                    except (ValueError, TypeError):
                        pass
                else:
                    ativo["patrimonio"] = patrimonio
                    asset_dict[patrimonio] = ativo

            # --- 5.8. Persistência de Ativos e Vinculação ---
            for pat, at_data in asset_dict.items():
                cursor.execute(
                    """
                    INSERT INTO tb_ativos (patrimonio, tipo, fabricante, modelo, serial)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(patrimonio) DO UPDATE SET
                        tipo=excluded.tipo, 
                        fabricante=excluded.fabricante, 
                        modelo=excluded.modelo
                """,
                    (
                        pat,
                        at_data.get("tipo"),
                        at_data.get("fabricante"),
                        at_data.get("modelo"),
                        at_data.get("serial"),
                    ),
                )

                cursor.execute(
                    """
                    INSERT INTO tb_termo_ativo (termo_id, patrimonio, qtd) 
                    VALUES (?, ?, ?)
                """,
                    (termo_id, pat, int(at_data.get("qtd", 1))),
                )

            conn.commit()
        return True

    except Exception as e:
        print(f"❌ Erro ao salvar histórico relacional: {e}")
        return False


def delete_history_record(record_id: int, docx_path: Optional[str] = None) -> None:
    """Exclui um registro do histórico e limpa arquivos físicos e órfãos.

    Args:
        record_id (int): ID do termo na tb_termos.
        docx_path (Optional[str]): Caminho para o arquivo .docx (opcional).
    """
    try:
        with _get_connection() as conn:
            cursor = conn.cursor()

            # --- 5.9. Identificação de Ativos Vinculados ---
            cursor.execute(
                "SELECT patrimonio FROM tb_termo_ativo WHERE termo_id = ?",
                (record_id,),
            )
            affected_assets = [row[0] for row in cursor.fetchall()]

            # --- 5.10. Deleção do Termo (Cascade afeta tb_termo_ativo) ---
            cursor.execute("DELETE FROM tb_termos WHERE id = ?", (record_id,))

            # --- 5.11. Limpeza de Ativos Órfãos ---
            for pat in affected_assets:
                cursor.execute(
                    "SELECT COUNT(*) FROM tb_termo_ativo WHERE patrimonio = ?",
                    (pat,),
                )
                if cursor.fetchone()[0] == 0:
                    cursor.execute("DELETE FROM tb_ativos WHERE patrimonio = ?", (pat,))
                    print(f"🧹 Limpeza: Ativo órfão {pat} removido.")

            conn.commit()

        # --- 5.12. Remoção de Arquivos Físicos ---
        if docx_path and os.path.exists(docx_path):
            try:
                os.remove(docx_path)
                pdf_path = docx_path.replace(".docx", ".pdf")
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
            except OSError as e:
                print(f"⚠️ Erro ao deletar arquivos físicos: {e}")

    except Exception as e:
        print(f"❌ Erro crítico ao excluir registro {record_id}: {e}")


# ==============================================================================
# 6. API PÚBLICA: LEITURA E ANALYTICS
# ==============================================================================


def _build_date_filters(
    mode: str, year: Optional[str] = None, month: Optional[str] = None
) -> Tuple[str, List[Any]]:
    """Constrói cláusulas WHERE baseadas em filtros de data.

    Args:
        mode (str): Modo de filtragem ('hoje', 'semana', '30_dias', etc).
        year (Optional[str]): Ano específico.
        month (Optional[str]): Nome do mês por extenso.

    Returns:
        Tuple[str, List[Any]]: Cláusula SQL e lista de parâmetros correspondentes.
    """
    now = datetime.now()
    clause = ""
    params: List[Any] = []

    if mode == "hoje":
        clause = "date(data_registro) = date(?)"
        params.append(now.strftime("%Y-%m-%d"))
    elif mode == "semana":
        dt = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        clause = "date(data_registro) >= date(?)"
        params.append(dt)
    elif mode == "30_dias":
        dt = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        clause = "date(data_registro) >= date(?)"
        params.append(dt)
    elif mode == "mes_atual":
        clause = "strftime('%Y-%m', data_registro) = ?"
        params.append(now.strftime("%Y-%m"))
    elif mode == "ano_atual":
        clause = "strftime('%Y', data_registro) = ?"
        params.append(now.strftime("%Y"))
    elif mode == "especifico":
        sub_clauses = []
        if year:
            sub_clauses.append("strftime('%Y', data_registro) = ?")
            params.append(str(year))
        if month:
            sub_clauses.append("strftime('%m', data_registro) = ?")
            params.append(SQL_MONTH_MAP.get(month, "01"))
        clause = " AND ".join(sub_clauses)

    return clause, params


def get_history(
    filter_mode: str = "hoje",
    month: Optional[str] = None,
    year: Optional[str] = None,
    search_term: str = "",
    op_type: str = "todos",
    limit: Optional[int] = 100,
) -> List[Tuple[Any, ...]]:
    """Busca o histórico de termos com filtros aplicados.

    Args:
        filter_mode (str): Modo de data ('hoje', 'todos', etc).
        month (Optional[str]): Filtro de mês.
        year (Optional[str]): Filtro de ano.
        search_term (str): Termo de busca textual.
        op_type (str): Tipo de operação ('Entrega', 'Devolução', etc).
        limit (Optional[int]): Limite de resultados.

    Returns:
        List[Tuple[Any, ...]]: Lista de registros da view vw_historico_legado.
    """
    try:
        path: str = _get_db_path()
        if not os.path.exists(path):
            return []

        with _get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT id, data_registro, tipo_operacao, chamado, colaborador, area, 
                caminho_docx, ativos_json, observacoes, arquivo_origem 
                FROM vw_historico_legado 
                WHERE 1=1
            """
            params: List[Any] = []

            if op_type and op_type != "todos":
                query += " AND tipo_operacao = ?"
                params.append(op_type)

            if not search_term:
                clause, date_params = _build_date_filters(filter_mode, year, month)
                if clause:
                    query += f" AND {clause}"
                    params.extend(date_params)

            if search_term:
                wildcard = f"%{search_term}%"
                search_fields = [
                    "chamado",
                    "colaborador",
                    "area",
                    "ativos_json",
                    "arquivo_origem",
                ]
                search_clauses = " OR ".join(
                    [f"{field} LIKE ?" for field in search_fields]
                )
                query += f" AND ({search_clauses})"
                params.extend([wildcard] * len(search_fields))

            query += " ORDER BY data_registro DESC, id DESC"
            if limit:
                query += " LIMIT ?"
                params.append(limit)

            cursor.execute(query, params)
            return cursor.fetchall()

    except Exception as e:
        print(f"❌ Erro na busca de histórico: {e}")
        return []


def get_dashboard(filters: Dict[str, str]) -> Dict[str, Any]:
    """Calcula métricas agregadas para o painel de controle (Dashboard).

    Args:
        filters (Dict[str, str]): Dicionário com modo, ano, mes, op_type, etc.

    Returns:
        Dict[str, Any]: Estrutura com KPIs, setores, timeline e ticker.
    """
    path: str = _get_db_path()
    if not os.path.exists(path):
        return {}

    clauses: List[str] = ["1=1"]
    params: List[Any] = []

    mode = filters.get("modo", "ano_atual")
    op_filter = filters.get("op_type", "Geral")
    sector_type = filters.get("sector_type", "todos")
    asset_mode = filters.get("asset_mode", "saidas")

    clause, date_params = _build_date_filters(
        mode, filters.get("ano"), filters.get("mes")
    )
    if clause:
        clauses.append(clause)
        params.extend(date_params)

    # --- 6.1. Filtros Específicos para Gráficos ---
    chart_clauses, chart_params = list(clauses), list(params)
    if op_filter and op_filter not in ["Geral", "todos", "Todas"]:
        chart_clauses.append("tipo_operacao = ?")
        chart_params.append(op_filter)

    sector_clauses, sector_params = list(clauses), list(params)
    if sector_type and sector_type not in ["Geral", "todos", "Todas"]:
        sector_clauses.append("tipo_operacao = ?")
        sector_params.append(sector_type)

    asset_clauses, asset_params = list(clauses), list(params)
    if asset_mode == "saidas":
        asset_clauses.append("tipo_operacao IN ('Entrega', 'Empréstimo')")
    elif asset_mode == "entradas":
        asset_clauses.append("tipo_operacao = 'Devolução'")

    where_sql_base = " AND ".join(clauses)
    where_sql_charts = " AND ".join(chart_clauses)
    where_sql_sectors = " AND ".join(sector_clauses)
    where_sql_assets = " AND ".join(asset_clauses)

    results: Dict[str, Any] = {
        "kpis": {},
        "setores": [],
        "timeline": [],
        "ticker": [],
        "ativos_metricas": {"Notebook": 0, "Desktop": 0, "Monitor": 0},
    }

    try:
        import json

        with _get_connection() as conn:
            cursor = conn.cursor()

            # --- 6.2. KPIs de Volume Por Operação ---
            cursor.execute(
                f"""
                SELECT tipo_operacao, COUNT(*) 
                FROM vw_historico_legado 
                WHERE {where_sql_base} 
                GROUP BY tipo_operacao
            """,
                params,
            )
            results["kpis"] = {row[0]: row[1] for row in cursor.fetchall() if row[0]}

            # --- 6.3. Ticker: Atividades Recentes ---
            cursor.execute(
                f"""
                SELECT data_registro, tipo_operacao, chamado, colaborador, arquivo_origem 
                FROM vw_historico_legado 
                WHERE {where_sql_base} 
                ORDER BY data_registro DESC LIMIT 10
            """,
                params,
            )
            results["ticker"] = cursor.fetchall()

            # --- 6.4. Ranking de Setores ---
            cursor.execute(
                f"""
                SELECT area, COUNT(*) 
                FROM vw_historico_legado 
                WHERE {where_sql_sectors} AND area IS NOT NULL AND area != '' 
                GROUP BY area ORDER BY COUNT(*) DESC
            """,
                sector_params,
            )
            results["setores"] = cursor.fetchall()

            # --- 6.5. Timeline: Evolução Mensal ---
            cursor.execute(
                f"""
                SELECT strftime('%Y', data_registro), strftime('%m', data_registro), COUNT(*) 
                FROM vw_historico_legado 
                WHERE {where_sql_charts} AND data_registro IS NOT NULL 
                GROUP BY 1, 2 ORDER BY 1, 2
            """,
                chart_params,
            )
            results["timeline"] = [
                row for row in cursor.fetchall() if row[0] is not None
            ]

            # --- 6.6. Métricas de Hardware (Agregação JSON) ---
            cursor.execute(
                f"""
                SELECT ativos_json, tipo_operacao 
                FROM vw_historico_legado 
                WHERE {where_sql_assets} AND ativos_json IS NOT NULL
            """,
                asset_params,
            )
            ativos_raw = cursor.fetchall()

            for row in ativos_raw:
                try:
                    js_data = json.loads(row[0]) if isinstance(row[0], str) else []
                    for item in js_data:
                        tipo = item.get("tipo", "Outros")
                        qtd = int(item.get("qtd", 1))
                        results["ativos_metricas"][tipo] = (
                            results["ativos_metricas"].get(tipo, 0) + qtd
                        )
                except Exception:
                    pass

    except Exception as e:
        print(f"❌ Erro no Analytics (Dashboard): {e}")

    return results


def get_available_dates() -> Tuple[List[str], List[str]]:
    """Recupera os anos e meses únicos presentes no banco para filtros da UI.

    Returns:
        Tuple[List[str], List[str]]: Listas de anos e nomes de meses ordenados.
    """
    try:
        path = _get_db_path()
        if not os.path.exists(path):
            return [str(datetime.now().year)], ["Janeiro"]

        with _get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT DISTINCT strftime('%Y', data_registro) FROM tb_termos ORDER BY 1 DESC"
            )
            years = [str(r[0]) for r in cursor.fetchall() if r[0]]

            cursor.execute(
                "SELECT DISTINCT strftime('%m', data_registro) FROM tb_termos ORDER BY 1 ASC"
            )
            month_nums = [str(r[0]) for r in cursor.fetchall() if r[0]]

        inv_map = {v: k for k, v in SQL_MONTH_MAP.items()}
        month_names = [inv_map.get(m, m) for m in month_nums]

        return (years if years else [str(datetime.now().year)]), (
            month_names if month_names else ["Janeiro"]
        )

    except Exception:
        return [str(datetime.now().year)], ["Janeiro"]


def find_sector_collaborator(partial_name: str) -> Optional[str]:
    """Tenta localizar o setor de um colaborador pelo nome parcial (Auto-Complete).

    Args:
        partial_name (str): Início do nome do colaborador.

    Returns:
        Optional[str]: Setor encontrado ou None.
    """
    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT area FROM tb_colaboradores 
                WHERE nome LIKE ? 
                ORDER BY LENGTH(nome) ASC LIMIT 1
            """,
                (f"{partial_name}%",),
            )
            res = cursor.fetchone()
            return str(res[0]) if res else None
    except Exception:
        return None


def find_asset_details(asset_tag: str) -> Optional[Dict[str, Any]]:
    if not asset_tag:
        return None
    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT patrimonio, tipo, fabricante, modelo, serial FROM tb_ativos WHERE patrimonio LIKE ?",
                (f"{asset_tag.strip()}%",),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "patrimonio": row[0],
                    "tipo": row[1],
                    "fabricante": row[2],
                    "modelo": row[3],
                    "serial": row[4],
                }
            return None
    except Exception as e:
        print(f"❌ Erro ao buscar detalhes: {e}")
        return None


def mdm_get_tables() -> List[str]:
    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'"
            )
            return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        print(f"❌ Erro ao listar tabelas (MDM): {e}")
        return []


def mdm_get_physical_tables() -> List[str]:
    """Retorna apenas tabelas físicas e permitidas (Ignora Views como vw_historico_legado)."""
    return list(MDM_ALLOWED_TABLES)


def mdm_get_table_data(
    table_name: str, limit: int = 100, offset: int = 0
) -> Tuple[List[str], List[Tuple]]:
    allowed = MDM_ALLOWED_TABLES | {"vw_historico_legado"}
    if table_name not in allowed:
        print(f"❌ MDM: Tabela não permitida — '{table_name}'")
        return [], []
    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [col_info[1] for col_info in cursor.fetchall()]

            if not columns:
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 1")
                columns = [description[0] for description in cursor.description]

            cursor.execute(
                f"SELECT * FROM {table_name} LIMIT ? OFFSET ?", (limit, offset)
            )
            rows = cursor.fetchall()
            return columns, rows
    except Exception as e:
        print(f"❌ Erro ao ler dados da tabela '{table_name}' (MDM): {e}")
        return [], []


def mdm_run_diagnostics() -> str:
    """Executa um diagnóstico de integridade e volume na base de dados.

    Returns:
        str: Relatório textual com principais métricas e alertas.
    """
    try:
        with _get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM tb_termos")
            total_termos = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM tb_ativos")
            total_ativos = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT COUNT(id) FROM tb_termos 
                WHERE data_registro IS NULL OR data_registro = ''
            """
            )
            datas_corrompidas = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT COUNT(*) FROM tb_termo_ativo 
                WHERE termo_id NOT IN (SELECT id FROM tb_termos)
            """
            )
            ativos_orfaos = cursor.fetchone()[0]

            report = (
                f"Total de Termos: {total_termos}\n"
                f"Ativos Cadastrados: {total_ativos}\n"
                f"Datas Corrompidas: {datas_corrompidas} "
                f"{'⚠️' if datas_corrompidas > 0 else '✅'}\n"
                f"Ativos Órfãos: {ativos_orfaos} "
                f"{'⚠️' if ativos_orfaos > 0 else '✅'}"
            )
            return report
    except Exception as e:
        print(f"❌ Erro no Diagnóstico (MDM): {e}")
        return "Erro ao rodar diagnóstico. Verifique o console."


def mdm_execute_vacuum() -> bool:
    """Executa o comando VACUUM para otimizar o espaço em disco do banco.

    Returns:
        bool: True se executado com sucesso.
    """
    try:
        with _get_connection() as conn:
            conn.isolation_level = None
            conn.execute("VACUUM")
        return True
    except Exception as e:
        print(f"❌ Erro no Vacuum (MDM): {e}")
        return False


def mdm_factory_reset() -> bool:
    """Realiza um reset de fábrica, limpando todas as tabelas e views.

    Cria um backup (.bak) antes da operação destrutiva.

    Returns:
        bool: True se resetado com sucesso.
    """
    db_path = _get_db_path()
    try:
        if os.path.exists(db_path):
            backup_dir = os.path.join(os.path.dirname(db_path), "backups")
            os.makedirs(backup_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"reset_backup_{timestamp}.db"
            backup_path = os.path.join(backup_dir, backup_name)
            
            shutil.copy2(db_path, backup_path)
            print(f"✅ Backup de segurança criado no diretório de backups: {backup_name}")

        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DROP VIEW IF EXISTS vw_historico_legado")
            cursor.execute("DROP TABLE IF EXISTS tb_termo_ativo")
            cursor.execute("DROP TABLE IF EXISTS tb_termos")
            cursor.execute("DROP TABLE IF EXISTS tb_ativos")
            cursor.execute("DROP TABLE IF EXISTS tb_colaboradores")
            conn.commit()

        init_db()
        return True
    except Exception as e:
        print(f"❌ Erro Fatal no Reset de Fábrica (MDM): {e}")
        return False


def mdm_export_csv(table_name: str, export_path: str) -> bool:
    """Exporta uma tabela permitida para um arquivo CSV.

    Args:
        table_name (str): Nome da tabela ou view.
        export_path (str): Caminho do arquivo de destino.

    Returns:
        bool: True se exportado com sucesso.
    """
    allowed = MDM_ALLOWED_TABLES | {"vw_historico_legado"}
    if table_name not in allowed:
        print(f"❌ MDM: Tabela não permitida — '{table_name}'")
        return False
    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table_name}")

            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()

            with open(export_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(columns)
                writer.writerows(rows)

        return True
    except Exception as e:
        print(f"❌ Erro ao exportar CSV (MDM): {e}")
        return False


def mdm_search_table(
    table_name: str, search_term: str, limit: int = 100, offset: int = 0
) -> Tuple[List[str], List[Tuple[Any, ...]]]:
    """Realiza uma busca dinâmica em todas as colunas de uma tabela.

    Args:
        table_name (str): Nome da tabela.
        search_term (str): Termo de busca textual.
        limit (int): Limite de resultados.
        offset (int): Deslocamento para paginação.

    Returns:
        Tuple[List[str], List[Tuple[Any, ...]]]: Nomes das colunas e as linhas.
    """
    allowed = MDM_ALLOWED_TABLES | {"vw_historico_legado"}
    if table_name not in allowed:
        print(f"❌ MDM: Tabela não permitida — '{table_name}'")
        return [], []
    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [col_info[1] for col_info in cursor.fetchall()]

            if not columns:
                return [], []

            where_clauses = " OR ".join([f"{col} LIKE ?" for col in columns])
            params: List[Any] = [f"%{search_term}%"] * len(columns)

            query = f"SELECT * FROM {table_name} WHERE {where_clauses} LIMIT ? OFFSET ?"
            params.append(limit)
            params.append(offset)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return columns, rows
    except Exception as e:
        print(f"❌ Erro na busca dinâmica (MDM): {e}")
        return [], []


def mdm_update_record(
    table_name: str, pk_column: str, pk_value: Any, update_data: Dict[str, Any]
) -> bool:
    """Atualiza um registro específico em uma tabela permitida.

    Args:
        table_name (str): Nome da tabela.
        pk_column (str): Nome da coluna de chave primária.
        pk_value (Any): Valor da chave primária.
        update_data (Dict[str, Any]): Novos dados.

    Returns:
        bool: True se atualizado com sucesso.
    """
    if table_name not in MDM_ALLOWED_TABLES:
        print(f"❌ MDM: Tabela não permitida — '{table_name}'")
        return False
    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            set_clauses = ", ".join([f"{col} = ?" for col in update_data.keys()])
            params = list(update_data.values())
            params.append(pk_value)

            query = f"UPDATE {table_name} SET {set_clauses} WHERE {pk_column} = ?"
            cursor.execute(query, params)
            conn.commit()
            return True
    except Exception as e:
        print(f"❌ Erro no Update dinâmico (MDM): {e}")
        return False


def mdm_delete_record(table_name: str, pk_column: str, pk_value: Any) -> bool:
    """Exclui um registro específico em uma tabela permitida.

    Args:
        table_name (str): Nome da tabela.
        pk_column (str): Nome da coluna de chave primária.
        pk_value (Any): Valor da chave primária.

    Returns:
        bool: True se excluído com sucesso.
    """
    if table_name not in MDM_ALLOWED_TABLES:
        print(f"❌ MDM: Tabela não permitida — '{table_name}'")
        return False
    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            query = f"DELETE FROM {table_name} WHERE {pk_column} = ?"
            cursor.execute(query, (pk_value,))
            conn.commit()
            return True
    except Exception as e:
        print(f"❌ Erro no Delete dinâmico (MDM): {e}")
        return False


def mdm_run_optimize() -> bool:
    """Executa a PRAGMA optimize para melhorar performance do banco.

    Returns:
        bool: True se otimizado.
    """
    try:
        with _get_connection() as conn:
            conn.execute("PRAGMA optimize")
        return True
    except Exception as e:
        print(f"❌ Erro na otimização (MDM): {e}")
        return False


def mdm_reindex() -> bool:
    """Recontrói todos os índices das tabelas.

    Returns:
        bool: True se reindexado.
    """
    try:
        with _get_connection() as conn:
            conn.execute("REINDEX")
        return True
    except Exception as e:
        print(f"❌ Erro no Reindex (MDM): {e}")
        return False


def mdm_create_backup() -> str:
    """Cria um snapshot do banco de dados na Área de Trabalho.

    Returns:
        str: Nome do arquivo de backup criado ou string vazia em caso de erro.
    """
    db_path = _get_db_path()
    try:
        if os.path.exists(db_path):
            desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_database_{timestamp}.sqlite"
            backup_path = os.path.join(desktop_path, backup_name)
            with _get_connection() as src, sqlite3.connect(backup_path) as dst:
                src.backup(dst)
            return backup_name
        return ""
    except Exception as e:
        print(f"❌ Erro no Snapshot de Backup (MDM): {e}")
        return ""


def mdm_delete_duplicates() -> Dict[str, int]:
    """Remove registros duplicados em todas as tabelas, consolidando dados.

    Tenta preservar a integridade referencial ao migrar vínculos de registros
    duplicados para o registro principal antes da exclusão.

    Returns:
        Dict[str, int]: Quantidade de registros deletados por tabela.
    """
    deleted: Dict[str, int] = {
        "tb_colaboradores": 0,
        "tb_termos": 0,
        "tb_termo_ativo": 0,
        "tb_ativos": 0,
    }
    try:
        with _get_connection() as conn:
            cursor = conn.cursor()

            # --- 6.7. Colaboradores: Unificação por Nome ---
            cursor.execute(
                """
                SELECT UPPER(TRIM(nome)), MAX(id) 
                FROM tb_colaboradores 
                GROUP BY UPPER(TRIM(nome)) HAVING COUNT(*) > 1
            """
            )
            dups_colab = cursor.fetchall()

            for nome_upper, max_id in dups_colab:
                cursor.execute(
                    """
                    SELECT id FROM tb_colaboradores 
                    WHERE UPPER(TRIM(nome)) = ? AND id != ?
                """,
                    (nome_upper, max_id),
                )
                olds = [r[0] for r in cursor.fetchall()]

                if olds:
                    pl = ",".join(["?"] * len(olds))
                    cursor.execute(
                        f"""
                        UPDATE tb_termos SET colaborador_id = ? 
                        WHERE colaborador_id IN ({pl})
                    """,
                        [max_id] + olds,
                    )
                    cursor.execute(
                        f"DELETE FROM tb_colaboradores WHERE id IN ({pl})", olds
                    )
                    deleted["tb_colaboradores"] += cursor.rowcount

            # --- 6.8. Termos: Unificação de Atividades Idênticas ---
            cursor.execute("""
                SELECT 
                    IFNULL(data_registro, ''), 
                    IFNULL(tipo_operacao, ''), 
                    IFNULL(chamado, ''), 
                    IFNULL(colaborador_id, 0), 
                    IFNULL(observacoes, ''), 
                    IFNULL(caminho_docx, ''), 
                    IFNULL(arquivo_origem, '')
                FROM tb_termos 
                GROUP BY 1, 2, 3, 4, 5, 6, 7
                HAVING COUNT(*) > 1
            """)
            grupos_identicos = cursor.fetchall()

            for grp in grupos_identicos:
                cursor.execute(
                    """
                    SELECT id FROM tb_termos
                    WHERE
                        IFNULL(data_registro, '') = ? AND
                        IFNULL(tipo_operacao, '') = ? AND
                        IFNULL(chamado, '') = ? AND
                        IFNULL(colaborador_id, 0) = ? AND
                        IFNULL(observacoes, '') = ? AND
                        IFNULL(caminho_docx, '') = ? AND
                        IFNULL(arquivo_origem, '') = ?
                    ORDER BY id ASC
                """,
                    grp,
                )
                ids_duplicados = [r[0] for r in cursor.fetchall()]

                if len(ids_duplicados) > 1:
                    keep_id = ids_duplicados[0]
                    olds_ids = ids_duplicados[1:]

                    for old_id in olds_ids:
                        cursor.execute(
                            """
                            UPDATE OR IGNORE tb_termo_ativo 
                            SET termo_id = ? WHERE termo_id = ?
                        """,
                            (keep_id, old_id),
                        )
                        cursor.execute(
                            "DELETE FROM tb_termo_ativo WHERE termo_id = ?",
                            (old_id,),
                        )
                        deleted["tb_termo_ativo"] += cursor.rowcount

                        cursor.execute("DELETE FROM tb_termos WHERE id = ?", (old_id,))
                        deleted["tb_termos"] += cursor.rowcount

            # --- 6.9. Integridade: Limpeza de Órfãos ---
            cursor.execute(
                """
                DELETE FROM tb_termo_ativo 
                WHERE termo_id NOT IN (SELECT id FROM tb_termos)
            """
            )
            deleted["tb_termo_ativo"] += cursor.rowcount

            cursor.execute(
                """
                DELETE FROM tb_termo_ativo 
                WHERE patrimonio NOT IN (SELECT patrimonio FROM tb_ativos)
            """
            )
            deleted["tb_termo_ativo"] += cursor.rowcount

            conn.commit()
            return deleted

    except Exception as e:
        print(f"❌ Erro ao apagar duplicatas (MDM): {e}")
        return {"error": -1}


def update_history_record(record_id: int, data_dict: Dict[str, Any]) -> bool:
    """Atualiza campos específicos de um termo de histórico.

    Args:
        record_id (int): ID do termo.
        data_dict (Dict[str, Any]): Campos a serem atualizados.

    Returns:
        bool: True se atualizado com sucesso.
    """
    try:
        with _get_connection() as conn:
            cursor = conn.cursor()

            nome_colab = data_dict.get("colaborador")
            colab_id = None

            if nome_colab:
                nome_colab = nome_colab.strip()
                cursor.execute(
                    """
                    INSERT INTO tb_colaboradores (nome, area) VALUES (?, ?) 
                    ON CONFLICT(nome) DO UPDATE SET 
                        area=COALESCE(excluded.area, area)
                """,
                    (nome_colab, data_dict.get("area", "")),
                )
                cursor.execute(
                    "SELECT id FROM tb_colaboradores WHERE nome=?", (nome_colab,)
                )
                colab_id = cursor.fetchone()[0]

            update_fields = []
            params: List[Any] = []

            if "chamado" in data_dict:
                update_fields.append("chamado = ?")
                params.append(data_dict["chamado"])

            if "observacoes" in data_dict:
                update_fields.append("observacoes = ?")
                params.append(data_dict["observacoes"])

            if "tipo_operacao" in data_dict:
                update_fields.append("tipo_operacao = ?")
                params.append(data_dict["tipo_operacao"])

            if colab_id is not None:
                update_fields.append("colaborador_id = ?")
                params.append(colab_id)

            if not update_fields:
                return True

            query = f"UPDATE tb_termos SET {', '.join(update_fields)} WHERE id = ?"
            params.append(record_id)

            cursor.execute(query, params)
            conn.commit()
            return True

    except Exception as e:
        print(f"❌ Erro ao atualizar histórico: {e}")
        return False


def mdm_delete_by_month_year(month: str, year: str) -> int:
    """Exclui todos os termos de um mês e ano específicos.

    Args:
        month (str): Nome do mês.
        year (str): Ano (YYYY).

    Returns:
        int: Quantidade de registros deletados ou -1 em caso de erro.
    """
    try:
        # --- 6.10. Formatação de Parâmetros ---
        mes_formatado = str(month).strip().capitalize()
        month_num = SQL_MONTH_MAP.get(mes_formatado, "01")

        target_prefix = f"{str(year).strip()}-{month_num}"
        target_br = f"/{month_num}/{str(year).strip()}"

        with _get_connection() as conn:
            cursor = conn.cursor()

            # --- 6.11. Identificação de Candidatos ---
            cursor.execute("SELECT id, data_registro FROM tb_termos")
            all_termos = cursor.fetchall()

            termos_ids = []
            for t_id, data_reg in all_termos:
                if not data_reg:
                    continue
                d_str = str(data_reg).strip()

                if d_str.startswith(target_prefix) or target_br in d_str:
                    termos_ids.append(t_id)

            if not termos_ids:
                return 0

            # --- 6.12. Mapeamento para Limpeza de Órfãos ---
            placeholders = ",".join(["?"] * len(termos_ids))
            cursor.execute(
                f"""
                SELECT DISTINCT patrimonio FROM tb_termo_ativo 
                WHERE termo_id IN ({placeholders})
            """,
                termos_ids,
            )
            pats = [row[0] for row in cursor.fetchall()]

            # --- 6.13. Exclusão em Massa ---
            cursor.execute(
                f"DELETE FROM tb_termos WHERE id IN ({placeholders})", termos_ids
            )

            for pat in pats:
                cursor.execute(
                    "SELECT COUNT(*) FROM tb_termo_ativo WHERE patrimonio = ?", (pat,)
                )
                if cursor.fetchone()[0] == 0:
                    cursor.execute("DELETE FROM tb_ativos WHERE patrimonio = ?", (pat,))

            conn.commit()
            return len(termos_ids)

    except Exception as e:
        print(f"❌ Erro ao deletar por período (MDM): {e}")
        return -1


def mdm_truncate_table(table_name: str) -> bool:
    """Esvazia uma tabela por completo, ignorando FKs temporariamente.

    Args:
        table_name (str): Nome da tabela.

    Returns:
        bool: True se esvaziada.
    """
    if table_name not in MDM_ALLOWED_TABLES:
        print(f"❌ MDM: Tabela não permitida — '{table_name}'")
        return False
    try:
        db_path = _get_db_path()
        conn = _get_connection()
        conn.isolation_level = None
        cursor = conn.cursor()

        cursor.execute("PRAGMA foreign_keys = OFF")
        cursor.execute(f"DELETE FROM {table_name}")

        try:
            cursor.execute("DELETE FROM sqlite_sequence WHERE name=?", (table_name,))
        except Exception:
            pass

        cursor.execute("PRAGMA foreign_keys = ON")
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Erro ao esvaziar tabela {table_name} (MDM): {e}")
        return False


# ==============================================================================
# 7. QUERIES DO DASHBOARD
# ==============================================================================


def get_available_sectors() -> List[str]:
    """Busca todos os setores únicos que possuem termos registrados.

    Returns:
        List[str]: Nomes dos setores ordenados alfabeticamente.
    """
    try:
        db_path = _get_db_path()
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT c.area 
                FROM tb_termos t
                JOIN tb_colaboradores c ON t.colaborador_id = c.id
                WHERE c.area IS NOT NULL AND c.area != ''
                ORDER BY c.area ASC
            """)
            return [str(row[0]) for row in cursor.fetchall()]
    except Exception as e:
        print(f"❌ Erro ao buscar setores: {e}")
        return []


def get_dashboard_raw(
    target_year: str = "Todos",
    target_month: str = "Todos",
    target_sector: str = "Todos",
) -> Dict[str, Any]:
    """Construtor dinâmico de queries para o Dashboard (Visão Raw).

    Args:
        target_year (str): Ano filtrado ou 'Todos'.
        target_month (str): Mês filtrado ou 'Todos'.
        target_sector (str): Setor filtrado ou 'Todos'.

    Returns:
        Dict[str, Any]: Estrutura com KPIs, setores, ativos, timeline e ticker.
    """
    try:
        db_path = _get_db_path()
        with _get_connection() as conn:
            cursor = conn.cursor()

            # --- 7.1. Construção do Filtro WHERE ---
            where_clauses = []
            params: List[Any] = []

            if target_year != "Todos":
                where_clauses.append("strftime('%Y', t.data_registro) = ?")
                params.append(target_year)

            if target_month != "Todos":
                month_num = SQL_MONTH_MAP.get(target_month.capitalize(), "01")
                where_clauses.append("strftime('%m', t.data_registro) = ?")
                params.append(month_num)

            if target_sector != "Todos":
                where_clauses.append("c.area = ?")
                params.append(target_sector)

            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

            # --- 7.2. Query de KPIs ---
            cursor.execute(
                f"""
                SELECT t.tipo_operacao, COUNT(DISTINCT t.id)
                FROM tb_termos t
                LEFT JOIN tb_colaboradores c ON t.colaborador_id = c.id
                WHERE {where_sql}
                GROUP BY t.tipo_operacao
            """,
                params,
            )
            kpis = {row[0]: row[1] for row in cursor.fetchall()}

            # --- 7.3. Query de Setores ---
            cursor.execute(
                f"""
                SELECT c.area, COUNT(DISTINCT t.id)
                FROM tb_termos t
                JOIN tb_colaboradores c ON t.colaborador_id = c.id
                WHERE {where_sql} AND c.area IS NOT NULL
                GROUP BY c.area
            """,
                params,
            )
            setores = cursor.fetchall()

            # --- 7.4. Query de Tipos de Ativos ---
            cursor.execute(
                f"""
                SELECT a.tipo, COUNT(a.patrimonio)
                FROM tb_termo_ativo ta
                JOIN tb_termos t ON ta.termo_id = t.id
                JOIN tb_ativos a ON ta.patrimonio = a.patrimonio
                LEFT JOIN tb_colaboradores c ON t.colaborador_id = c.id
                WHERE {where_sql} AND a.tipo IS NOT NULL
                GROUP BY a.tipo
            """,
                params,
            )
            ativos = cursor.fetchall()

            # --- 7.5. Query de Linha do Tempo ---
            timeline_where = (
                " AND ".join([w for w in where_clauses if "('%m'" not in w])
                if where_clauses
                else "1=1"
            )
            timeline_params = [
                p for p, w in zip(params, where_clauses) if "('%m'" not in w
            ]

            cursor.execute(
                f"""
                SELECT strftime('%Y-%m', t.data_registro) as mes_ano, COUNT(DISTINCT t.id)
                FROM tb_termos t
                LEFT JOIN tb_colaboradores c ON t.colaborador_id = c.id
                WHERE {timeline_where} AND t.data_registro IS NOT NULL
                GROUP BY mes_ano
                ORDER BY mes_ano ASC
            """,
                timeline_params,
            )
            timeline = cursor.fetchall()

            # --- 7.6. Query de Atividades Recentes ---
            cursor.execute(
                f"""
                SELECT t.data_registro, t.tipo_operacao, c.nome, c.area
                FROM tb_termos t
                JOIN tb_colaboradores c ON t.colaborador_id = c.id
                WHERE {where_sql}
                ORDER BY t.data_registro DESC
                LIMIT 50
            """,
                params,
            )
            ticker = cursor.fetchall()

            return {
                "kpis": kpis,
                "setores": setores,
                "ativos": ativos,
                "timeline": timeline,
                "ticker": ticker,
            }

    except Exception as e:
        print(f"❌ Erro Crítico na Query Raw do Dashboard: {e}")
        return {
            "kpis": {},
            "setores": [],
            "ativos": [],
            "timeline": [],
            "ticker": [],
        }
