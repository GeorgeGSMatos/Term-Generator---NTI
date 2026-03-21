"""
Módulo de Visualização de Onboarding (View Layer).

Gerencia o fluxo inicial de boas-vindas e configuração obrigatória
de diretórios para novos usuários da aplicação.
"""

# ==============================================================================
# 1. IMPORTS E DEPENDÊNCIAS
# ==============================================================================
import flet as ft

import core.strings as S
from core.settings import COLORS, save_setting

# --- 1.1. Fábrica UI Reutilizável ---
from views.ui import (
    create_directory_picker_card,
    create_primary_button,
    create_status_badge,
    handle_filepicker_result,
    show_snackbar,
)

# ==============================================================================
# 2. VIEW DE ONBOARDING
# ==============================================================================


def build_onboarding_view(page: ft.Page) -> None:
    """Renderiza a estrutura modal translúcida da tela de Welcome/Setup Inicial.

    Obriga o mapeamento em rede para habilitar navegação na Aplicação. Aciona picker Win32.

    Args:
        page (ft.Page): O DOM Master do Flet a ser renderizado.
    """

    # --- 2.1. Âncoras do Event Loop ---
    ref_path = ft.Ref[ft.TextField]()
    ref_pdf_path = ft.Ref[ft.TextField]()
    dlg_ref = ft.Ref[ft.AlertDialog]()

    # --- 2.2. Injeção Acoplada dos File Dialog Pickers Microsoft ---
    pk_word = ft.FilePicker(on_result=lambda e: handle_filepicker_result(e, ref_path))
    pk_pdf = ft.FilePicker(
        on_result=lambda e: handle_filepicker_result(e, ref_pdf_path)
    )
    page.overlay.extend([pk_word, pk_pdf])

    def save_initial_setup(e: ft.ControlEvent) -> None:
        """Processa Clicks: Escuta Botão Inicial, Valida Formulário e Dispara Configuração."""
        path_val = ref_path.current.value
        pdf_path_val = ref_pdf_path.current.value

        if not path_val:
            show_snackbar(page, S.MSG_ERRO_REDE_OBRIGATORIA, "error", ft.icons.WARNING)
            return

        # --- 2.3. Montagem do Dicionário de Configurações ---
        config_to_save = {"pasta_raiz_rede": path_val}

        if pdf_path_val:
            config_to_save["pasta_pdf"] = pdf_path_val

        save_setting(config_to_save)

        # --- 2.4. Liberação do Bloqueio Modal Dialog e Destruição Visual ---
        if dlg_ref.current:
            dlg_ref.current.open = False
        page.update()

        # --- 2.5. Pipeline de Redirecionamento da Árvore de Rotas ---
        page.go("/")
        page.go("/")
        show_snackbar(
            page, "Sistema configurado com sucesso!", "green", ft.icons.CHECK_CIRCLE
        )

    # --- 2.6. DOM Virtual Flet: Enclave de Conteúdo Principal ---

    content_ui = ft.Container(
        width=650,
        bgcolor=COLORS.get("card_bg", "white"),
        border_radius=15,
        padding=0,
        shadow=ft.BoxShadow(blur_radius=20, color=ft.colors.with_opacity(0.2, "black")),
        content=ft.Column(
            tight=True,
            spacing=0,
            controls=[
                # --- 2.6.1. Bloco 1: Hero Header Colorido do Onboarding Box ---
                ft.Container(
                    bgcolor=COLORS.get("secondary", "blue"),
                    padding=30,
                    border_radius=ft.border_radius.only(top_left=15, top_right=15),
                    content=ft.Row(
                        alignment="center",
                        spacing=15,
                        controls=[
                            ft.Container(
                                padding=10,
                                bgcolor=ft.colors.with_opacity(0.15, "white"),
                                border_radius=10,
                                content=ft.Icon(
                                    ft.icons.DNS,
                                    color=COLORS.get("text_inverse", "white"),
                                    size=35,
                                ),
                            ),
                            ft.Column(
                                spacing=5,
                                expand=True,
                                controls=[
                                    ft.Text(
                                        "Bem-vindo ao Gerenciador",
                                        color=COLORS.get("text_inverse", "white"),
                                        weight="bold",
                                        size=20,
                                    ),
                                    ft.Text(
                                        "Configuração inicial necessária",
                                        color=ft.colors.with_opacity(0.8, "white"),
                                        size=13,
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                # --- 2.6.2. Formulário e Ações ---
                ft.Container(
                    padding=35,
                    content=ft.Column(
                        spacing=20,
                        controls=[
                            # --- 2.6.2.1. Indicador Emblema de Autenticação Segura Ignorada ---
                            create_status_badge(
                                text="Autenticação Aceita",
                                icon_name=ft.icons.VERIFIED_USER,
                                color=COLORS.get("green", "green"),
                                bg_color=COLORS.get("green_bg", "lightgreen"),
                            ),
                            ft.Divider(height=10, color="transparent"),
                            ft.Text(
                                "Para o sistema funcionar corretamente, mapeie os diretórios base de armazenamento.",
                                size=13,
                                color=COLORS.get("text_secondary", "grey"),
                                text_align=ft.TextAlign.CENTER,
                            ),
                            # --- 2.6.2.2. Picker Customizado Injetável Win32 para Word ---
                            create_directory_picker_card(
                                title="Pasta Raíz (Onde o arquivo .docx será salvo)",
                                subtitle_path="",
                                icon_name=ft.icons.DNS,
                                ref_field=ref_path,
                                on_click=lambda _: pk_word.get_directory_path(),
                            ),
                            # --- 2.6.2.3. Picker Customizado Injetável Win32 para PDF ---
                            create_directory_picker_card(
                                title="Pasta Local (Onde o arquivo .pdf será salvo)",
                                subtitle_path="",
                                icon_name=ft.icons.PICTURE_AS_PDF,
                                ref_field=ref_pdf_path,
                                on_click=lambda _: pk_pdf.get_directory_path(),
                            ),
                            ft.Divider(height=20, color="transparent"),
                            # --- 2.6.2.4. CTA de Prosseguir Submissão Inicial ---
                            create_primary_button(
                                text="Salvar e Iniciar Sistema",
                                icon_name=ft.icons.CHECK_CIRCLE_OUTLINE,
                                on_click=save_initial_setup,
                                full_width=True,
                            ),
                        ],
                    ),
                ),
            ],
        ),
    )

    # --- 2.7. Popup Overlay Flet: Invólucro da Animação do Dialog ---

    dlg = ft.AlertDialog(
        ref=dlg_ref,
        modal=True,
        content=content_ui,
        content_padding=0,
        bgcolor="transparent",
        shape=ft.RoundedRectangleBorder(radius=15),
    )

    page.dialog = dlg
    dlg.open = True
    page.update()
