"""
Módulo de Visualização Principal (View Layer).

Interface central do gerador de termos, responsável pela orquestração
dos formulários de entrada, seleção de ativos e navegação principal.
"""

# ==============================================================================
# 1. IMPORTS E DEPENDÊNCIAS
# ==============================================================================
import asyncio
import os
from typing import Any, Dict, Optional

import flet as ft

import core.strings as S
from controllers.gateway_factory import get_asset_gateway, get_term_gateway
from controllers.services import AssetService, TermService

# --- 1.1. Infraestrutura Core e Middlewares ---
from core.settings import COLORS, get_header_color, load_setting
from data.state import AppState
from views.dashboard_view import build_dashboard_tab

# --- 1.3. Sub-Visualizações Embutidas ---
from views.history_view import build_history_tab

# --- 1.2. Componentes Sintéticos da View Layer ---
from views.ui import (
    create_filter_dropdown,
    create_form_input,
    create_primary_button,
    create_smart_asset_card,
    create_standard_card,
    shake_control,
    show_snackbar,
)

# ==============================================================================
# 2. CONSTANTES DE GEOMETRIA E ESTADO
# ==============================================================================

MIN_LIST_HEIGHT: int = 150


# ==============================================================================
# 3. FÁBRICA PRINCIPAL DA VISUALIZAÇÃO HOME
# ==============================================================================


def build_home_view(page: ft.Page, app_state: AppState) -> None:
    """Constrói a View Raiz do Sistema e Atrela o AppState Central.

    Implementa Layout Responsivo Baseado em State Machine, injetando Overlay Modal de
    Progresso e Navigation Rail Principal.

    Args:
        page (ft.Page): Objeto raiz Mutável Flet.
        app_state (AppState): Singleton Compartilhado de Memória Volátil.
    """

    # --- 3.1. Setup Inicial e Limpeza de Lixo React ---
    page.clean()
    page.data = "livre"

    # --- 3.2. Resolução de Contexto Modo de Teste ---
    current_config = load_setting()
    is_test_mode = current_config.get("modo_teste", False)
    focus_color = (
        COLORS.get("orange", "orange")
        if is_test_mode
        else COLORS.get("primary", "blue")
    )

    if is_test_mode and not app_state.nome:
        app_state.chamado = S.SIM_CHAMADO
        app_state.nome = S.SIM_NOME
        app_state.area = S.SIM_AREA
        app_state.operacao = S.SIM_OPERACAO
        app_state.obs = S.SIM_OBS

    # --- 3.3. Âncoras Dinâmicas de Mutação Virtual Dom ---

    list_container = ft.Column(spacing=8)

    refs = {
        "patrimonio": ft.Ref[ft.TextField](),
        "nome": ft.Ref[ft.TextField](),
        "chamado": ft.Ref[ft.TextField](),
        "area": ft.Ref[ft.TextField](),
        "obs": ft.Ref[ft.TextField](),
        "insumo_nome": ft.Ref[ft.TextField](),
        "insumo_qtd": ft.Ref[ft.TextField](),
    }
    ref_op = ft.Ref[ft.Dropdown]()
    ref_right_panel = ft.Ref[ft.Container]()

    # --- 3.4. Refs do Modal Loading ---
    ref_overlay, ref_overlay_card, ref_icon = (
        ft.Ref[ft.Container](),
        ft.Ref[ft.Container](),
        ft.Ref[ft.Icon](),
    )
    ref_txt, ref_progress_bar = ft.Ref[ft.Text](), ft.Ref[ft.ProgressBar]()
    ref_links, ref_close = ft.Ref[ft.Column](), ft.Ref[ft.Container]()

    # --- 3.5. Refs do Modal de Inserção Genérica/Forçada de Hardware ---
    refs_new_asset = {
        "patrimonio": ft.Ref[ft.TextField](),
        "modelo": ft.Ref[ft.TextField](),
        "serial": ft.Ref[ft.TextField](),
        "fabricante": ft.Ref[ft.TextField](),
        "tipo": ft.Ref[ft.Dropdown](),
    }

    # --- 3.6. Closures e Disparadores de Eventos de Interface ---

    def inject_new_item(item: Dict[str, Any]) -> None:
        """Faz Append no Topo da Lista UI de um novo Equipamento com Animação."""
        if list_container.controls and list_container.controls[0].key == "empty_state":
            list_container.controls.clear()

        new_card = _build_asset_card(item)

        new_card.opacity = 0
        new_card.offset = ft.transform.Offset(-0.05, 0)
        new_card.animate_opacity = ft.animation.Animation(400, "easeOut")
        new_card.animate_offset = ft.animation.Animation(400, "easeOutCubic")

        list_container.controls.insert(0, new_card)
        page.update()

        async def play_entrance_animation():
            await asyncio.sleep(0.05)
            new_card.opacity = 1
            new_card.offset = ft.transform.Offset(0, 0)
            new_card.update()

        asyncio.run_coroutine_threadsafe(play_entrance_animation(), page.loop)

    def remove_specific_item(item: Dict[str, Any], control: ft.Control) -> None:
        """Deleta da Memória RAM Central e Expurga o Nó da Interface."""
        # --- 3.6.1. Prevenção Ghost Items: Busca Exata por Referência e Fallbacks ---
        to_remove = None
        for saved_item in app_state.lista_ativos_memoria:
            if id(saved_item) == id(item):
                to_remove = saved_item
                break
        if not to_remove and item in app_state.lista_ativos_memoria:
            to_remove = item

        if to_remove:
            app_state.lista_ativos_memoria.remove(to_remove)

        if control in list_container.controls:
            list_container.controls.remove(control)

        if not list_container.controls:
            list_container.controls.append(_create_empty_state())

        page.update()

    async def full_list_refresh() -> None:
        """Gatilho Síncrono Total que repinta todos os cartões baseado na RAM."""
        list_container.controls.clear()
        if not app_state.lista_ativos_memoria:
            list_container.controls.append(_create_empty_state())
        else:
            AssetService.sort_assets_for_ui(app_state.lista_ativos_memoria)
            for item in app_state.lista_ativos_memoria:
                card = _build_asset_card(item)
                list_container.controls.append(card)
        page.update()

    def handle_reset_form(e: ft.ControlEvent) -> None:
        """Limpeza Destrutiva Manual Solicitada pelo Botão de Lixeira Global."""
        app_state.reset_state()
        for key in refs:
            if refs[key].current:
                refs[key].current.value = ""
                if key == "insumo_qtd":
                    refs[key].current.value = "1"
        dlg_reset.open = False
        page.update()

    # --- 3.7. Handlers do Fluxo Adição de Ativo Genérico ---
    def open_manual_dialog(e):
        """Abre Popup Limpo para Entradas Genéricas."""
        refs_new_asset["patrimonio"].current.value = ""
        refs_new_asset["modelo"].current.value = ""
        refs_new_asset["serial"].current.value = ""
        refs_new_asset["fabricante"].current.value = ""
        refs_new_asset["tipo"].current.value = "Notebook"
        refs_new_asset["modelo"].current.error_text = None

        page.dialog = dlg_new_asset
        dlg_new_asset.open = True
        page.update()

        asyncio.run_coroutine_threadsafe(full_list_refresh(), page.loop)
        if refs["chamado"].current:
            refs["chamado"].current.focus()

    def handle_manual_asset_confirm(e: ft.ControlEvent) -> None:
        """Efetiva o Payload Form Genérico Para a RAM Central."""
        pat = refs_new_asset["patrimonio"].current.value
        desc = refs_new_asset["modelo"].current.value
        serial = refs_new_asset["serial"].current.value
        tipo = refs_new_asset["tipo"].current.value
        fabricante = refs_new_asset["fabricante"].current.value

        if not desc:
            refs_new_asset["modelo"].current.error_text = S.MSG_CAMPO_OBRIGATORIO
            refs_new_asset["modelo"].current.update()
            return

        if not pat:
            pat = (
                app_state.patrimonio
                or f"MANUAL-{len(app_state.lista_ativos_memoria) + 1}"
            )

        new_asset = {
            "patrimonio": pat,
            "tipo": tipo,
            "categoria": tipo,
            "fabricante": fabricante if fabricante else "Genérico",
            "modelo": desc,
            "serial": serial if serial else "S/N",
            "descricao_visual": f"{tipo} {fabricante or ''} {desc}".strip(),
            "qtd": "1",
            "origem": "Manual",
        }

        app_state.lista_ativos_memoria.append(new_asset)
        dlg_new_asset.open = False
        inject_new_item(new_asset)

        refs["patrimonio"].current.value = ""
        app_state.patrimonio = ""
        refs["patrimonio"].current.focus()
        page.update()

    async def handle_asset_search(e: ft.ControlEvent) -> None:
        """Gatilho Web Restful na Service Layer para Fetch GLPI.

        Suporta Animações UX Inteligentes e Fallbacks.
        """
        value = refs["patrimonio"].current.value.strip()
        # --- 3.8. XSS / Null Protection — Bloqueio de Inputs Perigosos ou Vazios Antes do I/O ---
        if not value or "<" in value or ">" in value or len(value) > 50:
            await shake_control(refs["patrimonio"])
            show_snackbar(page, S.MSG_BUSCA_INVALIDA, "error", ft.icons.GPP_BAD)
            return

        refs["patrimonio"].current.disabled = True
        refs["patrimonio"].current.suffix = ft.Container(
            content=ft.ProgressRing(
                width=16, height=16, stroke_width=2, color=focus_color
            ),
            padding=ft.padding.only(right=15),
        )
        page.update()
        await asyncio.sleep(0.1)

        # --- 3.8.1. Instanciamento via Factory — View Agnóstica às Implementações Concretas ---
        asset_gateway = get_asset_gateway(is_test_mode)
        result = await AssetService.find_asset(value, page.loop, asset_gateway)
        status = result.get("status")

        if status == "sucesso":
            asset = result["data"]
            app_state.lista_ativos_memoria.append(asset)
            inject_new_item(asset)
            refs["patrimonio"].current.value = ""
            app_state.patrimonio = ""
            refs["patrimonio"].current.focus()
        elif status == "nao_encontrado":
            await shake_control(refs["patrimonio"])
            show_snackbar(
                page, S.MSG_ATIVO_NAO_ENCONTRADO, "error", ft.icons.SEARCH_OFF
            )
        else:
            show_snackbar(
                page, result.get("msg", S.MSG_ERRO), "error", ft.icons.GPP_BAD
            )

        refs["patrimonio"].current.disabled = False
        refs["patrimonio"].current.suffix = None
        page.update()

    async def handle_add_accessory(e: ft.ControlEvent) -> None:
        """Trata Entradas Rápidas de Teclados, Mouses da Row Auxiliar."""
        if getattr(page, "is_adding_quick", False):
            return

        page.is_adding_quick = True
        try:
            name = refs["insumo_nome"].current.value
            if not name or not name.strip():
                await shake_control(refs["insumo_nome"])
                refs["insumo_nome"].current.focus()
                page.update()
                return

            auto_type, auto_cat = "Acessório", "Periférico"
            if "notebook" in name.lower():
                auto_type, auto_cat = "Notebook", "Notebook"
            elif "monitor" in name.lower():
                auto_type, auto_cat = "Monitor", "Monitor"

            new_item = {
                "patrimonio": "S/N",
                "tipo": auto_type,
                "categoria": auto_cat,
                "fabricante": "Genérico",
                "modelo": name.strip(),
                "serial": f"Qtd: {app_state.insumo_qtd}",
                "descricao_visual": name.strip(),
                "qtd": app_state.insumo_qtd,
            }

            app_state.lista_ativos_memoria.append(new_item)
            inject_new_item(new_item)

            refs["insumo_nome"].current.value = ""
            refs["insumo_qtd"].current.value = "1"
            app_state.insumo_qtd = "1"
            refs["insumo_nome"].current.focus()
            page.update()
        finally:
            page.is_adding_quick = False

    def handle_progress_update(step: int, text: str) -> None:
        """Feedback Live do Core Worker Processing Word/PDF File.

        Renderiza Icones Coloridos baseados em Faixas de Percentual.
        """
        icon_name = ft.icons.HOURGLASS_TOP
        color = COLORS.get("primary", "blue")
        if step < 50:
            icon_name, color = ft.icons.DESCRIPTION, "#2B579A"
        elif step < 80:
            icon_name, color = ft.icons.PICTURE_AS_PDF, "#D32F2F"
        elif step >= 100:
            icon_name, color = ft.icons.CHECK_CIRCLE, COLORS.get("green", "green")

        ref_txt.current.value = text
        ref_progress_bar.current.value = step / 100.0
        ref_icon.current.name = icon_name
        ref_icon.current.color = color
        ref_progress_bar.current.color = color
        page.update()

    # --- 3.9. Núcleo Arquitetural de Comunicação (CONTROLLER <-> VIEW) ---
    async def handle_term_generation(e: Optional[ft.ControlEvent]) -> None:
        """Cérebro Principal que Solicita e Passa Payload para Word Doc Compiler.

        Maneja Sub-rotinas Críticas, Bloqueia UI e Retorna Links Dinâmicos de Arquivos ao Sucesso.
        """
        # --- 3.9.1. Prevenção de Spam Clicks ---
        if getattr(page, "is_generating", False) or ref_overlay.current.visible:
            return

        if not app_state.lista_ativos_memoria:
            await shake_control(refs["patrimonio"])
            show_snackbar(page, S.MSG_ADICIONAR_ATIVO, "error", ft.icons.ERROR)
            return

        # --- 3.9.2. Empty Form Check - Verificação e Exigência dos Campos Nome e Setor ---
        required_fields = [refs["nome"], refs["area"]]
        has_error = False
        for req_ref in required_fields:
            if not req_ref.current.value or not req_ref.current.value.strip():
                has_error = True
                asyncio.create_task(shake_control(req_ref))
        if has_error:
            show_snackbar(page, S.MSG_PREENCHER_NOME_SETOR, "error", ft.icons.WARNING)
            return

        page.is_generating = True

        page.data = "processando"
        ref_links.current.visible = False
        ref_close.current.visible = False
        ref_icon.current.name = ft.icons.HOURGLASS_EMPTY
        ref_icon.current.color = COLORS.get("primary", "blue")
        ref_txt.current.value = S.MSG_INICIANDO
        ref_progress_bar.current.value = 0
        ref_progress_bar.current.visible = True

        ref_overlay.current.visible = True
        ref_overlay.current.opacity = 1
        ref_overlay_card.current.scale = 1
        ref_overlay.current.update()
        page.update()

        try:
            await asyncio.sleep(0.2)
            if refs["nome"].current.value:
                refs["nome"].current.value = refs["nome"].current.value.title()

            ui_data = {
                "chamado": refs["chamado"].current.value,
                "nome": refs["nome"].current.value,
                "area": refs["area"].current.value,
                "obs": refs["obs"].current.value,
                "operacao": ref_op.current.value,
            }
            app_state.operacao = ui_data["operacao"]

            # --- 3.9.3. Instanciamento via Factory — View Agnóstica às Implementações Concretas ---
            term_gateway = get_term_gateway(is_test_mode)

            # --- 3.9.4. Request Assíncrona via TermController Handler ---
            result = await TermService.process_term(
                ui_data=ui_data,
                asset_list=app_state.lista_ativos_memoria,
                loop=page.loop,
                gateway=term_gateway,
                progress_callback=handle_progress_update,
            )

            if not result["sucesso"]:
                raise Exception(result["msg"])

            paths = result["paths"]
            ref_progress_bar.current.visible = False

            # --- 3.9.5. Broadcast Inter-componentes Polling Update ---
            if app_state.fn_update_history:
                app_state.fn_update_history()
            if app_state.fn_update_dashboard:
                app_state.fn_update_dashboard()

            async def copy_summary_action(e):
                text = TermService.generate_summary_copy(
                    ui_data, app_state.lista_ativos_memoria
                )
                page.set_clipboard(text)
                show_snackbar(page, S.MSG_RESUMO_COPIADO, "text", ft.icons.COPY_ALL)

            ref_links.current.controls = [
                ft.Container(
                    padding=ft.padding.only(bottom=5),
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Icon(
                                        ft.icons.CHECK_CIRCLE,
                                        size=22,
                                        color=COLORS.get("green", "green"),
                                    ),
                                    ft.Text(
                                        S.MSG_SUCESSO,
                                        weight="bold",
                                        size=16,
                                        color=COLORS.get("text", "black"),
                                    ),
                                ],
                                alignment="center",
                            ),
                            ft.Text(
                                paths["nome_base"],
                                size=14,
                                color=COLORS.get("text_secondary", "grey"),
                                weight="bold",
                                text_align="center",
                            ),
                        ],
                        spacing=5,
                        horizontal_alignment="center",
                    ),
                ),
                create_primary_button(
                    text=S.BTN_COPIAR_RESUMO,
                    icon_name=ft.icons.COPY,
                    on_click=copy_summary_action,
                    full_width=True,
                ),
                ft.Container(
                    padding=10,
                    bgcolor=COLORS.get("grey_bg", "grey"),
                    border_radius=8,
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Icon(
                                        ft.icons.EDIT_DOCUMENT,
                                        color=COLORS.get("blue_word", "blue"),
                                        size=20,
                                    ),
                                    ft.Text("Word", weight="bold", size=12),
                                ]
                            ),
                            ft.Text(
                                paths["docx"],
                                size=11,
                                color=COLORS.get("text_secondary", "grey"),
                                selectable=True,
                            ),
                        ],
                        spacing=2,
                    ),
                ),
                ft.Container(
                    padding=10,
                    bgcolor=COLORS.get("grey_bg", "grey"),
                    border_radius=8,
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Icon(
                                        ft.icons.PICTURE_AS_PDF,
                                        color=COLORS.get("error", "red"),
                                        size=20,
                                    ),
                                    ft.Text("PDF", weight="bold", size=12),
                                ]
                            ),
                            ft.Text(
                                paths["pdf"],
                                size=11,
                                color=COLORS.get("text_secondary", "grey"),
                                selectable=True,
                            ),
                        ],
                        spacing=2,
                    ),
                ),
            ]
            ref_links.current.visible = True

            async def close_overlay_handler(e):
                ref_overlay.current.opacity = 0
                ref_overlay_card.current.scale = 0.9
                ref_overlay.current.update()
                await asyncio.sleep(0.3)
                ref_overlay.current.visible = False
                ref_overlay.current.update()
                page.data = "livre"
                page.is_generating = False
                page.update()

            ref_close.current.content = ft.Row(
                [
                    ft.TextButton(
                        S.BTN_ABRIR_PASTA,
                        icon=ft.icons.FOLDER_OPEN,
                        icon_color=COLORS.get("text_secondary", "#555555"),
                        style=ft.ButtonStyle(
                            color=COLORS.get("text_secondary", "#555555")
                        ),
                        on_click=lambda e: page.run_task(os.startfile, paths["pasta"]),
                    ),
                    ft.ElevatedButton(
                        S.BTN_CONCLUIR,
                        bgcolor=COLORS.get("green", "green"),
                        color=COLORS.get("text_inverse", "white"),
                        elevation=0,
                        on_click=close_overlay_handler,
                    ),
                ],
                alignment=ft.MainAxisAlignment.END,
            )
            ref_close.current.visible = True
            page.update()

            if result["config"].get("abrir_auto", True):
                await asyncio.sleep(0.1)
                try:
                    await page.run_task(os.startfile, paths["pdf"])
                except Exception as ex:
                    print(f"⚠️ Erro ao abrir PDF automaticamente: {ex}")

        except Exception as ex:
            ref_icon.current.name = ft.icons.ERROR_OUTLINE
            ref_icon.current.color = COLORS.get("error", "red")
            ref_txt.current.value = f"Erro na Geração: {ex}"
            ref_progress_bar.current.visible = False

            async def close_error(e):
                ref_overlay.current.visible = False
                ref_overlay.current.update()
                page.is_generating = False

            ref_close.current.content = ft.ElevatedButton(
                S.BTN_FECHAR, on_click=close_error
            )
            ref_close.current.visible = True
            page.update()

    def handle_name_change(e: ft.ControlEvent) -> None:
        """Autofill Inteligente baseado nas Associações Históricas de RAM/Disk de Setor."""
        value = e.control.value
        app_state.nome = value
        if not value or not value.strip():
            refs["area"].current.value = ""
            app_state.area = ""
            refs["area"].current.update()
            return

        if len(value.strip()) >= 3:
            current_area = refs["area"].current.value
            if not current_area or not current_area.strip():
                sector = AssetService.get_collaborator_sector(value)
                if sector:
                    refs["area"].current.value = sector
                    app_state.area = sector
                    refs["area"].current.update()

    def adjust_qty(delta: int) -> None:
        """Matemática Simples de Componente Micro Spinner."""
        try:
            current_val = int(refs["insumo_qtd"].current.value or "1")
        except ValueError:
            current_val = 1

        novo_valor = min(100, max(1, current_val + delta))

        refs["insumo_qtd"].current.value = str(novo_valor)
        app_state.insumo_qtd = refs["insumo_qtd"].current.value
        refs["insumo_qtd"].current.update()

    # --- 3.10. Micros Componentes View Factory ---

    def _build_asset_card(item: Dict[str, Any]) -> ft.Container:
        """Encapsula Item Dic em Card com Delete Atrelado."""
        card_container = []

        def on_del_click(e):
            if card_container:
                remove_specific_item(item, card_container[0])

        card = create_smart_asset_card(item, on_delete=on_del_click)
        card_container.append(card)
        return card

    def _create_empty_state() -> ft.Container:
        """Placeholder UX Graceful."""
        return ft.Container(
            key="empty_state",
            alignment=ft.alignment.center,
            height=MIN_LIST_HEIGHT,
            opacity=0.8,
            content=ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(
                        ft.icons.DEVICES, size=40, color=COLORS.get("border", "grey")
                    ),
                    ft.Text(
                        S.MSG_NENHUM_ITEM,
                        size=12,
                        color=COLORS.get("text_secondary", "grey"),
                    ),
                ],
            ),
        )

    # --- 3.11. Popups Dialogs System UI ---
    dlg_reset = ft.AlertDialog(
        modal=True,
        title=ft.Text(S.DLG_TITLE_LIMPAR, selectable=True),
        actions=[
            ft.TextButton(
                S.BTN_CANCELAR,
                on_click=lambda e: setattr(dlg_reset, "open", False) or page.update(),
            ),
            ft.ElevatedButton(
                S.BTN_SIM,
                bgcolor=COLORS.get("error", "red"),
                color=COLORS.get("text_inverse", "white"),
                elevation=0,
                on_click=handle_reset_form,
            ),
        ],
    )

    dlg_new_asset = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.icons.ADD_TO_PHOTOS, color=COLORS.get("primary", "blue")),
                ft.Text(
                    S.DLG_TITLE_ADD_MANUAL,
                    weight="bold",
                    size=18,
                    color=COLORS.get("text", "black"),
                ),
            ]
        ),
        content=ft.Container(
            width=450,
            height=450,
            padding=10,
            content=ft.Column(
                [
                    ft.Text(
                        S.DLG_BODY_ADD_MANUAL,
                        size=12,
                        color=COLORS.get("text_secondary", "grey"),
                    ),
                    create_form_input(
                        "Patrimônio", ft.icons.TAG, refs_new_asset["patrimonio"], ""
                    ),
                    create_filter_dropdown(
                        label="Tipo de Ativo",
                        options=[
                            ("Notebook", "Notebook"),
                            ("Desktop", "Desktop"),
                            ("Monitor", "Monitor"),
                            ("Smartphone", "Smartphone"),
                            ("Periférico", "Periférico"),
                            ("Impressora", "Impressora"),
                        ],
                        value="Notebook",
                        width=430,
                        ref=refs_new_asset["tipo"],
                    ),
                    create_form_input(
                        "Fabricante",
                        ft.icons.PRECISION_MANUFACTURING,
                        refs_new_asset["fabricante"],
                        "",
                    ),
                    create_form_input(
                        "Modelo", ft.icons.DEVICES_OTHER, refs_new_asset["modelo"], ""
                    ),
                    create_form_input(
                        "Número de Série (SN)",
                        ft.icons.QR_CODE,
                        refs_new_asset["serial"],
                        "",
                    ),
                ],
                spacing=15,
                scroll=ft.ScrollMode.ADAPTIVE,
            ),
        ),
        actions=[
            ft.Row(
                controls=[
                    ft.TextButton(
                        S.BTN_CANCELAR,
                        on_click=lambda e: (
                            setattr(dlg_new_asset, "open", False) or page.update()
                        ),
                    ),
                    create_primary_button(
                        "Adicionar Ativo", on_click=handle_manual_asset_confirm
                    ),
                ],
                alignment=ft.MainAxisAlignment.END,
            )
        ],
        actions_alignment=ft.MainAxisAlignment.END,
        shape=ft.RoundedRectangleBorder(radius=12),
        bgcolor=COLORS.get("card_bg", "white"),
    )

    # --- 3.12. Loading Modal Overlay ---
    overlay_panel = ft.Container(
        ref=ref_overlay,
        visible=False,
        expand=True,
        bgcolor=ft.colors.with_opacity(0.8, "black"),
        alignment=ft.alignment.center,
        opacity=0,
        animate_opacity=300,
        content=ft.Container(
            ref=ref_overlay_card,
            bgcolor=COLORS.get("card_bg", "white"),
            padding=30,
            border_radius=20,
            shadow=ft.BoxShadow(blur_radius=20, color=COLORS.get("text", "black")),
            width=350,
            scale=ft.transform.Scale(0.9),
            animate_scale=ft.animation.Animation(400, "easeOutBack"),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
                tight=True,
                controls=[
                    ft.Icon(
                        ref=ref_icon,
                        name=ft.icons.HOURGLASS_EMPTY,
                        size=60,
                        color=COLORS.get("primary", "blue"),
                    ),
                    ft.Text(
                        ref=ref_txt,
                        value=S.MSG_INICIANDO,
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        color=COLORS.get("text", "black"),
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(
                        padding=ft.padding.symmetric(vertical=10),
                        content=ft.ProgressBar(
                            ref=ref_progress_bar,
                            width=280,
                            color=COLORS.get("primary", "blue"),
                            bgcolor=COLORS.get("grey_bg", "grey"),
                            value=0,
                        ),
                    ),
                    ft.Column(ref=ref_links, visible=False, spacing=10),
                    ft.Container(ref=ref_close, visible=False),
                ],
            ),
        ),
    )

    # --- 3.13. Montagem Final da Camada Gerador ---

    input_patrimonio = create_form_input(
        S.LABEL_BUSCA_PATRIMONIO,
        ft.icons.COMPUTER,
        refs["patrimonio"],
        app_state.patrimonio,
        lambda e: setattr(app_state, "patrimonio", e.control.value),
        handle_asset_search,
    )
    input_patrimonio.border_color = "transparent"
    input_patrimonio.focused_border_color = focus_color
    input_patrimonio.expand = True

    input_insumo = create_form_input(
        S.LABEL_INSUMO,
        ft.icons.KEYBOARD,
        refs["insumo_nome"],
        "",
        None,
        handle_add_accessory,
    )
    input_insumo.border_color = "transparent"
    input_insumo.focused_border_color = focus_color
    input_insumo.expand = True

    obs_field = create_form_input(
        S.LABEL_OBS,
        ft.icons.NOTE_ALT_OUTLINED,
        refs["obs"],
        app_state.obs,
        lambda e: setattr(app_state, "obs", e.control.value),
        multiline=True,
    )
    obs_field.min_lines = 1
    obs_field.max_lines = 8

    inputs_tab_content = ft.Container(
        expand=True,
        content=ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=15,
            controls=[
                ft.Text(
                    S.TITLE_INFO_CHAMADO,
                    weight="bold",
                    color=COLORS.get("text", "black"),
                    size=18,
                ),
                create_standard_card(
                    padding=15,
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            create_form_input(
                                S.LABEL_CHAMADO,
                                ft.icons.TAG,
                                refs["chamado"],
                                app_state.chamado,
                                lambda e: setattr(
                                    app_state, "chamado", e.control.value
                                ),
                                lambda e: refs["nome"].current.focus(),
                            ),
                            create_form_input(
                                S.LABEL_COLABORADOR,
                                ft.icons.PERSON_OUTLINE,
                                refs["nome"],
                                app_state.nome,
                                handle_name_change,
                                lambda e: refs["area"].current.focus(),
                            ),
                            create_form_input(
                                S.LABEL_AREA,
                                ft.icons.BUSINESS_OUTLINED,
                                refs["area"],
                                app_state.area,
                                lambda e: setattr(app_state, "area", e.control.value),
                                lambda e: refs["patrimonio"].current.focus(),
                            ),
                            ft.Dropdown(
                                ref=ref_op,
                                value=app_state.operacao,
                                options=[
                                    ft.dropdown.Option("Entrega"),
                                    ft.dropdown.Option("Devolução"),
                                    ft.dropdown.Option("Empréstimo"),
                                ],
                                on_change=lambda e: setattr(
                                    app_state, "operacao", e.control.value
                                ),
                                label=S.LABEL_TIPO_OP,
                                label_style=ft.TextStyle(
                                    size=12, color=COLORS.get("text_secondary", "grey")
                                ),
                                border_radius=8,
                                bgcolor=COLORS.get("input_bg", "white"),
                                border_color=COLORS.get("border", "grey"),
                                focused_border_color=focus_color,
                                text_size=14,
                                content_padding=15,
                            ),
                        ],
                    ),
                ),
                ft.Divider(height=10, color="transparent"),
                ft.Text(
                    S.TITLE_EQUIPAMENTOS,
                    weight="bold",
                    color=COLORS.get("text", "black"),
                    size=18,
                ),
                create_standard_card(
                    padding=5,
                    content=ft.Row(
                        [
                            input_patrimonio,
                            ft.IconButton(
                                icon=ft.icons.ADD_CIRCLE,
                                icon_color=COLORS.get("green", "green"),
                                icon_size=32,
                                tooltip=S.DLG_TITLE_ADD_MANUAL,
                                on_click=open_manual_dialog,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        spacing=0,
                    ),
                ),
                create_standard_card(
                    padding=5,
                    content=ft.Row(
                        [
                            input_insumo,
                            ft.Container(
                                width=1,
                                height=24,
                                bgcolor=COLORS.get("grey_bg", "grey"),
                            ),
                            ft.Row(
                                [
                                    ft.IconButton(
                                        icon=ft.icons.REMOVE,
                                        icon_size=16,
                                        icon_color=COLORS.get("text_secondary", "grey"),
                                        on_click=lambda e: adjust_qty(-1),
                                    ),
                                    ft.TextField(
                                        ref=refs["insumo_qtd"],
                                        value="1",
                                        text_align="center",
                                        width=35,
                                        text_size=13,
                                        border_color="transparent",
                                        bgcolor=COLORS.get("input_bg", "white"),
                                        focused_border_color=focus_color,
                                        keyboard_type=ft.KeyboardType.NUMBER,
                                        content_padding=10,
                                        on_change=lambda e: setattr(
                                            app_state, "insumo_qtd", e.control.value
                                        ),
                                        on_submit=handle_add_accessory,
                                    ),
                                    ft.IconButton(
                                        icon=ft.icons.ADD,
                                        icon_size=16,
                                        icon_color=focus_color,
                                        on_click=lambda e: adjust_qty(1),
                                    ),
                                ],
                                spacing=0,
                            ),
                            ft.Container(
                                bgcolor=COLORS.get("green", "green"),
                                border_radius=8,
                                width=40,
                                height=40,
                                content=ft.IconButton(
                                    icon=ft.icons.ARROW_FORWARD,
                                    icon_size=18,
                                    icon_color=COLORS.get("text_inverse", "white"),
                                    on_click=handle_add_accessory,
                                ),
                            ),
                        ],
                        alignment="center",
                        spacing=2,
                    ),
                ),
                ft.Container(
                    content=list_container,
                    border_radius=8,
                    bgcolor=COLORS.get("grey_light", "white"),
                    padding=10,
                    border=ft.border.all(1, color=COLORS.get("border", "grey")),
                ),
                ft.Divider(height=10, color="transparent"),
                create_standard_card(
                    padding=0,
                    content=obs_field,
                ),
                ft.Text(
                    S.LABEL_TOQUE_ADD,
                    size=11,
                    color=COLORS.get("text_secondary", "grey"),
                ),
                ft.Row(
                    wrap=True,
                    spacing=10,
                    controls=[
                        ft.Container(
                            content=ft.Text(
                                t,
                                color=COLORS.get("primary", "blue"),
                                weight="bold",
                                size=13,
                            ),
                            bgcolor=COLORS.get("primary_light", "lightblue"),
                            padding=10,
                            border_radius=8,
                            on_click=lambda e, txt=t: (
                                setattr(
                                    refs["obs"].current,
                                    "value",
                                    (
                                        (refs["obs"].current.value or "") + f"\n{txt}"
                                    ).lstrip(),
                                ),
                                refs["obs"].current.update(),
                                setattr(app_state, "obs", refs["obs"].current.value),
                            ),
                        )
                        for t in S.SUGESTOES_OBS
                    ],
                ),
                ft.Container(height=20),
                create_primary_button(
                    S.BTN_GERAR,
                    icon_name=ft.icons.CHECK_CIRCLE_OUTLINE,
                    on_click=lambda e: asyncio.run_coroutine_threadsafe(
                        handle_term_generation(e), page.loop
                    ),
                    full_width=True,
                ),
                ft.Container(height=30),
            ],
        ),
    )

    def _fechar_dlg_reset(e):
        dlg_reset.open = False
        page.update()

    def _executar_reset(e):
        for k in [
            "patrimonio",
            "nome",
            "chamado",
            "area",
            "obs",
            "insumo_nome",
            "insumo_qtd",
        ]:
            if refs.get(k) and refs[k].current:
                refs[k].current.value = ""
                refs[k].current.update()
        if ref_op.current:
            ref_op.current.value = "Entrega"
            ref_op.current.update()
        app_state.lista_ativos_memoria.clear()
        app_state.reset_state()
        asyncio.run_coroutine_threadsafe(full_list_refresh(), page.loop)

        dlg_reset.open = False
        page.update()

    dlg_reset = ft.AlertDialog(
        title=ft.Row(
            [
                ft.Icon(ft.icons.WARNING_AMBER, color=COLORS.get("orange", "orange")),
                ft.Text("Apagar Tudo?"),
            ]
        ),
        content=ft.Text("Tem certeza que deseja apagar todos os dados inseridos?"),
        shape=ft.RoundedRectangleBorder(radius=12),
        actions=[
            ft.TextButton("Não", on_click=_fechar_dlg_reset),
            ft.ElevatedButton(
                "Sim",
                bgcolor=COLORS.get("error", "red"),
                color=COLORS.get("text_inverse", "white"),
                elevation=0,
                on_click=_executar_reset,
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def prompt_clear_all_action():
        """Exibe o diálogo de exclusão em Lote dos Estados da UI (Ctrl+Del Action)"""
        page.dialog = dlg_reset
        dlg_reset.open = True
        page.update()

    # --- 3.14. Bindings System App State ---
    asyncio.run_coroutine_threadsafe(full_list_refresh(), page.loop)
    app_state.fn_generate_term = lambda: asyncio.run_coroutine_threadsafe(
        handle_term_generation(None), page.loop
    )
    app_state.fn_clear_form = prompt_clear_all_action

    header_bg = get_header_color(is_test_mode)

    view_header = ft.Container(
        padding=ft.padding.all(35),
        bgcolor=header_bg,
        border_radius=15,
        shadow=ft.BoxShadow(
            blur_radius=15,
            color=ft.colors.with_opacity(0.15, "black"),
            offset=ft.Offset(0, 5),
        ),
        content=ft.Row(
            [
                ft.Container(
                    padding=15,
                    bgcolor=ft.colors.with_opacity(0.15, "white"),
                    border_radius=12,
                    content=ft.Icon(
                        ft.icons.EDIT_DOCUMENT,
                        color=COLORS.get("text_inverse", "white"),
                        size=45,
                    ),
                ),
                ft.Column(
                    [
                        ft.Text(
                            S.TITLE_SIMULATION_MODE
                            if is_test_mode
                            else "Gerenciador de Termos",
                            size=32,
                            weight="bold",
                            color=COLORS.get("text_inverse", "white"),
                        ),
                        ft.Text(
                            "Preencha os dados corporativos abaixo para processar um novo documento.",
                            size=16,
                            color=ft.colors.with_opacity(0.8, "white"),
                        ),
                    ],
                    spacing=5,
                ),
            ],
            spacing=25,
        ),
    )

    view_gerador = ft.Column(
        [
            view_header,
            ft.Divider(height=20, color="transparent"),
            inputs_tab_content,
        ],
        expand=True,
    )

    # --- 3.15. Cérebro da Navigation Rail ---

    view_historico = build_history_tab(page, app_state)
    view_dashboard = build_dashboard_tab(page, app_state)
    views = [view_gerador, view_historico, view_dashboard]

    active_icon_color = (
        COLORS.get("orange", "orange")
        if is_test_mode
        else COLORS.get("primary", "blue")
    )
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

    def _update_nav_ui():
        if not nav_column_ref.current:
            return
        nav_column_ref.current.controls = [
            _build_nav_icon(
                0, ft.icons.EDIT_DOCUMENT, ft.icons.EDIT_DOCUMENT, "Gerador"
            ),
            _build_nav_icon(
                1, ft.icons.HISTORY, ft.icons.HISTORY_OUTLINED, "Histórico"
            ),
            _build_nav_icon(
                2, ft.icons.DASHBOARD, ft.icons.DASHBOARD_OUTLINED, "Dashboard"
            ),
        ]
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
        controls=[
            _build_nav_icon(
                0, ft.icons.EDIT_DOCUMENT, ft.icons.EDIT_DOCUMENT, "Gerador"
            ),
            _build_nav_icon(
                1, ft.icons.HISTORY, ft.icons.HISTORY_OUTLINED, "Histórico"
            ),
            _build_nav_icon(
                2, ft.icons.DASHBOARD, ft.icons.DASHBOARD_OUTLINED, "Dashboard"
            ),
        ],
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
                        ft.icons.SETTINGS, color=inactive_icon_color, size=28
                    ),
                    width=55,
                    height=55,
                    alignment=ft.alignment.center,
                    border_radius=50,
                    on_click=lambda _: page.go("/config"),
                    tooltip=S.TITLE_CONFIG,
                    ink=True,
                ),
            ),
        ],
    )

    # --- 3.16. Injeção do Container Raiz Responsivo Side-By-Side Applet ---
    main_dashboard = ft.Container(
        expand=True,
        bgcolor=COLORS.get("background", "white"),
        content=ft.Row(
            [
                left_sidebar,
                ft.Container(
                    ref=ref_right_panel,
                    content=view_gerador,
                    expand=True,
                    padding=ft.padding.all(60),
                ),
            ],
            expand=True,
        ),
    )

    # --- 3.17. Callbacks de UI pro State Container ---
    app_state.fn_generate_term = lambda: asyncio.run_coroutine_threadsafe(
        handle_term_generation(None), page.loop
    )
    app_state.fn_clear_form = prompt_clear_all_action

    # --- 3.18. Root Render Command UI Loop ---
    page.add(
        ft.Stack(
            [main_dashboard, overlay_panel],
            expand=True,
        )
    )
