"""
Módulo de Controle do Dashboard (Controller Layer).

Orquestra a agregação de métricas, filtros temporais e processamento
de séries analíticas para a visualização executiva de dados.
"""

# ==============================================================================
# 1. IMPORTS E DEPENDÊNCIAS
# ==============================================================================

import math
from datetime import datetime
from typing import Any, Dict, List

from core.settings import MONTH_MAP, OP_STYLES
from data.gold.database import get_available_dates, get_dashboard

# ==============================================================================
# 2. CONTROLADOR ANALÍTICO
# ==============================================================================


class DashboardController:
    """Orquestrador do processamento de dados para o Dashboard."""

    def __init__(self) -> None:
        """Inicializa o controlador com as dimensões de tempo da base.

        Carrega anos e meses disponíveis para popular os seletores de filtro
        da interface.
        """
        self.years_db: List[str]
        self.months_db: List[str]
        self.years_db, self.months_db = get_available_dates()

        current_year_str: str = str(datetime.now().year)
        if current_year_str not in self.years_db:
            self.years_db.append(current_year_str)
            self.years_db.sort(reverse=True)

        self.filters: Dict[str, Any] = {
            "modo": "ano_atual",
            "mes": self.months_db[0] if self.months_db else None,
            "ano": self.years_db[0] if self.years_db else None,
            "op_type": "Geral",
            "sector_type": "todos",
            "asset_mode": "saidas",
            "comparar_anos": False,
            "compare_years": [],
        }

    # --- 2.1. Controle de Estado dos Filtros ---

    def set_filter(self, key: str, value: Any) -> None:
        """Atualiza uma chave específica do dicionário de filtros.

        Args:
            key (str): Chave do filtro (ex: "mes", "op_type").
            value (Any): Valor a ser definido.
        """
        self.filters[key] = value

    def reset_filters(self) -> None:
        """Restaura os filtros do Dashboard para o estado original padrão."""
        self.filters["modo"] = "ano_atual"
        self.filters["sector_type"] = "todos"
        self.filters["asset_mode"] = "saidas"
        self.filters["op_type"] = "Geral"
        self.filters["comparar_anos"] = False
        self.filters["compare_years"] = []

    # --- 2.2. Agregação e Processamento de Métricas ---

    def get_dashboard_package(self) -> Dict[str, Any]:
        """Consolida o pacote de dados completo para renderização na View.

        Realiza cálculos de percentuais, rankings de setores e categorias,
        além de formatar a timeline para os gráficos.

        Returns:
            Dict[str, Any]: Dicionário estruturado com KPIs, Donut, Setores e Ativos.
        """
        query_params: Dict[str, Any] = {
            "modo": self.filters["modo"],
            "asset_mode": self.filters["asset_mode"],
        }

        if self.filters["comparar_anos"]:
            query_params["modo"] = "comparacao"

        if self.filters["mes"] and self.filters["mes"] not in [
            "todos",
            "Todos",
            "Geral",
        ]:
            mes_nome: str = self.filters["mes"]
            if mes_nome in MONTH_MAP:
                query_params["mes"] = f"{MONTH_MAP[mes_nome]:02d}"
            else:
                query_params["mes"] = mes_nome

        if self.filters["ano"] and self.filters["ano"] not in [
            "todos",
            "Todos",
            "Geral",
        ]:
            query_params["ano"] = self.filters["ano"]

        if self.filters["op_type"] and self.filters["op_type"] not in [
            "todos",
            "Todos",
            "Geral",
        ]:
            query_params["op_type"] = self.filters["op_type"]

        if self.filters["sector_type"] and self.filters["sector_type"] not in [
            "todos",
            "Todos",
            "Geral",
        ]:
            query_params["sector_type"] = self.filters["sector_type"]

        raw_data: Dict[str, Any] = get_dashboard(query_params)
        if not raw_data:
            return {}

        dto: Dict[str, Any] = {}

        # --- 2.3. Processamento de KPIs principais ---
        kpi_db: Dict[str, int] = raw_data.get("kpis", {})
        kpi_metrics: Dict[str, int] = {k: kpi_db.get(k, 0) for k in OP_STYLES.keys()}
        kpi_metrics["Total"] = sum(kpi_db.values())
        dto["kpis"] = kpi_metrics

        # --- 2.4. Processamento do Gráfico de Rosca ---
        ops: List[str] = ["Entrega", "Devolução", "Empréstimo", "Movimentação"]
        grand_total: int = sum([kpi_metrics.get(x, 0) for x in ops])
        donut_data: List[Dict[str, Any]] = []
        if grand_total > 0:
            for k in ops:
                val: int = kpi_metrics.get(k, 0)
                if val > 0:
                    pct: int = int(val / grand_total * 100)
                    donut_data.append({"op": k, "value": val, "pct": pct})
        dto["donut"] = donut_data

        # --- 2.5. Processamento dos Top Setores ---
        top_sectors: List[Any] = raw_data.get("setores", [])[:5]
        dto["setores"] = []
        if top_sectors:
            total_sectors: float = float(
                sum(
                    item[1]
                    for item in raw_data.get("setores", [])
                    if isinstance(item, tuple) and len(item) == 2
                )
            )
            for item in top_sectors:
                if isinstance(item, tuple) and len(item) == 2:
                    pct_sec: float = (
                        (item[1] / total_sectors * 100) if total_sectors > 0 else 0.0
                    )
                    dto["setores"].append(
                        {
                            "name": item[0],
                            "display": f"{pct_sec:.1f}%",
                            "ratio": pct_sec / 100.0,
                        }
                    )

        # --- 2.6. Processamento dos Top Ativos ---
        asset_stats: Dict[str, int] = raw_data.get(
            "ativos_metricas", {"Notebook": 0, "Desktop": 0, "Monitor": 0}
        )
        total_assets: int = sum(asset_stats.values())
        categories: List[str] = ["Notebook", "Desktop", "Monitor"]
        dto["ativos"] = []
        for cat in categories:
            count: int = asset_stats.get(cat, 0)
            if count > 0:
                pct_ast: float = (
                    (count / total_assets * 100) if total_assets > 0 else 0.0
                )
                dto["ativos"].append(
                    {
                        "name": cat,
                        "display": f"{pct_ast:.1f}%",
                        "ratio": pct_ast / 100.0,
                    }
                )

        # --- 2.7. Processamento da Timeline ---
        timeline_map: Dict[str, List[int]] = {}
        for row in raw_data.get("timeline", []):
            if not row or len(row) < 3:
                continue
            year_key: str = str(row[0]) if row[0] is not None else "Unknown"
            month_idx: int = int(row[1]) - 1
            count_tl: int = row[2]
            if year_key not in timeline_map:
                timeline_map[year_key] = [0] * 12
            timeline_map[year_key][month_idx] += count_tl

        years_to_plot: List[str]
        if self.filters["comparar_anos"]:
            years_to_plot = sorted(list(set(self.filters["compare_years"])))
        else:
            years_to_plot = sorted([str(k) for k in timeline_map.keys()])

        series_data: List[Dict[str, Any]] = []
        peak_val: int = 0
        for y_key in years_to_plot:
            monthly_vals: List[int] = timeline_map.get(y_key, [0] * 12)
            peak_val = max(peak_val, max(monthly_vals) if monthly_vals else 0)
            series_data.append({"year": y_key, "data": monthly_vals})

        y_limit: int = math.ceil((peak_val * 1.1) / 5) * 5 or 10
        dto["timeline"] = {
            "series": series_data,
            "y_limit": y_limit,
            "interval": math.ceil(y_limit / 5) if y_limit > 0 else 1,
        }

        dto["ticker"] = raw_data.get("ticker", [])

        return dto
