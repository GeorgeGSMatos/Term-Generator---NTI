"""
Módulo de Visualização MDM (Master Data Management).

Interface administrativa para gerenciamento direto de tabelas, regras de
negócio, auditoria de dados e manutenção preventiva do sistema.
"""

# ==============================================================================
# 1. IMPORTS E DEPENDÊNCIAS
# ==============================================================================
import asyncio
import os
from typing import List, Optional

import flet as ft

from controllers.mdm_controller import MDMController

# --- 1.1. Infraestrutura Core e Controller ---
from core.settings import COLORS
from data.state import AppState

# --- 1.2. Componentes Sintéticos da View Layer ---
from views.ui import (
    create_filter_dropdown,
    create_form_input,
    create_icon_row_card,
    create_page_header,
    create_primary_button,
    create_standard_card,
    shake_control,
    show_snackbar,
)

# ==============================================================================
# 2. ESTADO E CONSTRUÇÃO DAS VISUALIZAÇÕES
# ==============================================================================


def build_mdm_view(page: ft.Page, app_state: AppState) -> None:
    """Invoca o motor do flet e constrói o Applet Administrativo Master."""

    # --- 2.1. Instancia o Cérebro da Operação ---
    controller = MDMController()

    # --- 2.2. Âncoras Dinâmicas de Mutação Virtual Dom ---

    # --- 2.3. Telas de Base ---
    ref_lock_container = ft.Ref[ft.Container]()
    ref_mdm_container = ft.Ref[ft.Container]()
    ref_pass_input = ft.Ref[ft.TextField]()
    ref_right_panel = ft.Ref[ft.Container]()

    # --- 2.4. Elementos de Componentes Analíticos ---
    ref_db_dropdown = ft.Ref[ft.Dropdown]()
    ref_db_table = ft.Ref[ft.DataTable]()
    ref_db_limit = ft.Ref[ft.Dropdown]()
    ref_db_search = ft.Ref[ft.TextField]()
    ref_btn_prev = ft.Ref[ft.IconButton]()
    ref_btn_next = ft.Ref[ft.IconButton]()
    ref_txt_page = ft.Ref[ft.Text]()

    ref_rule_search = ft.Ref[ft.TextField]()
    ref_rule_target = ft.Ref[ft.Dropdown]()
    ref_rule_replace = ft.Ref[ft.TextField]()
    ref_rules_list = ft.Ref[ft.Column]()

    ref_sync_progress = ft.Ref[ft.ProgressBar]()
    ref_sync_log = ft.Ref[ft.Text]()
    ref_gemini_key = ft.Ref[ft.TextField]()
    ref_sync_years = ft.Ref[ft.TextField]()
    ref_sync_months = ft.Ref[ft.TextField]()
    ref_btn_start = ft.Ref[ft.Container]()
    ref_btn_pause = ft.Ref[ft.Container]()
    ref_btn_cancel = ft.Ref[ft.Container]()

    # --- 2.4.1. Auditoria Retroativa ---
    ref_audit_log = ft.Ref[ft.ListView]()
    ref_audit_status = ft.Ref[ft.Text]()
    ref_audit_progress = ft.Ref[ft.ProgressBar]()
    ref_audit_table = ft.Ref[ft.DataTable]()
    current_audit_findings = []
    selected_fixes = {}

    sync_state = {"pause": False, "cancel": False}
    current_page = [1]
    state_table = {"cols": [], "rows": [], "filters": {}, "last_table": None}

    # --- 2.5. Closures de Interação Frontend-Backend ---

    def refresh_rules_ui() -> None:
        """Sincroniza UI Lists Lendo em Disco e Redesenhando os Cards Json de Regra."""
        ref_rules_list.current.controls.clear()
        rules = controller.get_rules()

        if not rules:
            ref_rules_list.current.controls.append(
                ft.Text(
                    "Nenhuma regra ativa no momento.",
                    color=COLORS.get("text_secondary", "grey"),
                    italic=True,
                    size=14,
                )
            )
        else:
            for r in rules:
                card = create_icon_row_card(
                    title=f"Busca: '{r['search']}'",
                    subtitle=f"➔ {r['target']} = '{r['replace']}'",
                    icon_name=ft.icons.RULE,
                    accent_color=COLORS.get("primary", "blue"),
                    bg_icon_color=COLORS.get("primary_light", "lightblue"),
                    trailing_control=ft.IconButton(
                        icon=ft.icons.DELETE,
                        icon_color="red",
                        icon_size=24,
                        tooltip="Remover Regra",
                        on_click=lambda e, t=r["target"], s=r["search"]: (
                            handle_delete_rule(t, s)
                        ),
                    ),
                )
                ref_rules_list.current.controls.append(card)
        page.update()

    async def handle_unlock(e: ft.ControlEvent) -> None:
        sucesso, msg = controller.verify_admin_password(ref_pass_input.current.value)

        if sucesso:
            ref_lock_container.current.visible = False
            ref_mdm_container.current.visible = True
            ref_pass_input.current.value = ""

            tabelas_reais = controller.get_all_tables()
            if tabelas_reais:
                ref_db_dropdown.current.options = [
                    ft.dropdown.Option(t) for t in tabelas_reais
                ]
                ref_db_dropdown.current.value = tabelas_reais[0]

            handle_load_table(None)
            refresh_rules_ui()
            page.update()
        else:
            ref_pass_input.current.disabled = True
            page.update()
            await asyncio.sleep(1.0)
            ref_pass_input.current.value = ""
            ref_pass_input.current.error_text = msg
            ref_pass_input.current.disabled = False
            await shake_control(ref_pass_input)
            ref_pass_input.current.focus()
            page.update()

    def handle_lock_vault(e: ft.ControlEvent) -> None:
        ref_mdm_container.current.visible = False
        ref_lock_container.current.visible = True
        page.update()

    def handle_go_back(e: ft.ControlEvent) -> None:
        page.go("/config")

    # --- 2.6. Closures de Tabelas e Filtros Dinâmicos ---
    def set_col_filter(col: str, val: Optional[str]):
        state_table["filters"][col] = val
        _render_table_data_filtered()

    def build_filtered_column(title: str, options: set) -> ft.DataColumn:
        sorted_opts = sorted(
            list(options), key=lambda x: str(x) if x is not None else ""
        )
        menu_items = [
            ft.PopupMenuItem(
                text="Mostrar Todos", on_click=lambda e: set_col_filter(title, None)
            )
        ]

        for opt in sorted_opts:
            if opt is not None and str(opt).strip() != "":
                menu_items.append(
                    ft.PopupMenuItem(
                        text=str(opt)[:30],
                        on_click=lambda e, o=opt: set_col_filter(title, o),
                    )
                )

        current_val = state_table["filters"].get(title)

        return ft.DataColumn(
            ft.Row(
                spacing=2,
                controls=[
                    ft.Text(title, weight="bold", size=16),
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

    def _render_table_data_filtered():
        cols = state_table["cols"]
        raw_rows = state_table["rows"]

        if not cols:
            ref_db_table.current.columns = [
                ft.DataColumn(ft.Text("Nenhuma tabela selecionada ou Vazia", size=16))
            ]
            ref_db_table.current.rows = []
            page.update()
            return

        options_per_col = {c: set() for c in cols}
        filtered_rows = []

        for r in raw_rows:
            for i, c in enumerate(cols):
                options_per_col[c].add(r[i])
            pass_filter = True
            for i, c in enumerate(cols):
                f_val = state_table["filters"].get(c)
                if f_val is not None and r[i] != f_val:
                    pass_filter = False
                    break
            if pass_filter:
                filtered_rows.append(r)

        new_columns = [build_filtered_column(c, options_per_col[c]) for c in cols]
        new_columns.append(ft.DataColumn(ft.Text("Ações", weight="bold", size=16)))

        new_rows = []
        for r in filtered_rows:
            cells = [ft.DataCell(ft.Text(str(val), size=14)) for val in r]
            pk_val, pk_col = r[0], cols[0]

            btn_edit = ft.IconButton(
                icon=ft.icons.EDIT,
                icon_size=20,
                icon_color="blue",
                tooltip="Editar",
                on_click=lambda e, pk=pk_val, rd=r: handle_edit_record(
                    pk, pk_col, rd, cols
                ),
            )
            btn_delete = ft.IconButton(
                icon=ft.icons.DELETE,
                icon_size=20,
                icon_color="red",
                tooltip="Deletar",
                on_click=lambda e, pk=pk_val: handle_delete_record(pk, pk_col),
            )
            cells.append(ft.DataCell(ft.Row([btn_edit, btn_delete], spacing=5)))
            new_rows.append(ft.DataRow(cells=cells))

        ref_db_table.current.columns = new_columns
        ref_db_table.current.rows = new_rows
        ref_db_table.current.column_spacing = 50
        page.update()

    def update_pagination_ui(has_more=False):
        if ref_txt_page.current:
            ref_txt_page.current.value = f"Página {current_page[0]}"
            ref_btn_prev.current.disabled = current_page[0] <= 1
            ref_btn_next.current.disabled = not has_more
            page.update()

    def handle_load_table(e: ft.ControlEvent = None) -> None:
        if e is not None:
            current_page[0] = 1
        selected_table = ref_db_dropdown.current.value
        if not selected_table:
            return

        if state_table["last_table"] != selected_table:
            state_table["filters"] = {}
            state_table["last_table"] = selected_table

        limit_val = (
            int(ref_db_limit.current.value)
            if (ref_db_limit.current and ref_db_limit.current.value)
            else 50
        )
        offset_val = (current_page[0] - 1) * limit_val

        cols, rows = controller.get_table_data(
            selected_table, limit=limit_val + 1, offset=offset_val
        )

        has_more = len(rows) > limit_val
        if has_more:
            rows = rows[:limit_val]

        if state_table["cols"] != cols:
            state_table["filters"] = {c: None for c in cols}

        state_table["cols"], state_table["rows"] = cols, rows
        _render_table_data_filtered()
        update_pagination_ui(has_more)

    def handle_search_table(e: ft.ControlEvent = None) -> None:
        if e is not None:
            current_page[0] = 1
        selected_table, search_term = (
            ref_db_dropdown.current.value,
            ref_db_search.current.value,
        )

        if not selected_table:
            return
        if not search_term:
            return handle_load_table(None)

        if state_table["last_table"] != selected_table:
            state_table["filters"] = {}
            state_table["last_table"] = selected_table

        limit_val = (
            int(ref_db_limit.current.value)
            if (ref_db_limit.current and ref_db_limit.current.value)
            else 50
        )
        offset_val = (current_page[0] - 1) * limit_val

        cols, rows = controller.search_table(
            selected_table, search_term, limit=limit_val + 1, offset=offset_val
        )

        has_more = len(rows) > limit_val
        if has_more:
            rows = rows[:limit_val]

        if state_table["cols"] != cols:
            state_table["filters"] = {c: None for c in cols}

        state_table["cols"], state_table["rows"] = cols, rows
        _render_table_data_filtered()
        update_pagination_ui(has_more)

    def handle_prev_page(e):
        if current_page[0] > 1:
            current_page[0] -= 1
            handle_search_table(
                None
            ) if ref_db_search.current.value else handle_load_table(None)

    def handle_next_page(e):
        current_page[0] += 1
        handle_search_table(None) if ref_db_search.current.value else handle_load_table(
            None
        )

    def handle_edit_record(pk_value, pk_column, row_data, cols):
        selected_table = ref_db_dropdown.current.value
        field_refs = {}
        content_col = ft.Column(scroll=ft.ScrollMode.ALWAYS, expand=False, spacing=15)

        for col_name, val in zip(cols, row_data):
            ref = ft.Ref[ft.TextField]()
            tf = create_form_input(
                label=col_name,
                icon=ft.icons.KEY if col_name == pk_column else ft.icons.EDIT_NOTE,
                ref=ref,
                value=str(val) if val is not None else "",
            )
            if col_name == pk_column:
                tf.disabled = True
            field_refs[col_name] = ref
            content_col.controls.append(tf)

        def save_edit(e):
            update_data = {
                k: field_refs[k].current.value for k in field_refs if k != pk_column
            }
            if controller.update_record(
                selected_table, pk_column, pk_value, update_data
            ):
                show_snackbar(page, "✅ Registro atualizado no banco!", "green")
                dlg.open = False
                page.update()
                handle_search_table(
                    None
                ) if ref_db_search.current.value else handle_load_table()
            else:
                show_snackbar(page, "❌ Erro ao atualizar o registro.", "error")

        dlg = ft.AlertDialog(
            bgcolor=COLORS.get("card_bg", "white"),
            title=ft.Row(
                [
                    ft.Icon(ft.icons.EDIT, color=COLORS.get("primary", "blue")),
                    ft.Text(f"Editar na {selected_table}", weight="bold"),
                ]
            ),
            content=ft.Container(content=content_col, width=370, height=400),
            actions=[
                ft.TextButton(
                    "Cancelar",
                    on_click=lambda e: setattr(dlg, "open", False) or page.update(),
                ),
                ft.ElevatedButton(
                    "Salvar Alterações",
                    on_click=save_edit,
                    color=COLORS.get("text_inverse", "white"),
                    bgcolor=COLORS.get("primary", "blue"),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=12),
        )
        page.dialog = dlg
        dlg.open = True
        page.update()

    def handle_delete_record(pk_value, pk_column):
        selected_table = ref_db_dropdown.current.value

        def confirm_del(e):
            if controller.delete_record(selected_table, pk_column, pk_value):
                show_snackbar(page, "✅ Registro apagado da base de dados!", "green")
                dlg.open = False
                page.update()
                handle_search_table(
                    None
                ) if ref_db_search.current.value else handle_load_table()
            else:
                show_snackbar(
                    page, "❌ Restrição Relacional impediu a exclusão.", "error"
                )
                dlg.open = False
                page.update()

        dlg = ft.AlertDialog(
            title=ft.Row(
                [ft.Icon(ft.icons.WARNING, color="red"), ft.Text("Confirma Exclusão?")]
            ),
            content=ft.Text(
                f"Deseja remover esse dado da Tabela '{selected_table}' para sempre?"
            ),
            actions=[
                ft.TextButton(
                    "Cancelar",
                    on_click=lambda e: setattr(dlg, "open", False) or page.update(),
                ),
                ft.ElevatedButton(
                    "Excluir Permanentemente",
                    on_click=confirm_del,
                    color="white",
                    bgcolor="red",
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.dialog = dlg
        dlg.open = True
        page.update()

    def handle_export_csv(e: ft.ControlEvent) -> None:
        selected_table = ref_db_dropdown.current.value
        if not selected_table:
            return

        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        arquivo_destino = os.path.join(desktop_path, f"exportacao_{selected_table}.csv")

        if controller.export_table_csv(selected_table, arquivo_destino):
            show_snackbar(
                page,
                f"✅ CSV salvo na Área de Trabalho: exportacao_{selected_table}.csv",
                "green",
            )
        else:
            show_snackbar(page, "❌ Erro ao exportar CSV. Verifique os logs.", "error")

    async def handle_import_csv(e: ft.FilePickerResultEvent) -> None:
        if not e.files or len(e.files) == 0:
            return

        file_path = e.files[0].path
        page.is_db_locked = True
        show_snackbar(page, "⏳ Processando importação em lote...", "blue_info")
        page.update()

        try:
            sucessos, erros = await controller.import_csv_async(file_path)
            if sucessos > 0:
                show_snackbar(
                    page,
                    f"✅ Importação concluída: {sucessos} processados, {erros} erros.",
                    "green",
                )
                handle_load_table(None)
            else:
                show_snackbar(
                    page, f"⚠️ Nenhum ativo importado. ({erros} erros)", "orange"
                )
        except Exception as ex:
            show_snackbar(page, f"❌ Falha severa na importação: {ex}", "error")
        finally:
            page.is_db_locked = False
            page.update()

    # --- 2.7. Closures de Manutenções e Saúde DB ---
    async def handle_db_scan(e: ft.ControlEvent) -> None:
        if getattr(page, "is_db_locked", False):
            return
        page.is_db_locked = True
        show_snackbar(page, "🔍 Escaneando banco...", "blue_info")
        await asyncio.sleep(0.5)

        try:
            relatorio = controller.run_diagnostics()
            dlg = ft.AlertDialog(
                title=ft.Row(
                    [ft.Icon(ft.icons.ANALYTICS, color="blue"), ft.Text("Diagnóstico")]
                ),
                content=ft.Text(relatorio, size=16),
                actions=[
                    ft.TextButton(
                        "Fechar",
                        on_click=lambda e: setattr(dlg, "open", False) or page.update(),
                    )
                ],
            )
            page.dialog = dlg
            dlg.open = True
            page.update()
        finally:
            page.is_db_locked = False

    def handle_vacuum(e: ft.ControlEvent) -> None:
        if getattr(page, "is_db_locked", False):
            return
        page.is_db_locked = True
        if controller.execute_vacuum():
            show_snackbar(page, "✅ Banco desfragmentado com sucesso!", "green")
        page.is_db_locked = False

    def handle_optimize(e: ft.ControlEvent) -> None:
        if getattr(page, "is_db_locked", False):
            return
        page.is_db_locked = True
        if controller.optimize_indexes():
            show_snackbar(
                page, "💡 Engine de índices otimizada com a heurística atual!", "green"
            )
        page.is_db_locked = False

    def handle_reindex(e: ft.ControlEvent) -> None:
        if getattr(page, "is_db_locked", False):
            return
        page.is_db_locked = True
        if controller.reindex_db():
            show_snackbar(
                page, "📖 Árvores B-Tree rebalanceadas e índices refeitos!", "green"
            )
        page.is_db_locked = False

    def handle_backup(e: ft.ControlEvent) -> None:
        if getattr(page, "is_db_locked", False):
            return
        page.is_db_locked = True
        if controller.create_backup():
            show_snackbar(
                page, "💾 Clone de Segurança do Banco enviado ao Desktop!", "green"
            )
        else:
            show_snackbar(page, "❌ Falha ao criar backup manual.", "error")
        page.is_db_locked = False

    def handle_delete_duplicates(e: ft.ControlEvent) -> None:
        if getattr(page, "is_db_locked", False):
            return

        def confirm_action(evt):
            dlg.open = False
            page.update()
            page.is_db_locked = True
            result = controller.delete_duplicates()

            if "error" in result:
                show_snackbar(page, "❌ Ocorreu um erro ao apagar duplicatas.", "error")
            else:
                total_del = sum(result.values())
                if total_del > 0:
                    msg = (
                        f"🧹 Limpeza Concluída! Removidos: "
                        f"{result.get('tb_termos', 0)} Termos, "
                        f"{result.get('tb_colaboradores', 0)} Colabs, "
                        f"{result.get('tb_ativos', 0)} Ativos Órfãos, "
                        f"{result.get('tb_termo_ativo', 0)} Ligações."
                    )
                    show_snackbar(page, msg, "green")
                else:
                    show_snackbar(
                        page,
                        "✅ O Banco já está limpo. Nenhuma duplicata encontrada.",
                        "blue_info",
                    )
            page.is_db_locked = False

        dlg = ft.AlertDialog(
            title=ft.Row(
                [
                    ft.Icon(ft.icons.CONTROL_POINT_DUPLICATE, color="orange"),
                    ft.Text("Apagar Duplicatas", weight="bold"),
                ]
            ),
            content=ft.Text(
                "O sistema manterá apenas o registro mais recente e apagará os clones. Prosseguir?"
            ),
            actions=[
                ft.TextButton(
                    "Cancelar",
                    on_click=lambda e: setattr(dlg, "open", False) or page.update(),
                ),
                ft.ElevatedButton(
                    "ESCANEAR E LIMPAR",
                    on_click=confirm_action,
                    color="white",
                    bgcolor="orange",
                ),
            ],
            shape=ft.RoundedRectangleBorder(radius=12),
        )
        page.dialog = dlg
        dlg.open = True
        page.update()

    async def handle_date_audit_start(e: ft.ControlEvent) -> None:
        if getattr(page, "is_db_locked", False):
            return

        ref_audit_log.current.controls.clear()
        ref_audit_status.current.value = "Iniciando auditoria nos documentos DOCX..."
        ref_audit_progress.current.value = None
        ref_audit_progress.current.visible = True

        audit_view_log.visible = True
        audit_view_results.visible = False

        page.dialog = dlg_audit
        dlg_audit.open = True
        page.update()

        findings = []
        try:
            async for status in controller.run_date_auditor_generator(limit=100):
                if status["type"] == "log":
                    ref_audit_log.current.controls.append(
                        ft.Text(f"> {status['msg']}", size=12, font_family="monospace")
                    )
                    ref_audit_log.current.scroll_to(offset=-1, duration=100)
                    page.update()
                elif status["type"] == "done":
                    findings = status["results"]
                    break
                elif status["type"] == "error":
                    show_snackbar(
                        page, f"❌ Erro na auditoria: {status['msg']}", "error"
                    )
                    dlg_audit.open = False
                    page.update()
                    return

            if not findings:
                ref_audit_status.current.value = (
                    "✅ Nenhuma divergência de data encontrada!"
                )
                ref_audit_progress.current.visible = False
                ref_audit_log.current.controls.append(
                    ft.Text("--- Fim da Análise ---", italic=True)
                )
                page.update()
            else:
                nonlocal current_audit_findings
                current_audit_findings = findings
                _render_audit_results(findings)
                audit_view_log.visible = False
                audit_view_results.visible = True
                ref_audit_status.current.value = (
                    f"🔍 Encontradas {len(findings)} divergências."
                )
                page.update()

        except Exception as ex:
            show_snackbar(page, f"❌ Erro crítico no auditor: {ex}", "error")
            dlg_audit.open = False
            page.update()

    def _render_audit_results(findings):
        ref_audit_table.current.rows.clear()
        nonlocal selected_fixes
        selected_fixes = {f["id"]: "correct" for f in findings}

        def on_action_change(fid, action):
            selected_fixes[fid] = action

        for f in findings:
            fid = f["id"]
            row = ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(str(fid), size=11)),
                    ft.DataCell(
                        ft.Text(
                            f["nome_arquivo"][:20] + "...",
                            size=11,
                            tooltip=f["nome_arquivo"],
                        )
                    ),
                    ft.DataCell(ft.Text(f["data_db"], color="red", weight="bold")),
                    ft.DataCell(
                        ft.Text(f["data_encontrada"], color="green", weight="bold")
                    ),
                    ft.DataCell(
                        ft.Row(
                            [
                                ft.Dropdown(
                                    width=120,
                                    height=40,
                                    text_size=11,
                                    content_padding=5,
                                    value="correct",
                                    options=[
                                        ft.dropdown.Option("correct", "Corrigir"),
                                        ft.dropdown.Option("delete", "Excluir"),
                                        ft.dropdown.Option("ignore", "Ignorar"),
                                    ],
                                    on_change=lambda e, f_id=fid: on_action_change(
                                        f_id, e.control.value
                                    ),
                                )
                            ]
                        )
                    ),
                ]
            )
            ref_audit_table.current.rows.append(row)

    def handle_apply_audit_fixes(e):
        fixes_to_apply = []
        for fid, action in selected_fixes.items():
            if action != "ignore":
                original = next(
                    (f for f in current_audit_findings if f["id"] == fid), None
                )
                if original:
                    fixes_to_apply.append(
                        {
                            "id": fid,
                            "action": action,
                            "data_encontrada": original["data_encontrada"],
                        }
                    )

        if not fixes_to_apply:
            dlg_audit.open = False
            page.update()
            return

        if controller.apply_date_fixes(fixes_to_apply):
            show_snackbar(
                page,
                f"✅ {len(fixes_to_apply)} correções aplicadas com sucesso!",
                "green",
            )
            handle_load_table(None)
        else:
            show_snackbar(page, "❌ Erro ao aplicar algumas correções.", "error")

        dlg_audit.open = False
        page.update()

    audit_view_log = ft.Column(
        [
            ft.Container(
                content=ft.ListView(ref=ref_audit_log, expand=True, spacing=2),
                height=300,
                bgcolor="#1E1E1E",
                padding=10,
                border_radius=5,
                border=ft.border.all(1, "grey"),
            ),
            ft.ProgressBar(ref=ref_audit_progress, bgcolor="grey", color="orange"),
        ],
        visible=True,
    )

    audit_view_results = ft.Column(
        [
            ft.Container(
                content=ft.Column(
                    [
                        ft.DataTable(
                            ref=ref_audit_table,
                            columns=[
                                ft.DataColumn(ft.Text("ID")),
                                ft.DataColumn(ft.Text("Arquivo")),
                                ft.DataColumn(ft.Text("BD")),
                                ft.DataColumn(ft.Text("Doc")),
                                ft.DataColumn(ft.Text("Ação")),
                            ],
                            column_spacing=15,
                            heading_row_height=40,
                        )
                    ],
                    scroll=ft.ScrollMode.ALWAYS,
                ),
                height=400,
            )
        ],
        visible=False,
    )

    dlg_audit = ft.AlertDialog(
        title=ft.Row(
            [
                ft.Icon(ft.icons.HISTORY, color="orange"),
                ft.Text("Auditoria Retroativa de Datas"),
            ]
        ),
        content=ft.Column(
            [
                ft.Text(
                    "Analisando integridade temporal entre BD e Arquivos Word.",
                    size=14,
                    color="grey",
                ),
                ft.Text("", ref=ref_audit_status, weight="bold"),
                ft.Stack([audit_view_log, audit_view_results], width=650),
            ],
            tight=True,
            spacing=10,
        ),
        actions=[
            ft.TextButton(
                "Fechar / Cancelar",
                on_click=lambda e: setattr(dlg_audit, "open", False) or page.update(),
            ),
            ft.ElevatedButton(
                "CONFIRMAR MUDANÇAS",
                bgcolor="orange",
                color="white",
                on_click=handle_apply_audit_fixes,
            ),
        ],
        shape=ft.RoundedRectangleBorder(radius=12),
    )

    def handle_factory_reset(e: ft.ControlEvent) -> None:
        if getattr(page, "is_db_locked", False):
            return

        def confirm_nuke(evt):
            dlg.open = False
            page.update()
            page.is_db_locked = True
            if controller.factory_reset():
                show_snackbar(
                    page,
                    "☢️ EXPLOSÃO COMPLETA! Banco voltou ao Estado Zero. (.bak salvo)",
                    "error",
                )
            page.is_db_locked = False

        dlg = ft.AlertDialog(
            title=ft.Row(
                [
                    ft.Icon(ft.icons.DANGEROUS, color="red"),
                    ft.Text("RESET NUCLEAR", color="red", weight="bold"),
                ]
            ),
            content=ft.Text(
                "Atenção, todas as configurações serão pulverizadas e tabelas apagadas.\nTem certeza?"
            ),
            actions=[
                ft.TextButton(
                    "Me Arrependi",
                    on_click=lambda e: setattr(dlg, "open", False) or page.update(),
                ),
                ft.ElevatedButton(
                    "SIM, FAZER EXPLOSÃO!",
                    on_click=confirm_nuke,
                    color="white",
                    bgcolor="red",
                ),
            ],
        )
        page.dialog = dlg
        dlg.open = True
        page.update()

    def handle_custom_delete(e: ft.ControlEvent) -> None:
        if getattr(page, "is_db_locked", False):
            return

        years, months = controller.get_dates_for_filter()
        dd_year = create_filter_dropdown(
            "Ano", [(y, y) for y in years], years[0] if years else None
        )
        dd_year.width = 150
        dd_month = create_filter_dropdown(
            "Mês", [(m, m) for m in months], months[0] if months else None
        )
        dd_month.width = 150

        ref_pin = ft.Ref[ft.TextField]()
        txt_pin = create_form_input("Digite CONFIRMAR", ft.icons.PASSWORD, ref_pin)
        txt_pin.width = 310

        def do_delete(evt):
            pin_val = ref_pin.current.value if ref_pin.current else ""
            if not pin_val or pin_val.strip().upper() != "CONFIRMAR":
                show_snackbar(
                    page, "Palavra de segurança incorreta. Digite CONFIRMAR.", "error"
                )
                return

            dlg.open = False
            page.update()
            page.is_db_locked = True

            qtd = controller.delete_by_period(dd_month.value, dd_year.value)
            if qtd > 0:
                show_snackbar(
                    page, f"✅ Limpeza Concluída: {qtd} registros apagados.", "green"
                )
            elif qtd == 0:
                show_snackbar(page, "⚠️ Nenhum registro encontrado.", "orange")
            else:
                show_snackbar(page, "❌ Ocorreu um erro ao apagar.", "error")
            page.is_db_locked = False

        dlg = ft.AlertDialog(
            title=ft.Row(
                [
                    ft.Icon(ft.icons.EVENT_BUSY, color="orange"),
                    ft.Text("Apagar por Período", weight="bold"),
                ]
            ),
            content=ft.Column(
                [
                    ft.Text("Selecione mês e ano para limpar."),
                    ft.Row([dd_month, dd_year]),
                    txt_pin,
                ],
                tight=True,
                spacing=15,
            ),
            actions=[
                ft.TextButton(
                    "Cancelar",
                    on_click=lambda e: setattr(dlg, "open", False) or page.update(),
                ),
                ft.ElevatedButton(
                    "EXCLUIR PERÍODO", on_click=do_delete, color="white", bgcolor="red"
                ),
            ],
            shape=ft.RoundedRectangleBorder(radius=12),
        )
        page.dialog = dlg
        dlg.open = True
        page.update()

    def handle_truncate_table(e: ft.ControlEvent) -> None:
        if getattr(page, "is_db_locked", False):
            return

        tabelas = controller.get_physical_tables()
        dd_table = create_filter_dropdown(
            "Tabela Física", [(t, t) for t in tabelas], tabelas[0] if tabelas else None
        )
        dd_table.width = 300

        ref_pin_trunc = ft.Ref[ft.TextField]()
        txt_pin = create_form_input(
            "Digite CONFIRMAR", ft.icons.PASSWORD, ref_pin_trunc
        )
        txt_pin.width = 300

        def do_truncate(evt):
            pin_val = ref_pin_trunc.current.value if ref_pin_trunc.current else ""
            if not pin_val or pin_val.strip().upper() != "CONFIRMAR":
                show_snackbar(page, "Palavra de segurança incorreta.", "error")
                return

            dlg.open = False
            page.update()
            page.is_db_locked = True

            if controller.truncate_table(dd_table.value):
                show_snackbar(
                    page, "✅ Destruição Executada! Tabela esvaziada.", "green"
                )
            else:
                show_snackbar(page, f"❌ Erro ao esvaziar {dd_table.value}.", "error")
            page.is_db_locked = False

        dlg = ft.AlertDialog(
            title=ft.Row(
                [
                    ft.Icon(ft.icons.GRID_OFF, color="red"),
                    ft.Text("Esvaziar Tabela", weight="bold"),
                ]
            ),
            content=ft.Column(
                [
                    ft.Text(
                        "Isso limpará TODOS os dados da tabela sem afetar outras.",
                        color="red",
                    ),
                    dd_table,
                    txt_pin,
                ],
                tight=True,
                spacing=15,
            ),
            actions=[
                ft.TextButton(
                    "Cancelar",
                    on_click=lambda e: setattr(dlg, "open", False) or page.update(),
                ),
                ft.ElevatedButton(
                    "ESVAZIAR TABELA",
                    on_click=do_truncate,
                    color="white",
                    bgcolor="red",
                ),
            ],
            shape=ft.RoundedRectangleBorder(radius=12),
        )
        page.dialog = dlg
        dlg.open = True
        page.update()

    ref_mock_qtd = ft.Ref[ft.TextField]()

    def open_mock_dialog(e):
        page.dialog = dlg_mock
        dlg_mock.open = True
        page.update()

    def handle_generate_mock(e: ft.ControlEvent):
        qtd_str = ref_mock_qtd.current.value
        if not qtd_str or not qtd_str.isdigit():
            show_snackbar(page, "Digite uma quantidade válida (Ex: 100).", "error")
            return

        qtd = int(qtd_str)
        dlg_mock.open = False
        page.is_db_locked = True
        show_snackbar(page, f"⏳ Injetando {qtd} registros simulados...", "blue_info")
        page.update()

        async def run_async():
            sucesso = await controller.inject_mock_data_async(qtd)
            page.is_db_locked = False
            if sucesso:
                show_snackbar(
                    page, f"✅ {qtd} termos e ativos injetados com sucesso!", "green"
                )
                if ref_db_dropdown.current.value in [
                    "tb_termos",
                    "tb_ativos",
                    "vw_historico_legado",
                ]:
                    handle_load_table()
            else:
                show_snackbar(page, "❌ Erro ao injetar dados simulados.", "error")
            page.update()

        asyncio.run_coroutine_threadsafe(run_async(), page.loop)

    dlg_mock = ft.AlertDialog(
        title=ft.Row(
            [ft.Icon(ft.icons.SCIENCE, color="purple"), ft.Text("Gerador de Carga")]
        ),
        content=ft.Column(
            [
                ft.Text(
                    "Quantos registros aleatórios deseja injetar no banco de dados?"
                ),
                create_form_input(
                    "Quantidade (Ex: 100, 500, 2000)", ft.icons.NUMBERS, ref_mock_qtd
                ),
            ],
            tight=True,
            spacing=15,
        ),
        actions=[
            ft.TextButton(
                "Cancelar",
                on_click=lambda e: setattr(dlg_mock, "open", False) or page.update(),
            ),
            ft.ElevatedButton(
                "INJETAR DADOS",
                on_click=handle_generate_mock,
                color="white",
                bgcolor="purple",
            ),
        ],
        shape=ft.RoundedRectangleBorder(radius=12),
    )

    # --- 2.8. Closures de Regras ---
    def handle_add_rule(e: ft.ControlEvent) -> None:
        search = ref_rule_search.current.value
        target = ref_rule_target.current.value
        replace = ref_rule_replace.current.value

        if not search or not replace:
            show_snackbar(
                page, "⚠️ Preencha os campos de busca e substituição.", "orange"
            )
            return

        if controller.add_rule(target, search, replace):
            ref_rule_search.current.value = ""
            ref_rule_replace.current.value = ""
            refresh_rules_ui()
            show_snackbar(page, "✅ Regra adicionada ao motor com sucesso!", "green")
        else:
            show_snackbar(page, "❌ Erro ao salvar regra.", "error")

    def handle_delete_rule(target: str, search: str) -> None:
        if controller.delete_rule(target, search):
            refresh_rules_ui()
            show_snackbar(page, f"🗑️ Regra '{search}' removida.", "green")
        else:
            show_snackbar(page, "❌ Erro ao remover regra.", "error")

    # --- 2.9. Closures Ingestão ---
    def handle_save_gemini_key(e: ft.ControlEvent) -> None:
        controller.save_gemini_key(ref_gemini_key.current.value)
        show_snackbar(page, "✅ API Key do Gemini Salva com Sucesso!", "green")

    def handle_pause_sync(e: ft.ControlEvent) -> None:
        btn = ref_btn_pause.current.content
        if sync_state["pause"]:
            sync_state["pause"] = False
            btn.text = "Pausar Sincronização"
            btn.icon = ft.icons.PAUSE
            ref_sync_log.current.value = "▶️ Sincronização retomada..."
        else:
            sync_state["pause"] = True
            btn.text = "Retomar Sincronização"
            btn.icon = ft.icons.PLAY_ARROW
            ref_sync_log.current.value = "⏸️ Sincronização pausada..."
        page.update()

    def handle_cancel_sync(e: ft.ControlEvent) -> None:
        sync_state["cancel"] = True
        ref_btn_pause.current.visible = False
        ref_btn_cancel.current.visible = False
        ref_btn_start.current.visible = True
        ref_sync_log.current.value = "🛑 Cancelando sincronização..."
        page.update()

    async def handle_sync_batch(e: ft.ControlEvent) -> None:
        api_key = controller.get_gemini_key()
        if not api_key or len(api_key.strip()) < 10:
            show_snackbar(
                page,
                "❌ ERRO: Necessário configurar uma API Key do Google IA.",
                "error",
            )
            return

        sync_state["pause"] = False
        sync_state["cancel"] = False
        ref_btn_start.current.visible = False
        ref_btn_pause.current.visible = True
        ref_btn_cancel.current.visible = True

        btn_pause = ref_btn_pause.current.content
        btn_pause.text = "Pausar Sincronização"
        btn_pause.icon = ft.icons.PAUSE

        ref_sync_progress.current.visible = True
        ref_sync_log.current.value = "Iniciando varredura na rede..."

        years_txt = ref_sync_years.current.value or ""
        months_txt = ref_sync_months.current.value or ""
        target_years = [y.strip() for y in years_txt.split(",") if y.strip()]
        target_months = [m.strip() for m in months_txt.split(",") if m.strip()]
        page.update()

        try:
            async for status in controller.run_sync_generator(
                target_years, target_months, sync_state
            ):
                if status["type"] == "error":
                    show_snackbar(page, f"❌ {status['msg']}", "error")
                    break
                elif status["type"] == "log":
                    ref_sync_log.current.value = status["msg"]
                    page.update()
                elif status["type"] == "progress":
                    pct = status["current"] / max(1, status["total"])
                    ref_sync_progress.current.value = pct
                    ref_sync_log.current.value = f"[{status['current']}/{status['total']}] {status['action']} -> {status['filename']}"
                    page.update()
                elif status["type"] == "done":
                    stats = status["stats"]
                    ref_sync_log.current.value = f"🏁 Fim: {stats['sucesso']} importados, {stats['pulados']} pulados."
                    if stats["erro"] > 0:
                        show_snackbar(
                            page,
                            f"⚠️ {stats['sucesso']} salvos, mas {stats['erro']} falharam! Olhe a Quarentena.",
                            "orange",
                        )
                    elif stats["sucesso"] > 0:
                        show_snackbar(
                            page,
                            f"✅ Maravilha! {stats['sucesso']} termos importados com sucesso.",
                            "green",
                        )
                    else:
                        show_snackbar(
                            page,
                            "ℹ️ Nenhum arquivo novo processado na rede.",
                            "blue_info",
                        )
                    page.update()
        except Exception as ex:
            show_snackbar(page, f"❌ Falha Crítica do Motor: {ex}", "error")
        finally:
            ref_btn_start.current.visible = True
            ref_btn_pause.current.visible = False
            ref_btn_cancel.current.visible = False
            page.update()

    # --- 2.10. Tabelas & DB Audit ---
    dropdown_tabelas = create_filter_dropdown("Tabela", [], None, ref=ref_db_dropdown)
    dropdown_tabelas.width = 200
    dropdown_tabelas.text_size = 14
    dropdown_tabelas.on_change = lambda e: (
        handle_search_table(e) if ref_db_search.current.value else handle_load_table(e)
    )

    options_limit = [(str(i), str(i)) for i in range(50, 501, 50)]
    dropdown_limit = create_filter_dropdown(
        "Linhas", options_limit, "50", ref=ref_db_limit
    )
    dropdown_limit.width = 100
    dropdown_limit.text_size = 14
    dropdown_limit.on_change = lambda e: (
        handle_search_table(e) if ref_db_search.current.value else handle_load_table(e)
    )

    input_db_search = create_form_input(
        "Pesquisar na tabela... (Enter ao Fim)", ft.icons.SEARCH, ref_db_search
    )
    input_db_search.width = 300
    input_db_search.height = 45
    input_db_search.on_submit = handle_search_table

    file_picker_import = ft.FilePicker(on_result=handle_import_csv)
    page.overlay.append(file_picker_import)

    view_auditoria = ft.Column(
        [
            create_page_header(
                ft.icons.TABLE_CHART,
                "Auditoria e Administração",
                "Modifique campos diretamente nas Tabelas.",
            ),
            ft.Divider(height=40, color="transparent"),
            create_standard_card(
                padding=15,
                expand=True,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                dropdown_tabelas,
                                dropdown_limit,
                                input_db_search,
                                ft.Container(expand=True),
                                ft.Container(
                                    width=240,
                                    content=create_primary_button(
                                        "Importar CSV",
                                        icon_name=ft.icons.UPLOAD,
                                        on_click=lambda _: (
                                            file_picker_import.pick_files(
                                                allowed_extensions=["csv"]
                                            )
                                        ),
                                        color_override="#00ACC1",
                                    ),
                                ),
                                ft.Container(
                                    width=240,
                                    content=create_primary_button(
                                        "Exportar CSV",
                                        icon_name=ft.icons.DOWNLOAD,
                                        on_click=handle_export_csv,
                                    ),
                                ),
                            ],
                            spacing=20,
                        ),
                        ft.Divider(height=30, color="lightgrey"),
                        ft.Container(
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
                                                content=ft.DataTable(
                                                    ref=ref_db_table,
                                                    column_spacing=50,
                                                    columns=[
                                                        ft.DataColumn(
                                                            ft.Text(
                                                                "Aguardando Busca...",
                                                                size=16,
                                                            )
                                                        )
                                                    ],
                                                    rows=[],
                                                )
                                            )
                                        ],
                                    )
                                ],
                            ),
                        ),
                        ft.Divider(height=10, color="transparent"),
                        ft.Row(
                            [
                                ft.IconButton(
                                    ft.icons.CHEVRON_LEFT,
                                    ref=ref_btn_prev,
                                    disabled=True,
                                    on_click=handle_prev_page,
                                    icon_color="blue",
                                ),
                                ft.Text(
                                    "Página 1", ref=ref_txt_page, weight="bold", size=14
                                ),
                                ft.IconButton(
                                    ft.icons.CHEVRON_RIGHT,
                                    ref=ref_btn_next,
                                    disabled=True,
                                    on_click=handle_next_page,
                                    icon_color="blue",
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                    ],
                    expand=True,
                ),
            ),
        ],
        expand=True,
    )

    # --- 2.11. Motor Inteligente ---
    input_search = create_form_input(
        "Palavra-chave (Ex: Tclado)", ft.icons.SEARCH, ref_rule_search
    )
    input_search.expand = 2
    dropdown_target = create_filter_dropdown(
        "Alvo",
        [("Fabricante", "Fabricante"), ("Tipo", "Tipo")],
        "Fabricante",
        ref=ref_rule_target,
    )
    dropdown_target.expand = 1
    dropdown_target.text_size = 14
    input_replace = create_form_input(
        "Substituir por (Ex: Teclado)", ft.icons.FIND_REPLACE, ref_rule_replace
    )
    input_replace.expand = 2

    view_regras = ft.Column(
        [
            create_page_header(
                ft.icons.PSYCHOLOGY,
                "Motor de Regras",
                "Gerencie o dicionário de padronização.",
            ),
            ft.Divider(height=40, color="transparent"),
            create_standard_card(
                padding=15,
                expand=True,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                input_search,
                                dropdown_target,
                                input_replace,
                                ft.IconButton(
                                    icon=ft.icons.ADD_CIRCLE,
                                    icon_color="green",
                                    icon_size=50,
                                    on_click=handle_add_rule,
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=20,
                        ),
                        ft.Divider(height=30, color="lightgrey"),
                        ft.Text(
                            "Regras Ativas",
                            weight="bold",
                            size=18,
                            color=COLORS.get("text", "black"),
                        ),
                        ft.Column(ref=ref_rules_list, controls=[], spacing=10),
                    ],
                    expand=True,
                ),
            ),
        ],
        expand=True,
    )

    # --- 2.12. UTI do Banco ---
    def uti_card(
        icon, title, desc, btn_text, btn_icon, on_click, color="blue", is_danger=False
    ):
        return ft.Container(
            width=320,
            height=300,
            padding=25,
            border_radius=12,
            bgcolor=COLORS.get("card_bg", "white"),
            border=ft.border.all(
                2, color if is_danger else COLORS.get("border", "#E0E0E0")
            ),
            shadow=ft.BoxShadow(
                blur_radius=15, color=ft.colors.with_opacity(0.05, "black")
            ),
            content=ft.Column(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Column(
                        spacing=12,
                        controls=[
                            ft.Container(
                                padding=12,
                                bgcolor=ft.colors.with_opacity(0.1, color),
                                border_radius=50,
                                content=ft.Icon(icon, color=color, size=35),
                            ),
                            ft.Text(
                                title,
                                weight="w900",
                                size=16,
                                color=color
                                if is_danger
                                else COLORS.get("text", "black"),
                            ),
                            ft.Text(
                                desc,
                                size=13,
                                color=COLORS.get("text_secondary", "grey"),
                            ),
                        ],
                    ),
                    create_primary_button(
                        btn_text,
                        icon_name=btn_icon,
                        color_override=color,
                        on_click=on_click,
                        full_width=True,
                    ),
                ],
            ),
        )

    def create_zone_header(title, icon, color):
        return ft.Container(
            padding=ft.padding.only(top=20, bottom=10),
            content=ft.Row(
                spacing=10,
                controls=[
                    ft.Icon(icon, color=color, size=24),
                    ft.Text(title.upper(), weight="w900", size=16, color=color),
                ],
            ),
        )

    view_manutencao = ft.Column(
        expand=True,
        controls=[
            create_page_header(
                ft.icons.MEDICAL_SERVICES,
                "UTI do Banco de Dados",
                "Procedimentos avançados de recuperação e saúde.",
            ),
            ft.Divider(height=10, color="transparent"),
            ft.Column(
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=15,
                controls=[
                    create_zone_header(
                        "Zona de Manutenção de Rotina", ft.icons.VERIFIED_USER, "blue"
                    ),
                    ft.Row(
                        wrap=True,
                        spacing=20,
                        run_spacing=20,
                        controls=[
                            uti_card(
                                ft.icons.ANALYTICS,
                                "Diagnóstico da Master",
                                "Verifica integridade.",
                                "Rodar Análise",
                                ft.icons.PLAY_ARROW,
                                lambda e: asyncio.run_coroutine_threadsafe(
                                    handle_db_scan(e), page.loop
                                ),
                                "blue",
                            ),
                            uti_card(
                                ft.icons.BOLT,
                                "Otimização de Índices",
                                "Cria índices rápidos.",
                                "Otimizar Engine",
                                ft.icons.SPEED,
                                handle_optimize,
                                "green",
                            ),
                            uti_card(
                                ft.icons.AUTO_STORIES,
                                "Reconstrução de B-Trees",
                                "Refaz busca.",
                                "Reindexar Base",
                                ft.icons.AUTORENEW,
                                handle_reindex,
                                "teal",
                            ),
                            uti_card(
                                ft.icons.BUILD_CIRCLE,
                                "Limpeza de Bytes (VACUUM)",
                                "Reduz tamanho do .db.",
                                "Executar Vacuum",
                                ft.icons.BUILD,
                                handle_vacuum,
                                "blue",
                            ),
                            uti_card(
                                ft.icons.BACKUP,
                                "Gerador de Snapshot",
                                "Clona e salva backup.",
                                "Salvar Clone .db",
                                ft.icons.SAVE_ALT,
                                handle_backup,
                                "purple",
                            ),
                        ],
                    ),
                    ft.Divider(height=20, color="lightgrey"),
                    create_zone_header(
                        "Zona de Limpeza (Cuidado)", ft.icons.WARNING_AMBER, "orange"
                    ),
                    ft.Row(
                        wrap=True,
                        spacing=20,
                        run_spacing=20,
                        controls=[
                            uti_card(
                                ft.icons.HISTORY,
                                "Auditoria Retroativa",
                                "Busca erros de data nos Docs.",
                                "Escanear Docs",
                                ft.icons.TRAVEL_EXPLORE,
                                lambda e: asyncio.run_coroutine_threadsafe(
                                    handle_date_audit_start(e), page.loop
                                ),
                                "orange",
                            ),
                            uti_card(
                                ft.icons.CONTROL_POINT_DUPLICATE,
                                "Apagar Duplicatas (Clones)",
                                "Destrói termos repetidos.",
                                "Escanear Clones",
                                ft.icons.CLEANING_SERVICES,
                                handle_delete_duplicates,
                                "orange",
                            ),
                            uti_card(
                                ft.icons.EVENT_BUSY,
                                "Limpeza por Período",
                                "Bomba de Precisão.",
                                "Apagar Período",
                                ft.icons.CALENDAR_MONTH,
                                handle_custom_delete,
                                "orange",
                            ),
                        ],
                    ),
                    ft.Divider(height=20, color="lightgrey"),
                    create_zone_header(
                        "Zona Crítica (Perigo Extremo)", ft.icons.GPP_BAD, "red"
                    ),
                    ft.Row(
                        wrap=True,
                        spacing=20,
                        run_spacing=20,
                        controls=[
                            uti_card(
                                ft.icons.GRID_OFF,
                                "Esvaziar Tabela Específica",
                                "Destrói dados de uma tabela.",
                                "Esvaziar Tabela",
                                ft.icons.NO_CELL,
                                handle_truncate_table,
                                "red",
                                is_danger=True,
                            ),
                            uti_card(
                                ft.icons.DANGEROUS,
                                "Bomba Nuclear (Reset Total)",
                                "Elimina todas as tabelas!",
                                "DELETAR BANCO",
                                ft.icons.DELETE_FOREVER,
                                handle_factory_reset,
                                "red",
                                is_danger=True,
                            ),
                        ],
                    ),
                    ft.Divider(height=20, color="lightgrey"),
                    create_zone_header(
                        "Zona de Simulação Científica", ft.icons.SCIENCE, "purple"
                    ),
                    ft.Row(
                        wrap=True,
                        spacing=20,
                        run_spacing=20,
                        controls=[
                            uti_card(
                                ft.icons.SCIENCE,
                                "Gerador de Carga (Stress Test)",
                                "Injeta aleatórios.",
                                "Injetar Mocks",
                                ft.icons.BOLT,
                                open_mock_dialog,
                                "purple",
                            ),
                        ],
                    ),
                    ft.Container(height=40),
                ],
            ),
        ],
    )

    # --- 2.13. Ingestão ETL ---
    view_ingestao = ft.Column(
        [
            create_page_header(
                ft.icons.CLOUD_SYNC,
                "Motor de Ingestão",
                "Rastreio automatizado de termos na rede.",
            ),
            ft.Divider(height=50, color="transparent"),
            create_standard_card(
                padding=15,
                expand=True,
                content=ft.Column(
                    [
                        ft.Icon(
                            ft.icons.CLOUD_SYNC,
                            size=120,
                            color=COLORS.get("text_secondary", "grey"),
                        ),
                        ft.Text("Sincronização em Lote", size=26, weight="bold"),
                        ft.Text(
                            "A IA varre pastas predefinidas na rede e injeta documentos direto no banco.",
                            size=16,
                            color=COLORS.get("text_secondary", "grey"),
                        ),
                        ft.Divider(height=20, color="transparent"),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=20,
                            controls=[
                                ft.Container(
                                    width=215,
                                    content=create_form_input(
                                        "Anos (ex: 2023, 2024)",
                                        ft.icons.CALENDAR_TODAY,
                                        ref_sync_years,
                                    ),
                                ),
                                ft.Container(
                                    width=215,
                                    content=create_form_input(
                                        "Meses (ex: Janeiro)",
                                        ft.icons.CALENDAR_MONTH,
                                        ref_sync_months,
                                    ),
                                ),
                            ],
                        ),
                        ft.Container(height=10),
                        ft.Container(
                            ref=ref_btn_start,
                            width=450,
                            content=create_primary_button(
                                "Iniciar Varredura na Rede",
                                icon_name=ft.icons.PLAY_ARROW,
                                on_click=lambda e: asyncio.run_coroutine_threadsafe(
                                    handle_sync_batch(e), page.loop
                                ),
                                full_width=True,
                            ),
                        ),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=20,
                            controls=[
                                ft.Container(
                                    ref=ref_btn_pause,
                                    width=215,
                                    visible=False,
                                    content=create_primary_button(
                                        "Pausar Sincronização",
                                        icon_name=ft.icons.PAUSE,
                                        color_override="orange",
                                        on_click=handle_pause_sync,
                                        full_width=True,
                                    ),
                                ),
                                ft.Container(
                                    ref=ref_btn_cancel,
                                    width=215,
                                    visible=False,
                                    content=create_primary_button(
                                        "Cancelar Sincronização",
                                        icon_name=ft.icons.CANCEL,
                                        color_override="red",
                                        on_click=handle_cancel_sync,
                                        full_width=True,
                                    ),
                                ),
                            ],
                        ),
                        ft.Container(height=20),
                        ft.Divider(height=10, color="lightgrey"),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[
                                ft.Container(
                                    width=350,
                                    content=create_form_input(
                                        "Google Gemini API Key",
                                        ft.icons.PASSWORD,
                                        ref_gemini_key,
                                        value=controller.get_gemini_key(),
                                    ),
                                ),
                                ft.IconButton(
                                    icon=ft.icons.SAVE,
                                    icon_color="green",
                                    tooltip="Salvar Chave",
                                    on_click=handle_save_gemini_key,
                                ),
                            ],
                        ),
                        ft.Divider(height=10, color="transparent"),
                        ft.ProgressBar(
                            ref=ref_sync_progress,
                            value=0,
                            visible=False,
                            color="green",
                            bgcolor="lightgrey",
                            height=12,
                        ),
                        ft.Text(
                            ref=ref_sync_log,
                            value="",
                            size=14,
                            color="blue",
                            italic=True,
                            text_align="center",
                            width=float("inf"),
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=15,
                    expand=True,
                ),
            ),
        ],
        expand=True,
    )

    # --- 2.14. Injeção das Propriedades de Password ---
    ref_gemini_key.current.password = True
    ref_gemini_key.current.can_reveal_password = True

    views = [view_auditoria, view_regras, view_manutencao, view_ingestao]

    # --- 2.15. Barra Lateral ---
    active_icon_color = COLORS.get("primary", "blue")
    inactive_icon_color = COLORS.get("text_secondary", "grey")

    current_nav_state = {"index": 0}
    nav_column_ref = ft.Ref[ft.Column]()

    def _build_nav_icon(
        idx: int, icon_active: str, icon_inactive: str, tooltip_text: str
    ) -> ft.Container:
        is_active = current_nav_state["index"] == idx
        return ft.Container(
            content=ft.Icon(
                name=icon_active if is_active else icon_inactive,
                size=26,
                color=active_icon_color if is_active else inactive_icon_color,
            ),
            width=55,
            height=55,
            alignment=ft.alignment.center,
            border_radius=50,
            on_click=lambda e: _switch_custom_view(idx),
            tooltip=tooltip_text,
            ink=True,
        )

    def _get_nav_controls() -> List[ft.Control]:
        return [
            _build_nav_icon(
                0, ft.icons.TABLE_CHART, ft.icons.TABLE_CHART_OUTLINED, "Auditoria"
            ),
            _build_nav_icon(
                1, ft.icons.PSYCHOLOGY, ft.icons.PSYCHOLOGY_OUTLINED, "Regras"
            ),
            _build_nav_icon(
                2, ft.icons.MEDICAL_SERVICES, ft.icons.MEDICAL_SERVICES_OUTLINED, "UTI"
            ),
            _build_nav_icon(
                3, ft.icons.CLOUD_SYNC, ft.icons.CLOUD_SYNC_OUTLINED, "Ingestão"
            ),
        ]

    def _update_nav_ui():
        if not nav_column_ref.current:
            return
        nav_column_ref.current.controls = _get_nav_controls()
        nav_column_ref.current.update()

    def _switch_custom_view(idx: int):
        if current_nav_state["index"] == idx:
            return
        current_nav_state["index"] = idx
        ref_right_panel.current.content = views[idx]
        ref_right_panel.current.update()
        _update_nav_ui()

    nav_menu = ft.Column(
        ref=nav_column_ref,
        controls=_get_nav_controls(),
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=10,
    )

    left_sidebar = ft.Column(
        width=100,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Container(height=20),
            ft.Container(content=nav_menu, expand=True),
            ft.Container(
                padding=ft.padding.only(bottom=20),
                content=ft.Container(
                    content=ft.Icon(
                        ft.icons.LOCK, color=COLORS.get("error", "red"), size=28
                    ),
                    width=55,
                    height=55,
                    alignment=ft.alignment.center,
                    border_radius=50,
                    on_click=handle_lock_vault,
                    tooltip="Trancar Cofre",
                    ink=True,
                ),
            ),
        ],
    )

    # --- 2.16. Lock Screen Completo Render ---
    pass_input = create_form_input(
        "Senha de Administrador",
        ft.icons.LOCK,
        ref_pass_input,
        on_submit=lambda e: asyncio.run_coroutine_threadsafe(
            handle_unlock(e), page.loop
        ),
    )
    pass_input.password = True
    pass_input.can_reveal_password = True
    pass_input.text_align = "center"

    lock_screen = ft.Container(
        ref=ref_lock_container,
        expand=True,
        alignment=ft.alignment.center,
        bgcolor=ft.colors.with_opacity(0.85, "#101216"),
        content=ft.Container(
            width=420,
            bgcolor=COLORS.get("text_inverse", "white"),
            border_radius=24,
            padding=ft.padding.all(40),
            shadow=ft.BoxShadow(
                blur_radius=50,
                spread_radius=-10,
                color=ft.colors.with_opacity(0.4, "black"),
                offset=ft.Offset(0, 15),
            ),
            content=ft.Column(
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=20,
                controls=[
                    ft.Container(
                        padding=20,
                        bgcolor=ft.colors.with_opacity(
                            0.1, COLORS.get("primary", "blue")
                        ),
                        border_radius=100,
                        content=ft.Icon(
                            ft.icons.ADMIN_PANEL_SETTINGS_ROUNDED,
                            size=45,
                            color=COLORS.get("primary", "blue"),
                        ),
                    ),
                    ft.Column(
                        spacing=5,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Text(
                                "Modo Administrador",
                                size=24,
                                weight="w800",
                                color=COLORS.get("text", "black"),
                            ),
                            ft.Text(
                                "Digite a senha de segurança para acessar as configurações avançadas e o MDM.",
                                size=13,
                                text_align=ft.TextAlign.CENTER,
                                color=COLORS.get("text_secondary", "grey"),
                            ),
                        ],
                    ),
                    ft.Container(height=10),
                    pass_input,
                    ft.Container(height=5),
                    create_primary_button(
                        text="Acessar Sistema",
                        icon_name=ft.icons.FINGERPRINT,
                        on_click=lambda e: asyncio.run_coroutine_threadsafe(
                            handle_unlock(e), page.loop
                        ),
                        full_width=True,
                    ),
                    ft.TextButton(
                        "Voltar para Configurações",
                        icon=ft.icons.ARROW_BACK_ROUNDED,
                        on_click=handle_go_back,
                        style=ft.ButtonStyle(
                            color=COLORS.get("text_secondary", "grey")
                        ),
                    ),
                ],
            ),
        ),
    )

    # --- 2.17. MDM Container ---
    mdm_dashboard = ft.Container(
        ref=ref_mdm_container,
        visible=False,
        expand=True,
        bgcolor=COLORS.get("background", "white"),
        content=ft.Row(
            [
                left_sidebar,
                ft.Container(
                    ref=ref_right_panel,
                    content=view_auditoria,
                    expand=True,
                    padding=ft.padding.all(60),
                ),
            ],
            expand=True,
        ),
    )

    page.add(ft.Stack(controls=[mdm_dashboard, lock_screen], expand=True))
