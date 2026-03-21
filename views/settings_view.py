"""
Módulo de Visualização de Configurações (View Layer).

Interface para gerenciamento de diretórios de rede, preferências
de simulação e parâmetros globais do sistema.
"""

# ==============================================================================
# 1. IMPORTS E DEPENDÊNCIAS
# ==============================================================================
from typing import Any, Dict

import flet as ft

import core.strings as S

# --- 1.1. Infraestrutura Core e Dicionários ---
from core.settings import (
    COLORS,
    apply_theme,
    get_header_color,
    load_setting,
    save_setting,
)

# --- 1.2. Componentes Sintéticos da View Layer ---
from views.ui import (
    create_directory_picker_card,
    create_primary_button,
    create_standard_card,
    handle_filepicker_result,
    show_snackbar,
)

# ==============================================================================
# 2. ESTADO E CONSTRUÇÃO DA TELA
# ==============================================================================


def build_config_view(page: ft.Page) -> None:
    """Invoca o motor do Flet na Rota de Configuração limpando o App State limítrofe.

    Permite substituição in-flight segura das chaves do arquivo setting.json.

    Args:
        page (ft.Page): Objeto raiz mutável do Container Flet DOM.
    """
    page.clean()
    page.bgcolor = COLORS.get("background", "#F4F6F9")

    # --- 2.1. Recuperação do Objeto Singleton Atualizado ---
    config: Dict[str, Any] = load_setting()
    is_test_mode = config.get("modo_teste", False)

    # --- 2.2. Âncoras Dinâmicas para TextFields ---
    val_path_pdf = ft.Ref[ft.TextField]()
    val_path_rede = ft.Ref[ft.TextField]()

    # --- 2.3. Âncoras Dinâmicas de Booleans Toggles ---
    ref_sw_open = ft.Ref[ft.Switch]()
    ref_sw_test = ft.Ref[ft.Switch]()

    # --- 2.4. Closures e Lógica de Dados ---
    def handle_save_all(e: ft.ControlEvent) -> None:
        """Serializador de Dicionário final em Disco que atualiza o UI Color Mode.

        Bloqueia Submissões sem Path de Rede (Essencial para não trancar a IA na Bronze Layer).
        """
        if not val_path_rede.current.value:
            show_snackbar(page, S.MSG_ERRO_REDE_OBRIGATORIA, "error", ft.icons.WARNING)
            return

        # --- 2.5. Objeto de Payload ---
        new_config: Dict[str, Any] = {
            "pasta_pdf": val_path_pdf.current.value,
            "pasta_raiz_rede": val_path_rede.current.value,
            "abrir_auto": ref_sw_open.current.value,
            "modo_teste": ref_sw_test.current.value,
            "gemini_api_key": config.get("gemini_api_key", ""),
        }

        save_setting(new_config)

        # --- 2.6. Trata as Variações de Header Quente e Frio no Modo Teste ---
        if new_config["modo_teste"] != is_test_mode:
            apply_theme(new_config["modo_teste"])
            page.go("/config")
            show_snackbar(
                page,
                "Configurações salvas. Cores do sistema atualizadas.",
                "green",
                ft.icons.PALETTE,
            )
        else:
            show_snackbar(page, S.MSG_CONFIG_SALVA, "green", ft.icons.CHECK_CIRCLE)

    # --- 2.7. Injeta File Dialogs do Windows Core Overlay Async no App Principal ---
    pk_rede = ft.FilePicker(
        on_result=lambda e: handle_filepicker_result(e, val_path_rede)
    )
    pk_pdf = ft.FilePicker(
        on_result=lambda e: handle_filepicker_result(e, val_path_pdf)
    )
    page.overlay.extend([pk_rede, pk_pdf])

    # --- 2.7.1. Layout do Cabeçalho Limpo ---
    simple_header = ft.Row(
        spacing=15,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.IconButton(
                icon=ft.icons.ARROW_BACK,
                icon_color=COLORS.get("text", "black"),
                icon_size=28,
                tooltip="Voltar ao Sistema",
                on_click=lambda _: page.go("/"),
            ),
            ft.Column(
                spacing=2,
                controls=[
                    ft.Text(
                        "Configurações do Sistema",
                        size=26,
                        weight="bold",
                        color=COLORS.get("text", "black"),
                    ),
                    ft.Text(
                        "Gerencie os diretórios de rede e as preferências.",
                        size=14,
                        color=COLORS.get("text_secondary", "grey"),
                    ),
                ],
            ),
        ],
    )

    # --- 2.7.2. Scrollable Body de Inputs ---
    settings_body = ft.Container(
        padding=ft.padding.all(60),
        content=ft.Column(
            scroll=ft.ScrollMode.ALWAYS,
            expand=True,
            controls=[
                simple_header,
                ft.Divider(height=40, color="transparent"),
                # --- 2.7.2.1. Paths I/O Rede e Backup ---
                ft.Text(
                    "Mapeamento de Diretórios",
                    weight="bold",
                    size=18,
                    color=COLORS.get("text", "black"),
                ),
                ft.Text(
                    "Selecione onde os Termos (PDF/Word) serão salvos.",
                    size=13,
                    color=COLORS.get("text_secondary", "grey"),
                ),
                ft.Container(height=10),
                create_directory_picker_card(
                    title="Pasta Raíz (Word)",
                    subtitle_path=config.get("pasta_raiz_rede", ""),
                    icon_name=ft.icons.DNS,
                    ref_field=val_path_rede,
                    on_click=lambda _: pk_rede.get_directory_path(),
                ),
                ft.Container(height=5),
                create_directory_picker_card(
                    title="Pasta Local (PDF)",
                    subtitle_path=config.get("pasta_pdf", ""),
                    icon_name=ft.icons.PICTURE_AS_PDF,
                    ref_field=val_path_pdf,
                    on_click=lambda _: pk_pdf.get_directory_path(),
                ),
                ft.Divider(height=40, color=COLORS.get("border", "lightgrey")),
                # --- 2.7.2.2. Flags Booleanas Automatizadas UX ---
                ft.Text(
                    "Preferências",
                    weight="bold",
                    size=18,
                    color=COLORS.get("text", "black"),
                ),
                ft.Text(
                    "Ajuste o comportamento do sistema.",
                    size=13,
                    color=COLORS.get("text_secondary", "grey"),
                ),
                ft.Container(height=10),
                create_standard_card(
                    padding=25,
                    content=ft.Column(
                        spacing=20,
                        controls=[
                            ft.Switch(
                                ref=ref_sw_open,
                                label="Abrir PDF Automaticamente",
                                value=config.get("abrir_auto", True),
                                active_color=COLORS.get("primary", "blue"),
                                label_style=ft.TextStyle(
                                    size=14,
                                    weight="bold",
                                    color=COLORS.get("text", "black"),
                                ),
                            ),
                            ft.Divider(
                                height=1, color=COLORS.get("border", "lightgrey")
                            ),
                            ft.Switch(
                                ref=ref_sw_test,
                                label="Modo Simulação",
                                value=config.get("modo_teste", False),
                                active_color=COLORS.get("orange", "orange"),
                                label_style=ft.TextStyle(
                                    size=14,
                                    weight="bold",
                                    color=COLORS.get("text", "black"),
                                ),
                            ),
                        ],
                    ),
                ),
                ft.Divider(height=40, color=COLORS.get("border", "lightgrey")),
                # --- 2.7.2.3. Bypass Zone Command Center Restrito ---
                ft.Text(
                    "Administração Avançada",
                    weight="bold",
                    size=18,
                    color=COLORS.get("text", "black"),
                ),
                ft.Text(
                    "Acesso direto à Central de Controle, Banco de Dados e Motor de IA.",
                    size=13,
                    color=COLORS.get("text_secondary", "grey"),
                ),
                ft.Container(height=10),
                create_standard_card(
                    padding=20,
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                spacing=15,
                                controls=[
                                    ft.Container(
                                        padding=12,
                                        border_radius=50,
                                        bgcolor=COLORS.get("grey_bg", "#F5F5F5"),
                                        content=ft.Icon(
                                            ft.icons.ADMIN_PANEL_SETTINGS,
                                            color=COLORS.get("text_secondary", "grey"),
                                            size=28,
                                        ),
                                    ),
                                    ft.Column(
                                        spacing=2,
                                        controls=[
                                            ft.Text(
                                                "Central de Controle",
                                                weight="bold",
                                                size=16,
                                                color=COLORS.get("text", "black"),
                                            ),
                                            ft.Text(
                                                "Área restrita e protegida por senha de segurança.",
                                                size=12,
                                                color=COLORS.get(
                                                    "text_secondary", "grey"
                                                ),
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            ft.ElevatedButton(
                                "Acessar",
                                icon=ft.icons.SHIELD,
                                color=COLORS.get("text_inverse", "white"),
                                bgcolor=get_header_color(is_test_mode),
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=8)
                                ),
                                elevation=0,
                                on_click=lambda _: page.go("/mdm"),
                            ),
                        ],
                    ),
                ),
                ft.Container(height=30),
                # --- 2.7.2.4. Ação Final: Confirmação Salvar ---
                create_primary_button(
                    text=S.BTN_SALVAR_CONFIG,
                    icon_name=ft.icons.SAVE_AS,
                    on_click=handle_save_all,
                    full_width=True,
                ),
                ft.Container(height=50),
            ],
        ),
    )

    page.add(
        ft.Column(
            [settings_body],
            expand=True,
            scroll=ft.ScrollMode.ALWAYS,
        )
    )
