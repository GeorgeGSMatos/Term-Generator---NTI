"""
Módulo de Extração e Ingestão em Lote (Bronze Layer).

Coordena a leitura de documentos DOCX, extração de texto, enriquecimento
via IA Generativa e persistência no banco de dados, utilizando padrões
assíncronos para manter a interface responsiva.
"""

# ==============================================================================
# 1. IMPORTS E DEPENDÊNCIAS
# ==============================================================================

import asyncio
import json
import os
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

# --- 1.1. Infraestrutura e Core ---
from core.settings import NETWORK_FOLDERS, load_setting
from core.utils import extract_docx_text
from data.bronze.ai_worker import AIWorker
from data.gold.database import _get_connection, save_to_history
from data.silver.data_cleaner import normalize_item

# ==============================================================================
# 2. PIPELINE DE INGESTÃO AUTOMATIZADA
# ==============================================================================


async def run_smart_sync_generator(
    target_years: Optional[List[str]] = None,
    target_months: Optional[List[str]] = None,
    sync_state: Optional[Dict[str, bool]] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Orquestra a sincronização inteligente de documentos.

    Utiliza o padrão Generator para fornecer status em tempo real à UI
    sem bloquear a execução do processamento.

    Args:
        target_years (Optional[List[str]]): Filtro de anos.
        target_months (Optional[List[str]]): Filtro de meses.
        sync_state (Optional[Dict[str, bool]]): Controle de pausa/cancelamento.

    Yields:
        AsyncGenerator[Dict[str, Any], None]: Dicionário de status da operação.
    """

    config = load_setting()
    root_path = config.get("pasta_raiz_rede")

    if not root_path or not os.path.exists(root_path):
        yield {
            "type": "error",
            "msg": "Caminho de rede não configurado ou inacessível.",
        }
        return

    yield {"type": "log", "msg": "📂 Mapeando arquivos na rede..."}

    # --- 2.1. Escaneamento e Mapeamento de Arquivos ---
    files_to_process: List[Dict[str, str]] = []
    _t_years = [y.lower() for y in target_years] if target_years else []
    _t_months = [m.lower() for m in target_months] if target_months else []

    for op_type, info in NETWORK_FOLDERS.items():
        search_path = os.path.join(root_path, info["pasta"])
        if os.path.exists(search_path):
            try:
                for root, _, files in os.walk(search_path):
                    root_lower = root.lower()
                    match_year = (
                        any(y in root_lower for y in _t_years) if _t_years else True
                    )
                    match_month = (
                        any(m in root_lower for m in _t_months) if _t_months else True
                    )

                    if match_year and match_month:
                        for f in files:
                            if (
                                f.lower().endswith((".docx", ".doc"))
                                and not f.startswith("~$")
                                and not f.startswith(".")
                            ):
                                files_to_process.append(
                                    {"path": os.path.join(root, f), "op_type": op_type}
                                )
            except Exception:
                pass

    total = len(files_to_process)
    if total == 0:
        yield {
            "type": "done",
            "stats": {"sucesso": 0, "erro": 0, "pulados": 0},
            "msg": "Nenhum arquivo novo.",
        }
        return

    yield {"type": "log", "msg": f"🔌 Inicializando IA para {total} documentos..."}
    worker = AIWorker()

    # --- 2.2. Métricas e Controle de Qualidade (DLQ) ---
    stats = {"sucesso": 0, "erro": 0, "pulados": 0}
    quarentena: List[Dict[str, str]] = []

    # --- 2.3. Loop Principal de Processamento ---
    for idx, item in enumerate(files_to_process):
        if sync_state and sync_state.get("cancel", False):
            yield {"type": "log", "msg": "🚫 Cancelado pelo usuário."}
            break

        while sync_state and sync_state.get("pause", False):
            if sync_state.get("cancel", False):
                break
            await asyncio.sleep(0.5)

        if sync_state and sync_state.get("cancel", False):
            break

        file_path = item["path"]
        filename = os.path.basename(file_path)

        yield {
            "type": "progress",
            "current": idx + 1,
            "total": total,
            "filename": filename,
            "action": "Verificando DB",
        }

        # --- 2.4. Deduplicação Precoce ---
        try:
            skip_file = False

            with _get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id FROM tb_termos WHERE caminho_docx=?",
                    (file_path,),
                )
                if cursor.fetchone():
                    stats["pulados"] += 1
                    skip_file = True

            if skip_file:
                continue
        except Exception:
            pass

        # --- 2.5. Extração de Conteúdo ---
        yield {
            "type": "progress",
            "current": idx + 1,
            "total": total,
            "filename": filename,
            "action": "Lendo Word",
        }
        text = await asyncio.to_thread(extract_docx_text, file_path)

        if len(text) < 50:
            stats["erro"] += 1
            quarentena.append(
                {
                    "arquivo": filename,
                    "caminho": file_path,
                    "motivo": "Word corrompido, vazio ou ilegível (OCR falhou).",
                }
            )
            continue

        # --- 2.6. Enriquecimento de Dados via IA ---
        yield {
            "type": "progress",
            "current": idx + 1,
            "total": total,
            "filename": filename,
            "action": "Enviando à IA",
        }
        await asyncio.sleep(1.0)
        ai_data = await worker.analyze_document(text, filename)

        if not ai_data:
            stats["erro"] += 1
            quarentena.append(
                {
                    "arquivo": filename,
                    "caminho": file_path,
                    "motivo": "IA falhou (Erro de conexão, limite de cota ou formato ininteligível).",
                }
            )
            continue

        extracted_date = ai_data.get("termo", {}).get(
            "data_documento", "Não encontrada"
        )
        yield {"type": "log", "msg": f"📝 Data extraída do documento: {extracted_date}"}

        # --- 2.7. Persistência de Dados (Gold Layer) ---
        yield {
            "type": "progress",
            "current": idx + 1,
            "total": total,
            "filename": filename,
            "action": "Salvando",
        }
        try:
            raw_assets = ai_data.get("ativos", [])
            clean_assets = [normalize_item(a) for a in raw_assets]

            form_data = {
                "nome": ai_data.get("colaborador", {}).get("nome", "Desconhecido"),
                "area": ai_data.get("colaborador", {}).get("area", "TI"),
                "chamado": ai_data.get("termo", {}).get("numero_chamado", "S/N"),
                "tipo_operacao_db": item["op_type"],
                "observacoes": ai_data.get("termo", {}).get("observacoes", ""),
                "data_documento": ai_data.get("termo", {}).get("data_documento", ""),
            }

            success = await asyncio.to_thread(
                save_to_history, form_data, clean_assets, file_path
            )
            if success:
                stats["sucesso"] += 1
            else:
                stats["erro"] += 1
                quarentena.append(
                    {
                        "arquivo": filename,
                        "caminho": file_path,
                        "motivo": "Erro de persistência relacional (Restrição de DB).",
                    }
                )
        except Exception as e:
            stats["erro"] += 1
            quarentena.append(
                {
                    "arquivo": filename,
                    "caminho": file_path,
                    "motivo": f"Exceção fatal no pipeline: {str(e)}",
                }
            )

    # --- 2.8. Geração de Manifesto de Erros ---
    if quarentena:
        try:
            desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
            dlq_filename = (
                f"quarentena_importacao_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
            )
            dlq_path = os.path.join(desktop_path, dlq_filename)
            with open(dlq_path, "w", encoding="utf-8") as f:
                json.dump(quarentena, f, indent=4, ensure_ascii=False)
            yield {
                "type": "log",
                "msg": f"⚠️ Arquivos corrompidos detectados! Log salvo em: {dlq_filename} na Área de Trabalho.",
            }
            await asyncio.sleep(2)
        except Exception:
            pass

    yield {"type": "done", "stats": stats, "quarentena_count": len(quarentena)}
