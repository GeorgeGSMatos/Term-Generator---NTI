"""
Módulo de Simulação (Core Layer).

Define as interfaces (contratos) fundamentais e implementações mockadas
para desenvolvimento isolado e testes sem dependências de infraestrutura real.
"""

# ==============================================================================
# 1. IMPORTS E DEPENDÊNCIAS
# ==============================================================================

import asyncio
import os
import random
from abc import ABC, abstractmethod
from functools import partial
from typing import Any, Callable, Dict, List, Optional

# --- 1.1. Utilitários de Teste e Core ---
from core.testing_utils import setup_test_environment
from core.utils import fire_progress, sanitize_filename

# --- 1.2. Infraestrutura e Persistência ---
from data.gold.database import save_to_history
from data.silver.data_cleaner import normalize_item

# ==============================================================================
# 2. INTERFACES
# ==============================================================================


class IAssetGateway(ABC):
    """Contrato base para provedores de busca de ativos e inventário."""

    @abstractmethod
    async def find_asset(
        self, asset_tag: str, loop: asyncio.AbstractEventLoop
    ) -> Dict[str, Any]:
        """Busca os metadados físicos de um tombamento patrimonial.

        Args:
            asset_tag (str): A tag patrimonial identificadora.
            loop (asyncio.AbstractEventLoop): Gancho de thread assíncrona.

        Returns:
            Dict[str, Any]: Objeto padronizado com status e dados consolidados.
        """


class ITermGateway(ABC):
    """Contrato base para processamento e emissão de Termos Documentais."""

    @abstractmethod
    async def process_term(
        self,
        ui_data: Dict[str, Any],
        asset_list: List[Dict[str, Any]],
        template_data: Dict[str, Any],
        config: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """Processa a emissão documental acionando motores de geração.

        Args:
            ui_data (Dict[str, Any]): Dados coletados da interface gráfica.
            asset_list (List[Dict[str, Any]]): Itens do inventário selecionados.
            template_data (Dict[str, Any]): Contexto para renderização de documentos.
            config (Dict[str, Any]): Dicionário global de configurações.
            loop (asyncio.AbstractEventLoop): Loop para paralelismo I/O.
            progress_callback (Optional[Callable]): Injetor de feedback na UI.

        Returns:
            Dict[str, Any]: Resultado da operação com caminhos de arquivos simulados.
        """


# ==============================================================================
# 3. IMPLEMENTAÇÕES DE SIMULAÇÃO
# ==============================================================================


class SimulatedAssetGateway(IAssetGateway):
    """Estratégia de Desenvolvimento que retorna dados sintéticos randômicos."""

    async def find_asset(
        self, asset_tag: str, loop: asyncio.AbstractEventLoop
    ) -> Dict[str, Any]:
        """Implementação Mock: gera dados fake após delay artificial.

        Args:
            asset_tag (str): Patrimônio fornecido para busca.
            loop (asyncio.AbstractEventLoop): Loop de eventos.

        Returns:
            Dict[str, Any]: Dados simulados ou erro controlado (se tag contiver 'ERRO').
        """
        await asyncio.sleep(0.5)

        if "404" in asset_tag or "ERRO" in asset_tag.upper():
            return {"status": "erro", "msg": "Simulação de Falha (Modo Teste)"}

        # --- 3.1. Dicionário de Ativos Randômicos ---
        mock_types: List[tuple[str, str]] = [
            ("Notebook", "Dell Latitude 5420"),
            ("Desktop", "Dell Optiplex 7050"),
            ("Monitor", "Samsung T350 24''"),
            ("Smartphone", "Samsung Galaxy S23"),
            ("Periférico", "Dock Station Dell WD19"),
        ]

        chosen_type, chosen_model = random.choice(mock_types)
        sim_tag: str = asset_tag if asset_tag else f"SIM-{random.randint(100, 999)}"

        raw_data = {
            "tipo": chosen_type,
            "fabricante": "Genérico",
            "modelo": f"{chosen_model} - [TESTE]",
            "serial": f"SN{random.randint(1000, 9999)}X",
            "patrimonio": sim_tag,
            "qtd": "1",
        }

        clean_data = normalize_item(raw_data)
        return {"status": "sucesso", "data": clean_data}


class SimulatedTermGateway(ITermGateway):
    """Estratégia de Desenvolvimento para geração documental efêmera (Sandbox)."""

    async def process_term(
        self,
        ui_data: Dict[str, Any],
        asset_list: List[Dict[str, Any]],
        template_data: Dict[str, Any],
        config: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """Gera artefatos em sandbox local sem impactar infra de produção.

        Args:
            ui_data (Dict[str, Any]): Dados da UI.
            asset_list (List[Dict[str, Any]]): Itens do termo.
            template_data (Dict[str, Any]): Dados para o template.
            config (Dict[str, Any]): Configurações do sistema.
            loop (asyncio.AbstractEventLoop): Executor assíncrono.
            progress_callback (Optional[Callable]): Callback de progresso.

        Returns:
            Dict[str, Any]: Resultado simulado com sucesso.
        """
        try:
            name_val: str = ui_data.get("nome", "Sem Nome")

            # --- 3.2. Setup de Diretório Temporário ---
            fire_progress(
                progress_callback,
                20,
                "Modo Simulação: Limpando ambiente de teste...",
            )
            dest_folder = setup_test_environment()
            base_name = f"SIMULACAO - {sanitize_filename(name_val)}"

            docx_path = os.path.join(dest_folder, f"{base_name}.docx")
            pdf_path = os.path.join(dest_folder, f"{base_name}.pdf")

            await asyncio.sleep(0.5)

            # --- 3.3. Materialização de Documento Word Mock ---
            fire_progress(progress_callback, 50, "Simulando Geração de Doc...")
            await asyncio.sleep(0.3)

            with open(docx_path, "w", encoding="utf-8") as f:
                f.write("Isto é um termo simulado de teste. Nenhuma api acionada.")

            # --- 3.4. Criação de Binário PDF Mínimo ---
            fire_progress(progress_callback, 80, "Simulando Motor PDF...")
            await asyncio.sleep(0.3)

            min_pdf = (
                b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj "
                b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
                b"3 0 obj<</Type/Page/MediaBox[0 0 3 3]>>endobj xref\n"
                b"0 4\n0000000000 65535 f \n0000000009 00000 n \n"
                b"0000000052 00000 n \n0000000101 00000 n \n"
                b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n147\n%%EOF\n"
            )
            with open(pdf_path, "wb") as f:
                f.write(min_pdf)

            # --- 3.5. Persistência Simulada no Banco de Dados ---
            fire_progress(
                progress_callback,
                95,
                "Sincronizando histórico de testes no Local DB...",
            )
            await loop.run_in_executor(
                None,
                partial(save_to_history, template_data, asset_list, docx_path),
            )

            fire_progress(progress_callback, 100, "Concluído (SIMULADO)!")

            return {
                "sucesso": True,
                "msg": "Termo gerado com sucesso [MODO SIMULADO]!",
                "paths": {
                    "docx": docx_path,
                    "pdf": pdf_path,
                    "pasta": dest_folder,
                    "nome_base": base_name,
                },
                "config": config,
            }

        except Exception as e:
            return {"sucesso": False, "msg": f"Erro interno (Simulado): {str(e)}"}
