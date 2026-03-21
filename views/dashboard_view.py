"""
Módulo de Visualização Analitica (View Layer).

Centraliza a lógica de monitoramento de métricas, gráficos e histórico de
atividades recentes (Dashboard) da aplicação.
"""

# ==============================================================================
# 1. IMPORTS E DEPENDÊNCIAS
# ==============================================================================
import traceback
from datetime import datetime
from typing import Any, Dict, Optional, Tuple, Union

import flet as ft

import core.strings as S

# --- 1.2. Sub-módulos SQL e Controller MVC ---
from controllers.dashboard_controller import DashboardController

# --- 1.1. Infraestrutura Core e Dicionários ---
from core.settings import COLORS, OP_STYLES, get_header_color, load_setting
from core.utils import clean_filename, format_ticker_time
from data.state import AppState

# --- 1.3. Componentes Sintéticos da View Layer ---
from views.ui import (
    create_filter_dropdown,
    create_hero_header,
    create_progress_bar_row,
    create_standard_card,
    scale_dd,
)

# ==============================================================================
# 2. FABRICANTES DE SUB-COMPONENTES MICRO
# ==============================================================================


def _create_kpi_card(
    title: str,
    value: int,
    icon: str,
    icon_color: str,
    bg_color: str = COLORS.get("card_bg", "white"),
) -> ft.Container:
    """Micro Elemento Flex Box contendo Números e Ícones Rápidos Absolutos."""
    return ft.Container(
        expand=True,
        margin=ft.margin.symmetric(horizontal=8),
        padding=20,
        bgcolor=COLORS.get("card_bg", "white"),
        border_radius=15,
        shadow=ft.BoxShadow(
            blur_radius=10, color=ft.colors.with_opacity(0.05, "black")
        ),
        content=ft.Row(
            controls=[
                ft.Container(
                    content=ft.Icon(name=icon, color=icon_color, size=28),
                    bgcolor=bg_color,
                    padding=12,
                    border_radius=50,
                ),
                ft.Column(
                    spacing=2,
                    expand=True,
                    controls=[
                        ft.Text(
                            str(value),
                            size=28,
                            weight=ft.FontWeight.BOLD,
                            color=COLORS.get("text", "black"),
                        ),
                        ft.Text(
                            title,
                            size=13,
                            color=COLORS.get("text_secondary", "grey"),
                            no_wrap=True,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                ),
            ]
        ),
    )


def _build_ticker_item(entry: Tuple) -> Optional[ft.Control]:
    """Sintetiza um Array de Audit Log Real (SQL Tuple) em Micro List Tile (Ticker UX)."""
    try:
        time_raw = str(entry[0])
        h_fmt, d_fmt = format_ticker_time(time_raw)

        op_type = str(entry[1])
        ticket_id = str(entry[2])
        colab_name = str(entry[3])
        original_filename = str(entry[4]) if len(entry) > 4 else ""

        op_style = OP_STYLES.get(op_type, OP_STYLES["Desconhecido"])

        if original_filename and original_filename.lower() not in ["none", ""]:
            display_text = clean_filename(original_filename)
        else:
            display_text = f"{op_type} - {colab_name}"

        return ft.Container(
            padding=12,
            bgcolor=COLORS.get("input_bg", "white"),
            border_radius=8,
            border=ft.border.all(1, COLORS.get("border", "lightgrey")),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.START,
                spacing=8,
                controls=[
                    ft.Column(
                        width=45,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=0,
                        controls=[
                            ft.Text(
                                h_fmt,
                                weight=ft.FontWeight.BOLD,
                                size=14,
                                color=COLORS.get("text", "black"),
                            ),
                            ft.Text(
                                d_fmt,
                                size=11,
                                color=COLORS.get("text_secondary", "grey"),
                            ),
                        ],
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.START,
                        spacing=10,
                        expand=True,
                        controls=[
                            ft.Container(
                                padding=10,
                                border_radius=50,
                                bgcolor=op_style.get(
                                    "bg", COLORS.get("card_bg", "white")
                                ),
                                content=ft.Icon(
                                    name=op_style["icon"],
                                    size=18,
                                    color=op_style["color"],
                                ),
                            ),
                            ft.Column(
                                expand=True,
                                spacing=2,
                                controls=[
                                    ft.Text(
                                        display_text,
                                        weight=ft.FontWeight.BOLD,
                                        size=13,
                                        color=COLORS.get("text", "black"),
                                        no_wrap=True,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    ft.Text(
                                        f"{S.LABEL_CHAMADO}: {ticket_id}",
                                        size=12,
                                        color=COLORS.get("text_secondary", "grey"),
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        )
    except (IndexError, TypeError):
        return None


def _create_dashboard_card(
    title: str, content: ft.Control, expand: Union[bool, int] = False
) -> ft.Container:
    """Padroniza Encadernamento Visual de todos os Wrappers Brancos do Dashboard."""
    return create_standard_card(
        expand=expand,
        padding=25,
        content=ft.Column(
            spacing=0,
            controls=[
                ft.Text(
                    title.upper(),
                    size=14,
                    weight=ft.FontWeight.BOLD,
                    color=COLORS.get("text", "black"),
                ),
                ft.Divider(height=20, color="transparent"),
                content,
            ],
        ),
    )


def _generate_theme_gradient() -> list[str]:
    """Retorna a paleta de degrade baseada no tema ativo (Produção ou Simulação/Teste)."""
    return COLORS.get(
        "chart_assets_palette",
        ["#002F6C", "#004EA8", "#0072C6", "#4FA6E0", "#42A5F5", "#BBDEFB"],
    )


# ==============================================================================
# 3. FÁBRICA PRINCIPAL DA VISUALIZAÇÃO
# ==============================================================================


def build_dashboard_tab(page: ft.Page, app_state: AppState) -> ft.Column:
    """Invoca o Flet para plotar a página inteira de Gráficos Reativos Analytics."""

    current_config: Dict[str, Any] = load_setting()
    is_test_mode: bool = current_config.get("modo_teste", False)

    # --- 3.1. Instância do Controller MVC ---
    controller = DashboardController()
    years_db, months_db = controller.years_db, controller.months_db

    # --- 3.2. Definições de Entidades com ft.Ref ---
    ref_container_cards_kpi = ft.Ref[ft.Row]()
    ref_chart_donut = ft.Ref[ft.PieChart]()
    ref_legend_donut = ft.Ref[ft.Row]()
    ref_coluna_setores_custom = ft.Ref[ft.Column]()
    ref_coluna_ativos_horizontal = ft.Ref[ft.Column]()
    ref_chart_timeline = ft.Ref[ft.LineChart]()
    ref_legenda_anos = ft.Ref[ft.Row]()
    ref_lista_ticker = ft.Ref[ft.ListView]()

    ref_dropdown_filtro_global = ft.Ref[ft.Dropdown]()
    ref_dropdown_mes = ft.Ref[ft.Dropdown]()
    ref_dropdown_ano = ft.Ref[ft.Dropdown]()
    ref_dropdown_setores_tipo = ft.Ref[ft.Dropdown]()
    ref_dropdown_ativos = ft.Ref[ft.Dropdown]()
    ref_dropdown_timeline = ft.Ref[ft.Dropdown]()

    ref_chk_comparar = ft.Ref[ft.Checkbox]()
    ref_row_dropdowns = ft.Ref[ft.Row]()
    ref_btn_add_year = ft.Ref[ft.IconButton]()
    ref_btn_remove_year = ft.Ref[ft.IconButton]()
    ref_container_comparacao = ft.Ref[ft.Row]()
    ref_container_datas = ft.Ref[ft.Row]()

    # --- 3.3. Funções de Controle UI e Callbacks ---

    def _update_date_filter_visibility() -> None:
        """Mostra Dropdown Mês/Ano apenas se Específico estiver setado."""
        if ref_container_datas.current and ref_dropdown_filtro_global.current:
            ref_container_datas.current.visible = (
                ref_dropdown_filtro_global.current.value == "especifico"
            )
            load_dashboard_data(e=True)

    def _toggle_comparison_mode() -> None:
        """Gerencia Estado Oculto dos Selects Dinâmicos de Ano Comparado."""
        if ref_chk_comparar.current:
            is_on = ref_chk_comparar.current.value
            if ref_row_dropdowns.current:
                ref_row_dropdowns.current.visible = is_on
                if ref_btn_add_year.current:
                    ref_btn_add_year.current.visible = (
                        is_on and len(ref_row_dropdowns.current.controls) < 5
                    )
                if ref_btn_remove_year.current:
                    ref_btn_remove_year.current.visible = (
                        is_on and len(ref_row_dropdowns.current.controls) > 1
                    )
            if ref_dropdown_filtro_global.current:
                ref_dropdown_filtro_global.current.disabled = is_on
                ref_dropdown_filtro_global.current.update()
            if ref_container_comparacao.current:
                ref_container_comparacao.current.update()
            load_dashboard_data(e=True)

    def add_compare_year(e=None, initial_val=None):
        if (
            not ref_row_dropdowns.current
            or len(ref_row_dropdowns.current.controls) >= 5
        ):
            return

        year_opts = [(str(y), str(y)) for y in years_db]
        dd = scale_dd(
            create_filter_dropdown(
                "",
                year_opts,
                value=initial_val or str(datetime.now().year),
                width=100,
                on_change=lambda ev: load_dashboard_data(e=True),
            )
        )
        ref_row_dropdowns.current.controls.append(dd)

        if len(ref_row_dropdowns.current.controls) >= 5 and ref_btn_add_year.current:
            ref_btn_add_year.current.visible = False

        if ref_btn_remove_year.current:
            ref_btn_remove_year.current.visible = len(
                ref_row_dropdowns.current.controls
            ) > 1 and getattr(ref_chk_comparar.current, "value", False)

        if ref_btn_add_year.current:
            ref_btn_add_year.current.visible = len(
                ref_row_dropdowns.current.controls
            ) < 5 and getattr(ref_chk_comparar.current, "value", False)

        if e and ref_container_comparacao.current:
            ref_container_comparacao.current.update()
            load_dashboard_data(e=True)

    def remove_compare_year(e=None):
        if (
            not ref_row_dropdowns.current
            or len(ref_row_dropdowns.current.controls) <= 1
        ):
            return

        ref_row_dropdowns.current.controls.pop()

        if ref_btn_add_year.current:
            ref_btn_add_year.current.visible = True

        if ref_btn_remove_year.current:
            ref_btn_remove_year.current.visible = (
                len(ref_row_dropdowns.current.controls) > 1
            )

        if e and ref_container_comparacao.current:
            ref_container_comparacao.current.update()
            load_dashboard_data(e=True)

    def reset_filters(e: ft.ControlEvent) -> None:
        """Limpa toda a bagunça de cruzamento e reseta a Factory Master."""
        controller.reset_filters()

        if ref_dropdown_filtro_global.current:
            ref_dropdown_filtro_global.current.value = "ano_atual"
            ref_dropdown_filtro_global.current.disabled = False
        if ref_container_datas.current:
            ref_container_datas.current.visible = False
        if ref_dropdown_setores_tipo.current:
            ref_dropdown_setores_tipo.current.value = "todos"
        if ref_dropdown_ativos.current:
            ref_dropdown_ativos.current.value = "saidas"
        if ref_dropdown_timeline.current:
            ref_dropdown_timeline.current.value = "Geral"
        if ref_chk_comparar.current:
            ref_chk_comparar.current.value = False

        if ref_row_dropdowns.current:
            ref_row_dropdowns.current.visible = False
            ref_row_dropdowns.current.controls = ref_row_dropdowns.current.controls[:2]

            last_year_calc = str(int(datetime.now().year) - 1)
            if len(ref_row_dropdowns.current.controls) > 0:
                ref_row_dropdowns.current.controls[0].value = str(datetime.now().year)
            if len(ref_row_dropdowns.current.controls) > 1:
                ref_row_dropdowns.current.controls[1].value = (
                    last_year_calc if len(years_db) > 1 else str(datetime.now().year)
                )

        if ref_btn_add_year.current:
            ref_btn_add_year.current.visible = False

        if ref_btn_remove_year.current:
            ref_btn_remove_year.current.visible = False

        for ctrl in [
            ref_dropdown_filtro_global.current,
            ref_container_datas.current,
            ref_dropdown_setores_tipo.current,
            ref_dropdown_ativos.current,
            ref_dropdown_timeline.current,
            ref_chk_comparar.current,
            ref_container_comparacao.current,
        ]:
            if ctrl:
                ctrl.update()

        load_dashboard_data(e=True)

    def sync_filters_to_controller():
        """Passa o estado da View para o Controller."""
        if ref_dropdown_filtro_global.current:
            controller.set_filter("modo", ref_dropdown_filtro_global.current.value)
        if ref_dropdown_mes.current:
            controller.set_filter("mes", ref_dropdown_mes.current.value)
        if ref_dropdown_ano.current:
            controller.set_filter("ano", ref_dropdown_ano.current.value)
        if ref_dropdown_timeline.current:
            controller.set_filter("op_type", ref_dropdown_timeline.current.value)
        if ref_dropdown_setores_tipo.current:
            controller.set_filter(
                "sector_type", ref_dropdown_setores_tipo.current.value
            )
        if ref_dropdown_ativos.current:
            controller.set_filter("asset_mode", ref_dropdown_ativos.current.value)
        if ref_chk_comparar.current:
            controller.set_filter("comparar_anos", ref_chk_comparar.current.value)

        selected_compare_years = []
        if (
            ref_chk_comparar.current
            and ref_chk_comparar.current.value
            and ref_row_dropdowns.current
        ):
            selected_compare_years = [
                dd.value for dd in ref_row_dropdowns.current.controls if dd.value
            ]
        controller.set_filter("compare_years", selected_compare_years)

    def load_dashboard_data(e: Optional[Any] = None) -> None:
        """Carrega e popula os dados através do DashboardController."""
        try:
            sync_filters_to_controller()
            dto = controller.get_dashboard_package()
            if not dto:
                return

            # --- 3.3.1. Popula Plot 1: KPIs Rápidos ---
            kpi_metrics = dto.get("kpis", {})
            cards_list = [
                _create_kpi_card(
                    "Total",
                    kpi_metrics.get("Total", 0),
                    ft.icons.DATA_USAGE,
                    COLORS.get("blue_info", "blue"),
                    COLORS.get("primary_light", "lightblue"),
                )
            ]

            for op_key in ["Entrega", "Devolução", "Empréstimo", "Movimentação"]:
                val = kpi_metrics.get(op_key, 0)
                st = OP_STYLES.get(op_key, OP_STYLES["Desconhecido"])
                cards_list.append(
                    _create_kpi_card(
                        f"{op_key}",
                        val,
                        st["icon"],
                        st["color"],
                        st.get("bg", COLORS.get("card_bg", "white")),
                    )
                )

            if ref_container_cards_kpi.current:
                ref_container_cards_kpi.current.controls = cards_list

            # --- 3.3.2. Popula Plot 2: Donut Chart ---
            donut_data = dto.get("donut", [])
            donut_palette = COLORS.get(
                "chart_assets_palette", ["#002F6C", "#004EA8", "#0072C6", "#4FA6E0"]
            )
            pie_palette = {
                "Entrega": donut_palette[0 % len(donut_palette)],
                "Devolução": donut_palette[1 % len(donut_palette)],
                "Empréstimo": donut_palette[2 % len(donut_palette)],
                "Movimentação": donut_palette[3 % len(donut_palette)],
            }
            if ref_chart_donut.current:
                ref_chart_donut.current.sections = []
                for item in donut_data:
                    cor = pie_palette.get(item["op"], COLORS.get("primary", "blue"))
                    ref_chart_donut.current.sections.append(
                        ft.PieChartSection(
                            item["value"],
                            color=cor,
                            radius=40,
                            title=f"{item['pct']}%",
                            title_style=ft.TextStyle(
                                size=12,
                                color=COLORS.get("text_inverse", "white"),
                                weight=ft.FontWeight.BOLD,
                            ),
                        )
                    )

            if ref_legend_donut.current:
                ref_legend_donut.current.controls = [
                    ft.Row(
                        [
                            ft.Container(
                                width=12,
                                height=12,
                                bgcolor=pie_palette.get(k["op"], "black"),
                                border_radius=3,
                            ),
                            ft.Text(
                                k["op"][:3].upper(),
                                size=13,
                                color=COLORS.get("text_secondary", "grey"),
                                weight="bold",
                            ),
                        ]
                    )
                    for k in donut_data
                ]

            # --- 3.3.3. Popula Plot 3: Setores Bar ---
            if ref_coluna_setores_custom.current:
                ref_coluna_setores_custom.current.controls.clear()
                setores = dto.get("setores", [])
                palette = _generate_theme_gradient()
                if setores:
                    for i, s in enumerate(setores):
                        bar_color = palette[i % len(palette)]
                        ref_coluna_setores_custom.current.controls.append(
                            create_progress_bar_row(
                                s["name"],
                                s["display"],
                                s["ratio"],
                                bar_color,
                            )
                        )
                else:
                    ref_coluna_setores_custom.current.controls.append(
                        ft.Text(
                            S.PLACEHOLDER_NO_SECTOR_DATA,
                            italic=True,
                            color=COLORS.get("text_secondary", "grey"),
                            size=14,
                        )
                    )

            # --- 3.3.4. Popula Plot 4: Ativos Bar ---
            if ref_coluna_ativos_horizontal.current:
                ref_coluna_ativos_horizontal.current.controls.clear()
                ativos = dto.get("ativos", [])
                palette = _generate_theme_gradient()
                if ativos:
                    for i, a in enumerate(ativos):
                        bar_color = palette[i % len(palette)]
                        ref_coluna_ativos_horizontal.current.controls.append(
                            create_progress_bar_row(
                                a["name"], a["display"], a["ratio"], bar_color
                            )
                        )
                else:
                    ref_coluna_ativos_horizontal.current.controls.append(
                        ft.Text(
                            S.PLACEHOLDER_NO_ASSET_DATA,
                            italic=True,
                            color=COLORS.get("text_secondary", "grey"),
                            size=14,
                        )
                    )

            # --- 3.3.5. Popula Plot 5: Timeline ---
            if ref_chart_timeline.current and ref_legenda_anos.current:
                timeline = dto.get("timeline", {})
                series_list = []
                ref_legenda_anos.current.controls.clear()

                year_colors = _generate_theme_gradient()

                for c_idx, s in enumerate(timeline.get("series", [])):
                    y_key = s["year"]
                    monthly_vals = s["data"]
                    line_color = year_colors[c_idx % len(year_colors)]

                    ref_legenda_anos.current.controls.append(
                        ft.Row(
                            [
                                ft.Container(
                                    width=12,
                                    height=12,
                                    bgcolor=line_color,
                                    border_radius=3,
                                ),
                                ft.Text(
                                    y_key,
                                    size=13,
                                    weight=ft.FontWeight.BOLD,
                                    color=COLORS.get("text_secondary", "grey"),
                                ),
                            ],
                            spacing=5,
                        )
                    )
                    series_list.append(
                        ft.LineChartData(
                            stroke_width=4,
                            color=line_color,
                            curved=True,
                            stroke_cap_round=True,
                            point=True,
                            below_line_bgcolor=ft.colors.with_opacity(0.05, line_color),
                            data_points=[
                                ft.LineChartDataPoint(i, val)
                                for i, val in enumerate(monthly_vals)
                            ],
                        )
                    )

                ref_chart_timeline.current.max_y = timeline.get("y_limit", 10)
                ref_chart_timeline.current.left_axis.labels_interval = timeline.get(
                    "interval", 2
                )
                ref_chart_timeline.current.data_series = series_list

            # --- 3.3.6. Popula Plot 6: Barra Lateral do Contador de Atividades do Microfeed ---
            if ref_lista_ticker.current:
                ref_lista_ticker.current.controls.clear()
                ticker = dto.get("ticker", [])
                for entry in ticker:
                    item = _build_ticker_item(entry)
                    if item:
                        ref_lista_ticker.current.controls.append(item)

                if not ref_lista_ticker.current.controls:
                    ref_lista_ticker.current.controls.append(
                        ft.Container(
                            padding=20,
                            alignment=ft.alignment.center,
                            content=ft.Text(
                                S.PLACEHOLDER_NO_ACTIVITY,
                                size=14,
                                color=COLORS.get("text_secondary", "grey"),
                                italic=True,
                            ),
                        )
                    )

            if e:
                page.update()

        except Exception:
            print(
                "❌ Erro Crítico no Dashboard Analítico. Reportado no Log do Terminal."
            )
            traceback.print_exc()

    # --- 3.4. Instanciação e Montagem da Flet UI Structure ---

    global_opts = [
        ("tudo", "Todo o Período"),
        ("ano_atual", "Este Ano"),
        ("mes_atual", "Este Mês"),
        ("30_dias", "Últimos 30 Dias"),
        ("hoje", "Hoje"),
        ("especifico", "Mês/Ano Específico"),
    ]
    dropdown_filtro_global = scale_dd(
        create_filter_dropdown(
            "",
            global_opts,
            value="ano_atual",
            width=200,
            on_change=lambda e: _update_date_filter_visibility(),
            ref=ref_dropdown_filtro_global,
        )
    )

    month_opts = [(m, m) for m in months_db]
    dropdown_mes = scale_dd(
        create_filter_dropdown(
            "Mês",
            month_opts,
            value=months_db[0] if months_db else None,
            width=150,
            on_change=lambda e: load_dashboard_data(e=True),
            ref=ref_dropdown_mes,
        )
    )

    year_opts = [(str(y), str(y)) for y in years_db]
    dropdown_ano = scale_dd(
        create_filter_dropdown(
            "Ano",
            year_opts,
            value=str(years_db[0]) if years_db else None,
            width=120,
            on_change=lambda e: load_dashboard_data(e=True),
            ref=ref_dropdown_ano,
        )
    )

    container_datas = ft.Row(
        ref=ref_container_datas,
        visible=False,
        alignment=ft.MainAxisAlignment.END,
        spacing=10,
        controls=[dropdown_mes, dropdown_ano],
    )

    container_cards_kpi = ft.Row(
        ref=ref_container_cards_kpi,
        spacing=0,
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    chart_donut = ft.PieChart(
        ref=ref_chart_donut,
        sections=[],
        sections_space=3,
        center_space_radius=45,
        height=200,
    )
    legend_donut = ft.Row(
        ref=ref_legend_donut,
        wrap=False,
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=15,
        scroll=ft.ScrollMode.HIDDEN,
    )

    sector_opts = [("todos", "Geral")] + [
        (k, k) for k in OP_STYLES.keys() if k != "Desconhecido"
    ]
    dropdown_setores_tipo = scale_dd(
        create_filter_dropdown(
            "",
            sector_opts,
            value="todos",
            width=150,
            on_change=lambda e: load_dashboard_data(e=True),
            ref=ref_dropdown_setores_tipo,
        )
    )
    coluna_setores_custom = ft.Column(
        ref=ref_coluna_setores_custom,
        spacing=20,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    asset_opts = [("saidas", "Entregas"), ("entradas", "Devoluções")]
    dropdown_ativos = scale_dd(
        create_filter_dropdown(
            "",
            asset_opts,
            value="saidas",
            width=180,
            on_change=lambda e: load_dashboard_data(e=True),
            ref=ref_dropdown_ativos,
        )
    )
    coluna_ativos_horizontal = ft.Column(
        ref=ref_coluna_ativos_horizontal, spacing=20, scroll=ft.ScrollMode.HIDDEN
    )

    timeline_opts = [("Geral", "Geral")] + [
        (k, k) for k in OP_STYLES.keys() if k != "Desconhecido"
    ]
    dropdown_timeline = scale_dd(
        create_filter_dropdown(
            "",
            timeline_opts,
            value="Geral",
            width=160,
            on_change=lambda e: load_dashboard_data(e=True),
            ref=ref_dropdown_timeline,
        )
    )

    chk_comparar = ft.Checkbox(
        ref=ref_chk_comparar,
        label="Comparar Anos",
        value=False,
        active_color=COLORS.get("primary", "blue"),
        label_style=ft.TextStyle(
            size=14,
            color=COLORS.get("text_secondary", "grey"),
            weight=ft.FontWeight.BOLD,
        ),
        on_change=lambda e: _toggle_comparison_mode(),
    )

    row_dropdowns = ft.Row(ref=ref_row_dropdowns, spacing=10, visible=False, wrap=True)
    btn_add_year = ft.IconButton(
        ref=ref_btn_add_year,
        icon=ft.icons.ADD_CIRCLE,
        icon_color=COLORS.get("primary", "blue"),
        tooltip="Adicionar Ano para Comparação",
        visible=False,
        on_click=lambda e: add_compare_year(e),
    )

    btn_remove_year = ft.IconButton(
        ref=ref_btn_remove_year,
        icon=ft.icons.REMOVE_CIRCLE,
        icon_color=COLORS.get("error", "red"),
        tooltip="Remover Último Ano",
        visible=False,
        on_click=lambda e: remove_compare_year(e),
    )

    last_year_calc = str(int(datetime.now().year) - 1)
    add_compare_year(initial_val=str(datetime.now().year))
    add_compare_year(
        initial_val=last_year_calc if len(years_db) > 1 else str(datetime.now().year)
    )

    container_comparacao = ft.Row(
        ref=ref_container_comparacao,
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=10,
        controls=[chk_comparar, row_dropdowns, btn_add_year, btn_remove_year],
    )

    months_short = [
        "Jan",
        "Fev",
        "Mar",
        "Abr",
        "Mai",
        "Jun",
        "Jul",
        "Ago",
        "Set",
        "Out",
        "Nov",
        "Dez",
    ]
    legenda_anos = ft.Row(
        ref=ref_legenda_anos,
        wrap=False,
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=20,
        scroll=ft.ScrollMode.AUTO,
    )

    chart_timeline = ft.LineChart(
        ref=ref_chart_timeline,
        data_series=[],
        border=ft.border.all(1, COLORS.get("dash_border", "lightgrey")),
        left_axis=ft.ChartAxis(labels_size=40, title_size=0),
        bottom_axis=ft.ChartAxis(
            labels=[
                ft.ChartAxisLabel(
                    value=i,
                    label=ft.Container(
                        ft.Text(
                            m,
                            size=12,
                            weight=ft.FontWeight.BOLD,
                            color=COLORS.get("text_secondary", "grey"),
                        ),
                        padding=5,
                    ),
                )
                for i, m in enumerate(months_short)
            ],
            labels_size=30,
            labels_interval=1,
        ),
        horizontal_grid_lines=ft.ChartGridLines(
            color=COLORS.get("dash_grid", "lightgrey"), width=1, dash_pattern=[3, 3]
        ),
        vertical_grid_lines=ft.ChartGridLines(
            color=COLORS.get("dash_grid", "lightgrey"), width=1, dash_pattern=[3, 3]
        ),
        tooltip_bgcolor=ft.colors.with_opacity(0.9, COLORS.get("card_bg", "white")),
        min_y=0,
        min_x=0,
        max_x=11,
        expand=True,
    )

    lista_ticker = ft.ListView(
        ref=ref_lista_ticker, spacing=15, padding=10, expand=True
    )

    header_bg = get_header_color(is_test_mode)
    view_header = create_hero_header(
        ft.icons.SPACE_DASHBOARD,
        "Painel Analítico",
        "Acompanhe o volume e a sazonalidade das operações no seu parque tecnológico.",
        header_bg,
    )

    view_col = ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        controls=[
            view_header,
            ft.Divider(height=20, color="transparent"),
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        spacing=15,
                        controls=[
                            create_standard_card(dropdown_filtro_global, padding=0),
                            container_datas,
                        ],
                    ),
                    ft.Container(
                        padding=ft.padding.only(left=10, right=10),
                        content=ft.IconButton(
                            icon=ft.icons.REFRESH_ROUNDED,
                            tooltip="Resetar Filtros",
                            icon_color=COLORS.get("text_secondary", "grey"),
                            icon_size=24,
                            on_click=reset_filters,
                        ),
                    ),
                ],
            ),
            ft.Divider(height=10, color="transparent"),
            container_cards_kpi,
            ft.Divider(height=20, color="transparent"),
            ft.Row(
                height=420,
                spacing=20,
                vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    _create_dashboard_card(
                        "Distribuição Operacional",
                        ft.Column(
                            horizontal_alignment="center",
                            controls=[
                                chart_donut,
                                ft.Container(height=15),
                                legend_donut,
                            ],
                        ),
                        expand=1,
                    ),
                    create_standard_card(
                        expand=2,
                        padding=25,
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text(
                                            "TIMELINE DE OPERAÇÕES",
                                            size=14,
                                            weight=ft.FontWeight.BOLD,
                                            color=COLORS.get("text", "black"),
                                        ),
                                        dropdown_timeline,
                                    ],
                                ),
                                ft.Container(height=10),
                                container_comparacao,
                                ft.Container(height=10),
                                ft.Container(content=chart_timeline, expand=True),
                                ft.Container(height=10),
                                legenda_anos,
                            ]
                        ),
                    ),
                ],
            ),
            ft.Divider(height=20, color="transparent"),
            ft.Row(
                height=350,
                spacing=20,
                vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    _create_dashboard_card(
                        "Rank de Departamentos",
                        ft.Column(
                            expand=True,
                            controls=[
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.END,
                                    controls=[dropdown_setores_tipo],
                                ),
                                coluna_setores_custom,
                            ],
                        ),
                        expand=1,
                    ),
                    _create_dashboard_card(
                        "Ativos Frequentes",
                        ft.Column(
                            expand=True,
                            controls=[
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.END,
                                    controls=[dropdown_ativos],
                                ),
                                coluna_ativos_horizontal,
                            ],
                        ),
                        expand=1,
                    ),
                    _create_dashboard_card(
                        "Feed de Movimentações",
                        lista_ticker,
                        expand=2,
                    ),
                ],
            ),
            ft.Container(height=50),
        ],
    )

    # --- 3.5. Chamada Explicita no Final do Build ---
    load_dashboard_data()
    app_state.fn_update_dashboard = lambda: load_dashboard_data(e=True)

    return view_col
