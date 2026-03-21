"""
Módulo de Serviços (Controller Layer).

Centraliza a lógica de negócios para gestão de ativos e pipeline de
processamento de termos, mediando a comunicação entre UI e Gateways.
"""

# ==============================================================================
# 1. IMPORTS E DEPENDÊNCIAS
# ==============================================================================

import asyncio
from typing import Any, Callable, Dict, List, Optional

# --- 1.1. Configurações e Utilitários Core ---
from core.settings import KEYWORDS_MOVEMENT, load_setting
from core.simulation_mode import IAssetGateway, ITermGateway
from core.utils import (
    classify_operation_type,
    fire_progress,
    get_full_date_text,
)

# --- 1.2. Infraestrutura de Dados ---
from data.gold.database import find_sector_collaborator

# ==============================================================================
# 2. SERVIÇOS DE ATIVOS
# ==============================================================================


class AssetService:
    """Acopla requisições da interface com a recuperação de ativos de infra."""

    @staticmethod
    async def find_asset(
        asset_tag: str, loop: asyncio.AbstractEventLoop, gateway: IAssetGateway
    ) -> Dict[str, Any]:
        """Busca um ativo utilizando o gateway configurado (Real ou Simulação).

        Args:
            asset_tag (str): Patrimônio do item.
            loop (asyncio.AbstractEventLoop): Loop de eventos assíncronos.
            gateway (IAssetGateway): Gateway de comunicação com a fonte de dados.

        Returns:
            Dict[str, Any]: Dados do ativo localizados.
        """
        return await gateway.find_asset(asset_tag, loop)

    @staticmethod
    def get_collaborator_sector(name: str) -> str:
        """Realiza projeção de área sugerida baseada no histórico.

        Args:
            name (str): Nome do colaborador para busca.

        Returns:
            str: Nome do último setor registrado ou vazio.
        """
        if not name or not name.strip():
            return ""

        sector_found: Optional[str] = find_sector_collaborator(name.strip())
        return sector_found if sector_found else ""

    @staticmethod
    def sort_assets_for_ui(asset_list: List[Dict[str, Any]]) -> None:
        """Ordena a lista de ativos para exibição prioritária na UI.

        Move itens com patrimônio válido para o topo da lista.

        Args:
            asset_list (List[Dict[str, Any]]): Lista de ativos em memória.
        """
        if not asset_list:
            return

        asset_list.sort(key=lambda x: x.get("patrimonio", "S/N") == "S/N")


# ==============================================================================
# 3. SERVIÇOS DE TERMOS
# ==============================================================================


class TermService:
    """Motor de orquestração para geração e processamento de documentos físico/lógicos."""

    @staticmethod
    def generate_summary_copy(
        ui_data: Dict[str, Any], asset_list: List[Dict[str, Any]]
    ) -> str:
        """Gera um resumo textual amigável para cópia manual em tickets.

        Args:
            ui_data (Dict[str, Any]): Inputs do formulário.
            asset_list (List[Dict[str, Any]]): Itens atrelados à operação.

        Returns:
            str: Resumo formatado com bullet points.
        """
        op: str = ui_data.get("operacao", "Operação")
        colab: str = ui_data.get("nome", "Colaborador")
        sector: str = ui_data.get("area", "Setor")

        lines: List[str] = [
            f"Realizado Termo de {op} para o colaborador(a) {colab} - {sector},",
            "-" * 30,
        ]

        for asset in asset_list:
            pat: str = asset.get("patrimonio", "S/N")
            desc: str = asset.get(
                "descricao_visual", asset.get("modelo", "Equipamento")
            )
            lines.append(f"• [{pat}] {desc}")

        lines.append("-" * 30)

        obs_text: str = ui_data.get("observacoes") or ui_data.get("obs", "")
        if obs_text:
            lines.append(f"OBS: {obs_text}")

        return "\n".join(lines)

    @staticmethod
    async def process_term(
        ui_data: Dict[str, Any],
        asset_list: List[Dict[str, Any]],
        loop: asyncio.AbstractEventLoop,
        gateway: ITermGateway,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """Pipeline mestre de emissão documental com normalização e persistência.

        Args:
            ui_data (Dict[str, Any]): Metadados puros da interface.
            asset_list (List[Dict[str, Any]]): Inventário selecionado.
            loop (asyncio.AbstractEventLoop): Executor de tarefas.
            gateway (ITermGateway): Gateway de despacho documental.
            progress_callback (Optional[Callable]): Sinalizador visual de progresso.

        Returns:
            Dict[str, Any]: Status final da geração e caminhos dos logs.
        """

        def update_progress(pct: int, msg: str) -> None:
            fire_progress(progress_callback, pct, msg)

        try:
            update_progress(5, "Inicializando motor de geração via Gateway...")

            # --- 3.1. Classificação e Regras ---
            op_val: str = ui_data.get("operacao", "Entrega")
            name_val: Optional[str] = ui_data.get("nome")
            obs_val: str = ui_data.get("obs", "") or ""

            if not name_val:
                return {"sucesso": False, "msg": "Nome do colaborador é obrigatório."}

            op_db_final: str = classify_operation_type(
                op_val, obs_val, KEYWORDS_MOVEMENT
            )
            config: Dict[str, Any] = load_setting()

            # --- 3.2. Normalização de DTO (Data Transfer Object) ---
            word_list: List[Dict[str, Any]] = []
            for item in asset_list:
                tag: str = item.get("patrimonio", "S/N")
                visual_desc: str = item.get("descricao_visual", item.get("modelo", ""))

                if tag not in ["S/N", "N/A"]:
                    full_desc: str = (
                        f"{item.get('tipo', '')} {item.get('fabricante', '')} - "
                        f"{item.get('modelo', '')} - SN: {item.get('serial', '')}"
                    )
                else:
                    full_desc = visual_desc

                word_list.append(
                    {
                        "patrimonio": tag if tag != "S/N" else "N/A",
                        "descricao_completa": full_desc,
                        "qtd": item.get("qtd", "1"),
                        "modelo": item.get("modelo", ""),
                        "serial": item.get("serial", ""),
                        "fabricante": item.get("fabricante", ""),
                        "tipo": item.get("tipo", ""),
                    }
                )

            # --- 3.3. Montagem do Contexto do Template ---
            template_data: Dict[str, Any] = {
                "chamado": ui_data.get("chamado") or "S_N",
                "nome": name_val,
                "area": ui_data.get("area"),
                "observacoes": obs_val,
                "data": get_full_date_text(),
                "lista_ativos": word_list,
                "x_entrega": "X" if op_val == "Entrega" else " ",
                "x_devolucao": "X" if op_val == "Devolução" else " ",
                "x_emprestimo": "X" if op_val == "Empréstimo" else " ",
                "tipo_operacao_db": op_db_final,
            }

            # --- 3.4. Delegação ao Gateway Concreto ---
            return await gateway.process_term(
                ui_data=ui_data,
                asset_list=asset_list,
                template_data=template_data,
                config=config,
                loop=loop,
                progress_callback=progress_callback,
            )

        except Exception as e:
            return {"sucesso": False, "msg": f"Erro Controlador: {str(e)}"}
