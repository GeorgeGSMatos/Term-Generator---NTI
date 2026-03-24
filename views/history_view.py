"""
Módulo de Visualização de Histórico (View Layer).

Interface reativa para consulta, filtragem e gerenciamento de termos de
responsabilidade gerados e importados no sistema.
"""

# ==============================================================================
# 1. IMPORTS E DEPENDÊNCIAS
# ==============================================================================
import json
import os
from typing import Any, Dict, List, Optional

import flet as ft

import core.strings as S
from controllers.history_controller import HistoryController

# --- 1.1. Infraestrutura Core, Dicionários e Persistência do BD ---
from core.settings import COLORS, OP_STYLES, get_header_color, load_setting
from core.utils import format_display_date, resolve_operation_context
from data.state import AppState

# --- 1.2. Componentes Sintéticos da View Layer ---
from views.ui import (
    create_filter_dropdown,
    create_form_input,
    create_hero_header,
    create_smart_asset_card,
    create_standard_card,
    scale_dd,
    show_snackbar,
)

# ==============================================================================
# 2. FÁBRICA PRINCIPAL DA VISUALIZAÇÃO DATA GRID
# ==============================================================================


def build_history_tab(page: ft.Page, app_state: AppState) -> ft.Column:
    """Invoca o motor do flet e constrói a Tabela e Controles de Histórico Flet."""

    # --- 2.1. Instância do Controller Master do Histórico ---
    controller = HistoryController()

    # --- 2.2. Closures de Interação ---

    def show_item_details_modal(assets_list: List[Dict[str, Any]]) -> None:
        """Invoca o Dialog Popup para exibr um sub-array injetado no botão em Row."""
        list_controls: List[ft.Control] = []

        if not assets_list:
            list_controls.append(
                ft.Container(
                    content=ft.Text(
                        S.PLACEHOLDER_NO_DETAILS,
                        color=COLORS.get("text_secondary", "grey"),
                        italic=True,
                        size=14,
                    ),
                    alignment=ft.alignment.center,
                    padding=30,
                )
            )
        else:
            for item in assets_list:
                list_controls.append(create_smart_asset_card(item))

        dlg_details = ft.AlertDialog(
            bgcolor=COLORS.get("card_bg", "white"),
            shape=ft.RoundedRectangleBorder(radius=15),
            title=ft.Row(
                [
                    ft.Icon(
                        ft.icons.LIST_ALT, color=COLORS.get("tertiary", "blue"), size=30
                    ),
                    ft.Text("Detalhes dos Itens", weight=ft.FontWeight.BOLD, size=22),
                ]
            ),
            content=ft.Container(
                width=600,
                height=min(450, max(150, len(list_controls) * 120)),
                padding=10,
                content=ft.Column(list_controls, scroll=ft.ScrollMode.AUTO),
            ),
            actions=[
                ft.TextButton(
                    S.BTN_FECHAR,
                    on_click=lambda e: (
                        setattr(dlg_details, "open", False) or page.update()
                    ),
                )
            ],
        )
        page.dialog = dlg_details
        dlg_details.open = True
        page.update()

    def confirm_deletion_dialog(db_id: int, docx_path: str) -> None:
        """Garante barreira lógica perante destruição atômica relacional via UI."""

        def execute_delete(e: ft.ControlEvent) -> None:
            """Ponteiro Sub-Closure de acionamento do DROP Master no SQL."""
            if getattr(e.control, "is_deleting", False):
                return

            e.control.is_deleting = True
            e.control.disabled = True
            e.control.text = "Excluindo..."
            e.control.update()

            try:
                success = controller.delete_record(db_id, docx_path)
                if success:
                    dlg_confirm.open = False
                    handle_data_load()
                    show_snackbar(
                        page, S.MSG_REGISTRO_REMOVIDO, "green", ft.icons.CHECK_CIRCLE
                    )
                    if app_state.fn_update_dashboard:
                        app_state.fn_update_dashboard()
                else:
                    show_snackbar(
                        page,
                        "Erro generalizado ao excluir registro.",
                        "red",
                        ft.icons.ERROR,
                    )
            finally:
                e.control.is_deleting = False
                e.control.disabled = False

        dlg_confirm = ft.AlertDialog(
            title=ft.Text(S.DLG_TITLE_EXCLUIR, size=20, weight="bold"),
            content=ft.Text(S.DLG_BODY_EXCLUIR, size=15),
            actions=[
                ft.TextButton(
                    S.BTN_CANCELAR,
                    on_click=lambda e: (
                        setattr(dlg_confirm, "open", False) or page.update()
                    ),
                ),
                ft.ElevatedButton(
                    S.BTN_EXCLUIR,
                    bgcolor=COLORS.get("error", "red"),
                    color=COLORS.get("text_inverse", "white"),
                    elevation=0,
                    on_click=execute_delete,
                ),
            ],
            shape=ft.RoundedRectangleBorder(radius=12),
        )
        page.dialog = dlg_confirm
        dlg_confirm.open = True
        page.update()

    def show_edit_modal(db_id: int, current_data: dict) -> None:
        """Invoca o Modal de Edição para alterar metadados simples do registro."""
        ref_colab = ft.Ref[ft.TextField]()
        ref_chamado = ft.Ref[ft.TextField]()
        ref_obs = ft.Ref[ft.TextField]()

        txt_colab = create_form_input(
            label="Colaborador",
            icon=ft.icons.PERSON,
            ref=ref_colab,
            value=current_data.get("colaborador", ""),
        )
        txt_chamado = create_form_input(
            label="Chamado",
            icon=ft.icons.CONFIRMATION_NUMBER,
            ref=ref_chamado,
            value=current_data.get("chamado", ""),
        )

        type_options = [(k, k) for k in OP_STYLES.keys()]
        dd_tipo = create_filter_dropdown(
            "Tipo de Operação",
            type_options,
            value=current_data.get("tipo_operacao", "Desconhecido"),
            width=380,
        )

        txt_obs = create_form_input(
            label="Observações",
            icon=ft.icons.NOTES,
            ref=ref_obs,
            value=current_data.get("observacoes", ""),
            multiline=True,
            lines=2,
        )

        def save_edit(e):
            e.control.disabled = True
            e.control.text = "Salvando..."
            page.update()

            new_data = {
                "colaborador": ref_colab.current.value,
                "chamado": ref_chamado.current.value,
                "tipo_operacao": dd_tipo.value,
                "observacoes": ref_obs.current.value,
            }
            if controller.update_record(db_id, new_data):
                dlg_edit.open = False
                show_snackbar(
                    page,
                    "Registro atualizado com sucesso!",
                    "green",
                    ft.icons.CHECK_CIRCLE,
                )
                handle_data_load()
                if app_state.fn_update_dashboard:
                    app_state.fn_update_dashboard()
            else:
                show_snackbar(
                    page, "Erro ao atualizar registro.", "red", ft.icons.ERROR
                )
                e.control.disabled = False
                e.control.text = "Salvar"
                page.update()

        dlg_edit = ft.AlertDialog(
            bgcolor=COLORS.get("card_bg", "white"),
            title=ft.Row(
                [
                    ft.Icon(ft.icons.EDIT, color=COLORS.get("primary", "blue")),
                    ft.Text("Editar Registro", weight="bold"),
                ]
            ),
            content=ft.Column(
                [txt_colab, txt_chamado, dd_tipo, txt_obs],
                tight=True,
                spacing=15,
                width=400,
            ),
            actions=[
                ft.TextButton(
                    S.BTN_CANCELAR,
                    on_click=lambda e: (
                        setattr(dlg_edit, "open", False) or page.update()
                    ),
                ),
                ft.ElevatedButton(
                    "Salvar",
                    on_click=save_edit,
                    bgcolor=COLORS.get("primary", "blue"),
                    color=COLORS.get("text_inverse", "white"),
                    elevation=0,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=12),
        )
        page.dialog = dlg_edit
        dlg_edit.open = True
        page.update()

    local_column_filters = {
        "Tipo": None,
        "Item": None,
        "Colaborador": None,
        "Origem": None,
    }

    cached_raw_rows = []

    def set_col_filter(col: str, val: Optional[str]):
        local_column_filters[col] = val
        handle_data_load(e=None, skip_db=True)
        page.update()

    def build_filtered_column(title: str, options: set) -> ft.DataColumn:
        sorted_opts = sorted(list(options))
        menu_items = [
            ft.PopupMenuItem(
                text="Mostrar Todos", on_click=lambda e: set_col_filter(title, None)
            )
        ]
        for opt in sorted_opts:
            if opt:
                menu_items.append(
                    ft.PopupMenuItem(
                        text=str(opt)[:30],
                        on_click=lambda e, o=opt: set_col_filter(title, o),
                    )
                )

        current_val = local_column_filters.get(title)

        return ft.DataColumn(
            ft.Row(
                spacing=2,
                controls=[
                    ft.Text(
                        title,
                        weight=ft.FontWeight.BOLD,
                        size=14,
                        color=COLORS.get("text_secondary", "grey"),
                    ),
                    ft.PopupMenuButton(
                        icon=ft.icons.FILTER_ALT
                        if current_val
                        else ft.icons.ARROW_DROP_DOWN,
                        tooltip=f"Filtrar por {title} (Atual: {current_val or 'Todos'})",
                        items=menu_items,
                    )
                    if options
                    else ft.Container(),
                ],
            )
        )

    async def handle_open_document_click(e: ft.ControlEvent, p: str) -> None:
        """Ponteiro de ação para visualizar o documento MS Word originário."""
        if p and os.path.exists(p):
            try:
                os.startfile(p)
            except Exception as ex:
                show_snackbar(page, f"Erro ao abrir: {ex}", "red", ft.icons.ERROR)
        else:
            show_snackbar(page, S.MSG_ARQUIVO_NAO_ENCONTRADO, "red", ft.icons.ERROR)

    # --- 2.3. Controle Rápido Contextual Global ---
    current_config = load_setting()
    is_test_mode = current_config.get("modo_teste", False)
    focus_color = (
        COLORS.get("orange", "orange")
        if is_test_mode
        else COLORS.get("primary", "blue")
    )

    # --- 2.4. Input Mestre de Search FullText SQL ---
    txt_search = ft.TextField(
        label=S.LABEL_BUSCA_PATRIMONIO,
        label_style=ft.TextStyle(color=COLORS.get("text_secondary", "grey"), size=13),
        text_size=15,
        prefix_icon=ft.icons.SEARCH,
        border_radius=12,
        bgcolor=COLORS.get("input_bg", "white"),
        border_color="transparent",
        focused_border_color=focus_color,
        content_padding=18,
    )
    container_search = create_standard_card(txt_search, padding=0, expand=True)

    # --- 2.5. Puxadas em Tempo Real no Controller ---
    years_db, months_db = controller.years_db, controller.months_db

    # --- 2.6. Selectors da UI Flexíveis Escalados ---
    period_options = [
        ("hoje", "Hoje"),
        ("semana", "Esta Semana"),
        ("30_dias", "Últimos 30 Dias"),
        ("especifico", "Mês/Ano Específico"),
        ("tudo", "Mostrar Tudo"),
    ]
    dropdown_period = scale_dd(
        create_filter_dropdown("Período", period_options, value="30_dias", width=200)
    )
    container_period = create_standard_card(dropdown_period, padding=0)

    type_options = [("todos", "Todos")] + [
        (k, k) for k in OP_STYLES.keys() if k != "Desconhecido"
    ]
    dropdown_type = scale_dd(
        create_filter_dropdown("Tipo", type_options, value="todos", width=150)
    )
    container_type = create_standard_card(dropdown_type, padding=0)

    # --- 2.7. Mês e Ano Restrito Toggleables ---
    month_options = [(m, m) for m in months_db]
    dropdown_month = scale_dd(
        create_filter_dropdown(
            "Mês", month_options, value=months_db[0] if months_db else None, width=150
        )
    )

    year_options = [(str(y), str(y)) for y in years_db]
    dropdown_year = scale_dd(
        create_filter_dropdown(
            "Ano", year_options, value=str(years_db[0]) if years_db else None, width=120
        )
    )

    container_specific_dates = ft.Container(
        visible=False,
        content=ft.Row(
            spacing=10,
            controls=[
                create_standard_card(dropdown_month, padding=0),
                create_standard_card(dropdown_year, padding=0),
            ],
        ),
    )

    # --- 2.8. Tabela Centralizada de Exibição ---
    data_table = ft.DataTable(
        heading_row_height=50,
        data_row_max_height=70,
        column_spacing=50,
        heading_row_color=COLORS.get("grey_bg", "lightgrey"),
        divider_thickness=0.5,
        columns=[
            ft.DataColumn(
                ft.Text(
                    "Data",
                    weight=ft.FontWeight.BOLD,
                    size=14,
                    color=COLORS.get("text_secondary", "grey"),
                )
            ),
            ft.DataColumn(
                ft.Text(
                    "Tipo",
                    weight=ft.FontWeight.BOLD,
                    size=14,
                    color=COLORS.get("text_secondary", "grey"),
                )
            ),
            ft.DataColumn(
                ft.Text(
                    "Item",
                    weight=ft.FontWeight.BOLD,
                    size=14,
                    color=COLORS.get("text_secondary", "grey"),
                )
            ),
            ft.DataColumn(
                ft.Text(
                    "Colaborador(a)",
                    weight=ft.FontWeight.BOLD,
                    size=14,
                    color=COLORS.get("text_secondary", "grey"),
                )
            ),
            ft.DataColumn(
                ft.Text(
                    "Origem",
                    weight=ft.FontWeight.BOLD,
                    size=14,
                    color=COLORS.get("text_secondary", "grey"),
                )
            ),
            ft.DataColumn(
                ft.Text(
                    "Ações",
                    weight=ft.FontWeight.BOLD,
                    size=14,
                    color=COLORS.get("text_secondary", "grey"),
                )
            ),
        ],
    )

    # --- 2.9. Cérebro da UI ---

    def handle_data_load(
        e: Optional[ft.ControlEvent] = None, skip_db: bool = False
    ) -> None:
        """Ponteiro Mestre Recarregador de Linhas Table com filtragem cruzada dinâmica."""
        nonlocal cached_raw_rows

        container_specific_dates.visible = dropdown_period.value == "especifico"
        if e:
            page.update()

        if not skip_db:
            raw_rows = controller.load_history_data(
                filter_mode=dropdown_period.value,
                month=dropdown_month.value,
                year=dropdown_year.value,
                search_term=txt_search.value,
                op_type=dropdown_type.value,
                limit=100,
            )
            cached_raw_rows = raw_rows
        else:
            raw_rows = cached_raw_rows

        data_table.rows.clear()

        if not raw_rows:
            if e:
                page.update()
            return

        # --- 2.9.1. Conjuntos Para Preencher os Dropdowns ---
        tipos_set = set()
        itens_set = set()
        colabs_set = set()
        origens_set = set()

        for record in raw_rows:
            try:
                (
                    id_db,
                    date_raw,
                    op_type,
                    ticket,
                    colab,
                    area,
                    path_docx,
                    assets_json,
                    obs,
                    origin,
                ) = record
            except ValueError:
                continue

            tipos_set.add(op_type)
            colabs_set.add(colab)

            # --- 2.9.2. Helper Origin ---
            val_origin = origin if origin else "Gerado Manualmente"
            origens_set.add(val_origin)

            try:
                asset_list = json.loads(assets_json)
                for a in asset_list:
                    itens_set.add(a.get("tipo", "Item Genérico"))
                if asset_list:
                    main_desc = asset_list[0].get("descricao_visual", "Item Genérico")
                    btn_label = (
                        f"{main_desc[:35]}..." if len(main_desc) > 35 else main_desc
                    )
                    if len(asset_list) > 1:
                        btn_label += f" [+{len(asset_list) - 1}]"
                else:
                    btn_label = "-"
            except (json.JSONDecodeError, TypeError):
                asset_list = []
                btn_label = "Erro Dados"

            # --- 2.9.3. Aplica Filtros Locais ---
            if local_column_filters["Tipo"] and local_column_filters["Tipo"] != op_type:
                continue
            if (
                local_column_filters["Colaborador"]
                and local_column_filters["Colaborador"] != colab
            ):
                continue
            if (
                local_column_filters["Origem"]
                and local_column_filters["Origem"] != val_origin
            ):
                continue

            if local_column_filters["Item"]:
                has_item = False
                for a in asset_list:
                    if a.get("tipo") == local_column_filters["Item"]:
                        has_item = True
                        break
                if not has_item:
                    continue

            date_fmt = format_display_date(date_raw)
            content_btn = ft.Text(
                btn_label,
                color=COLORS.get("primary", "blue")
                if asset_list
                else COLORS.get("error", "red"),
                size=14,
                weight=ft.FontWeight.BOLD,
                no_wrap=True,
            )

            icon_name, color, is_hybrid = resolve_operation_context(
                op_type, path_docx, obs
            )

            if is_hybrid:
                mov_style = OP_STYLES.get("Movimentação")
                visual_icon = ft.Row(
                    spacing=-4,
                    controls=[
                        ft.Icon(name=icon_name, color=color, size=18),
                        ft.Icon(
                            name=mov_style["icon"], color=mov_style["color"], size=18
                        ),
                    ],
                )
            else:
                visual_icon = ft.Icon(name=icon_name, color=color, size=20)

            if not origin or origin == "Gerado Manualmente":
                icon_origin = ft.Icon(
                    ft.icons.CREATE,
                    size=18,
                    color=COLORS.get("text_secondary", "grey"),
                    tooltip="Geração Manual",
                )
            else:
                icon_origin = ft.Icon(
                    ft.icons.CLOUD_DOWNLOAD,
                    size=18,
                    color=COLORS.get("blue_info", "blue"),
                    tooltip=f"Importado de: {origin}",
                )

            # --- 2.9.4. Dados para Modal de Edição ---
            current_data = {
                "colaborador": colab,
                "chamado": ticket,
                "tipo_operacao": op_type,
                "observacoes": obs,
            }

            data_table.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(date_fmt, size=14)),
                        ft.DataCell(
                            ft.Row(
                                spacing=8,
                                controls=[
                                    visual_icon,
                                    ft.Text(
                                        str(op_type),
                                        size=14,
                                        weight="bold",
                                        color=color,
                                    ),
                                ],
                            )
                        ),
                        ft.DataCell(
                            ft.TextButton(
                                content=content_btn,
                                on_click=lambda e, al=asset_list: (
                                    show_item_details_modal(al)
                                ),
                            )
                        ),
                        ft.DataCell(ft.Text(str(colab)[:25], size=14)),
                        ft.DataCell(icon_origin),
                        ft.DataCell(
                            ft.Row(
                                spacing=5,
                                controls=[
                                    ft.IconButton(
                                        ft.icons.EDIT,
                                        tooltip="Editar",
                                        icon_color=COLORS.get("primary", "blue"),
                                        icon_size=20,
                                        on_click=lambda e, i=id_db, cd=current_data: (
                                            show_edit_modal(i, cd)
                                        ),
                                    ),
                                    ft.IconButton(
                                        ft.icons.EDIT_DOCUMENT,
                                        tooltip="Abrir Word",
                                        icon_color=COLORS.get("blue_word", "blue"),
                                        icon_size=20,
                                        on_click=lambda e, p=path_docx: (
                                            handle_open_document_click(e, p)
                                        ),
                                    ),
                                    ft.IconButton(
                                        ft.icons.DELETE,
                                        tooltip=S.BTN_EXCLUIR,
                                        icon_color=COLORS.get("error", "red"),
                                        icon_size=20,
                                        on_click=lambda e, i=id_db, d=path_docx: (
                                            confirm_deletion_dialog(i, d)
                                        ),
                                    ),
                                ],
                            )
                        ),
                    ]
                )
            )

        # --- 2.9.5. Reconstrução de Colunas com Menus Dropdowns ---
        data_table.columns = [
            ft.DataColumn(
                ft.Text(
                    "Data",
                    weight=ft.FontWeight.BOLD,
                    size=14,
                    color=COLORS.get("text_secondary", "grey"),
                )
            ),
            build_filtered_column("Tipo", tipos_set),
            build_filtered_column("Item", itens_set),
            build_filtered_column("Colaborador", colabs_set),
            build_filtered_column("Origem", origens_set),
            ft.DataColumn(
                ft.Text(
                    "Ações",
                    weight=ft.FontWeight.BOLD,
                    size=14,
                    color=COLORS.get("text_secondary", "grey"),
                )
            ),
        ]
        if e:
            page.update()

    def reset_filters(e: Optional[ft.ControlEvent] = None) -> None:
        """Limpa todos os filtros Globais e Locais, restaurando a visão padrão do sistema."""
        # --- 2.10. Reset de Componentes Visuais ---
        txt_search.value = ""
        dropdown_period.value = "30_dias"
        dropdown_type.value = "todos"

        if months_db:
            dropdown_month.value = months_db[0]
        if years_db:
            dropdown_year.value = str(years_db[0])

        container_specific_dates.visible = False

        # --- 2.10.1. Reset de Cache de Filtros Locais das Colunas ---
        for key in local_column_filters:
            local_column_filters[key] = None

        # --- 2.10.2. Forçação da Atualização do Motor de Pesquisa ---
        page.update()
        handle_data_load()
        show_snackbar(
            page, "Filtros restaurados para o padrão.", "blue_info", ft.icons.REFRESH
        )

    # --- 2.11. Bindings Finais de Eventos e Export do Layout ---

    txt_search.on_submit = handle_data_load
    dropdown_period.on_change = handle_data_load
    dropdown_month.on_change = handle_data_load
    dropdown_year.on_change = handle_data_load
    dropdown_type.on_change = handle_data_load

    # --- 2.11.1. Initial Fetch ---
    handle_data_load()

    # --- 2.11.2. Registro da View no State Machine ---
    app_state.fn_update_history = lambda: handle_data_load(e=True)

    header_bg = get_header_color(is_test_mode)
    view_header = create_hero_header(
        ft.icons.HISTORY,
        "Histórico de Termos",
        "Consulte, filtre e gerencie os documentos gerados e importados.",
        header_bg,
    )

    # --- 2.12. Envelopamento Global Retornado para main.py UI Controller ---
    return ft.Column(
        expand=True,
        controls=[
            view_header,
            ft.Divider(height=20, color="transparent"),
            ft.Row(
                alignment=ft.MainAxisAlignment.START,
                spacing=10,
                controls=[
                    container_period,
                    container_specific_dates,
                    container_type,
                    container_search,
                    ft.Container(
                        padding=ft.padding.only(left=5, right=5),
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
            create_standard_card(
                padding=15,
                expand=True,
                content=ft.Container(
                    expand=True,
                    content=ft.Column(
                        scroll=ft.ScrollMode.ALWAYS,
                        alignment=ft.MainAxisAlignment.START,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        controls=[
                            ft.Row(
                                scroll=ft.ScrollMode.ALWAYS,
                                vertical_alignment=ft.CrossAxisAlignment.START,
                                controls=[
                                    ft.Container(
                                        content=data_table,
                                    )
                                ],
                            )
                        ],
                    ),
                ),
            ),
        ],
    )
