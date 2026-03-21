"""
Módulo de Estratégias de Produção (Core Layer).

Implementa os gateways reais para busca de ativos no banco de dados
e processamento completo de termos (Word/PDF) no sistema de arquivos.
"""

# ==============================================================================
# 1. IMPORTS E DEPENDÊNCIAS
# ==============================================================================

import asyncio
import os
from functools import partial
from typing import Any, Callable, Dict, List, Optional

# --- 1.1. Configurações e Contratos ---
from core.settings import NETWORK_FOLDERS, PATH_ASSETS, TEMPLATE_FILENAME
from core.simulation_mode import IAssetGateway, ITermGateway

# --- 1.2. Utilitários de Processamento ---
from core.utils import (
    calculate_smart_path,
    convert_to_pdf,
    fire_progress,
    generate_final_docx,
    generate_unique_path,
    sanitize_filename,
    truncate_to_max_path,
)

# --- 1.3. Persistência e Limpeza ---
from data.gold.database import find_asset_details, save_to_history
from data.silver.data_cleaner import normalize_item

# ==============================================================================
# 2. IMPLEMENTAÇÕES DE INFRAESTRUTURA
# ==============================================================================


class RealAssetGateway(IAssetGateway):
    """Estratégia de Produção para recuperação de ativos no SQLite relacional."""

    async def find_asset(
        self, asset_tag: str, loop: asyncio.AbstractEventLoop
    ) -> Dict[str, Any]:
        """Consulta o banco de dados real em thread isolada.

        Args:
            asset_tag (str): Tag patrimonial identificadora.
            loop (asyncio.AbstractEventLoop): Event loop assíncrono.

        Returns:
            Dict[str, Any]: Status da busca e objeto do ativo normalizado.
        """
        try:
            local_res: Optional[Dict[str, Any]] = await loop.run_in_executor(
                None, find_asset_details, asset_tag
            )

            if local_res:
                clean_data = normalize_item(local_res)
                return {"status": "sucesso", "data": clean_data}

        except Exception as e:
            print(f"⚠️ Erro na Estratégia de BD Local: {e}")

        return {
            "status": "nao_encontrado",
            "msg": "Ativo não encontrado na base local.",
        }


class RealTermGateway(ITermGateway):
    """Estratégia de Produção para pipeline completo de emissão documental."""

    async def process_term(
        self,
        ui_data: Dict[str, Any],
        asset_list: List[Dict[str, Any]],
        template_data: Dict[str, Any],
        config: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """Orquestra a geração física (.docx/.pdf) e persistência lógica (SQL).

        Args:
            ui_data (Dict[str, Any]): Dados puros da UI.
            asset_list (List[Dict[str, Any]]): Itens do inventário.
            template_data (Dict[str, Any]): Contexto para renderização Word.
            config (Dict[str, Any]): Configurações de pastas de rede.
            loop (asyncio.AbstractEventLoop): Executor de tarefas.
            progress_callback (Optional[Callable]): Feedback visual.

        Returns:
            Dict[str, Any]: Resultado da operação com caminhos de arquivos.
        """

        def update_progress(pct: int, msg: str) -> None:
            """Sinaliza o progresso da operação para a interface."""
            fire_progress(progress_callback, pct, msg)

        try:
            op_val: str = ui_data.get("operacao", "Entrega")
            name_val: str = ui_data.get("nome", "Sem Nome")
            template_path: str = os.path.join(PATH_ASSETS, TEMPLATE_FILENAME)

            # --- 2.1. Resolução de Topologia de Rede ---
            update_progress(10, "Calculando destino na rede...")

            root_path_cfg = config.get("pasta_raiz_rede")
            if not root_path_cfg or not os.path.exists(root_path_cfg):
                root_path_cfg = os.path.join(os.environ["USERPROFILE"], "Documents")

            dest_folder = calculate_smart_path(root_path_cfg, op_val)
            acronym = NETWORK_FOLDERS.get(op_val, {}).get("prefixo", "DOC")

            raw_base_name = f"{acronym} - {sanitize_filename(name_val)}"
            base_name = truncate_to_max_path(dest_folder, raw_base_name)

            docx_path, _ = generate_unique_path(dest_folder, base_name, ".docx")

            # --- 2.2. Destino do Espelhamento PDF ---
            pdf_root_cfg = config.get("pasta_pdf")
            pdf_root = (
                pdf_root_cfg
                if pdf_root_cfg and os.path.exists(pdf_root_cfg)
                else dest_folder
            )
            pdf_path, _ = generate_unique_path(pdf_root, base_name, ".pdf")

            # --- 2.3. Compilação Word (Office Interop/Python-docx) ---
            update_progress(30, "Gerando documento Word...")
            await loop.run_in_executor(
                None,
                partial(generate_final_docx, template_data, template_path, docx_path),
            )

            # --- 2.4. Conversão para PDF ---
            update_progress(60, "Convertendo para PDF...")
            try:
                await loop.run_in_executor(
                    None, partial(convert_to_pdf, docx_path, pdf_path)
                )
            except Exception as pdf_err:
                print(f"⚠️ Falha na conversão de PDF (ignorado): {pdf_err}")

            # --- 2.5. Sincronização com o Banco Local (Historização) ---
            update_progress(85, "Sincronizando histórico na rede...")
            await loop.run_in_executor(
                None,
                partial(save_to_history, template_data, asset_list, docx_path),
            )

            update_progress(100, "Concluído!")

            return {
                "sucesso": True,
                "msg": "Termo gerado com sucesso!",
                "paths": {
                    "docx": docx_path,
                    "pdf": pdf_path,
                    "pasta": dest_folder,
                    "nome_base": base_name,
                },
                "config": config,
            }

        except Exception as e:
            return {"sucesso": False, "msg": f"Erro interno (Produção): {str(e)}"}
