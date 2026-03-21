"""
Módulo de Entrada Principal (Entry Point).

Responsável pela inicialização do framework Flet, configuração da janela,
gerenciamento de rotas e orquestração do estado global da aplicação.
"""

# ==============================================================================
# 1. IMPORTS E DEPENDÊNCIAS
# ==============================================================================
import asyncio
import threading
import traceback
from typing import Any, Dict

import flet as ft

from controllers.backup_service import perform_auto_backup
from core.settings import (
    COLORS,
    WINDOW_HEIGHT,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
    WINDOW_WIDTH,
    apply_theme,
    load_setting,
)
from data.gold.database import init_db
from data.state import AppState
from views.home_view import build_home_view
from views.mdm_view import build_mdm_view
from views.onboarding_view import build_onboarding_view
from views.settings_view import build_config_view


# ==============================================================================
# 2. ORQUESTRAÇÃO PRINCIPAL
# ==============================================================================
def main(page: ft.Page) -> None:
    """Orquestrador principal da aplicação.

    Gerencia o ciclo de vida da janela primária, inicialização de sistema,
    roteamento dinâmico e limites de falha.

    Args:
        page (ft.Page): A página gerenciada pelo Flet.
    """
    # --- 2.1. Configurações de Janela ---
    page.title = "GDT"
    page.theme_mode = ft.ThemeMode.LIGHT

    page.fonts = {
        "Inter": "https://github.com/rsms/inter/raw/master/docs/font-files/Inter-Regular.woff2",
        "Inter-Medium": "https://github.com/rsms/inter/raw/master/docs/font-files/Inter-Medium.woff2",
        "Inter-Bold": "https://github.com/rsms/inter/raw/master/docs/font-files/Inter-Bold.woff2",
        "RobotoMono": "https://github.com/google/fonts/raw/main/ofl/robotomono/RobotoMono-Regular.ttf",
    }

    page.theme = ft.Theme(
        font_family="Inter",
        page_transitions=ft.PageTransitionsTheme(
            windows=ft.PageTransitionTheme.FADE_UPWARDS,
            macos=ft.PageTransitionTheme.FADE_UPWARDS,
            linux=ft.PageTransitionTheme.FADE_UPWARDS,
        ),
    )
    page.padding = 0
    page.bgcolor = COLORS.get("background", "#F5F5F7")

    page.window_title_bar_hidden = False
    page.window_icon = "assets/app_icone.ico"
    page.window_width = WINDOW_WIDTH
    page.window_height = WINDOW_HEIGHT
    page.window_min_width = WINDOW_MIN_WIDTH
    page.window_min_height = WINDOW_MIN_HEIGHT
    page.window_center()

    # --- 2.2. Inicialização de Serviços e Banco de Dados ---
    try:
        print("🚀 Início do Sistema: Validando Banco de Dados...")
        init_db()

        def _background_backup() -> None:
            """Executa rotina silenciosa de backup."""
            try:
                if perform_auto_backup():
                    print("   ✅ Backup automático realizado com sucesso.")
                else:
                    print("   ⚠️ Backup ignorado (configuração incompleta).")
            except Exception as backup_err:
                print(f"   ❌ Erro silencioso no backup automático: {backup_err}")

        threading.Thread(target=_background_backup, daemon=True).start()

    except Exception as e:
        print(f"⚠️ Aviso Crítico de Inicialização: {e}")

    # --- 2.3. Inicialização de Estado e Opções ---
    try:
        config: Dict[str, Any] = load_setting()
        app_state: AppState = AppState()

        apply_theme(config.get("modo_teste", False))

    except Exception as e:
        page.add(
            ft.Text(
                f"Erro Fatal ao iniciar Estado Global: {e}",
                color=COLORS.get("error", "red"),
                size=20,
            )
        )
        return

    # --- 2.4. Manipuladores de Eventos Globais ---
    def global_keyboard_handler(e: ft.KeyboardEvent) -> None:
        """Processa atalhos globais de teclado no sistema.

        Args:
            e (ft.KeyboardEvent): Evento de teclado propagado pelo framework.
        """
        if e.ctrl and e.key.lower() == "s":
            if (
                page.route == "/"
                and hasattr(app_state, "fn_generate_term")
                and app_state.fn_generate_term
            ):
                try:
                    result = app_state.fn_generate_term()
                    if asyncio.iscoroutine(result):
                        asyncio.run_coroutine_threadsafe(result, page.loop)
                except Exception as ex:
                    print(f"❌ Erro ao acionar atalho Ctrl+S: {ex}")

        if e.ctrl and e.key in ["Delete", "Del"]:
            if (
                page.route == "/"
                and hasattr(app_state, "fn_clear_form")
                and app_state.fn_clear_form
            ):
                app_state.fn_clear_form()

    page.on_keyboard_event = global_keyboard_handler

    # --- 2.5. Roteamento e Navegação ---
    def route_change(route: ft.RouteChangeEvent) -> None:
        """Gerencia transições de tela reconstruindo a view requerida.

        Args:
            route (ft.RouteChangeEvent): Elemento contendo dados da rota acionada.
        """
        app_state._observers.clear()
        page.clean()

        try:
            if page.route == "/":
                build_home_view(page, app_state)
            elif page.route == "/config":
                build_config_view(page)
            elif page.route == "/mdm":
                build_mdm_view(page, app_state)

            page.update()

        except Exception as e:
            print("❌ ERRO FATAL DE RENDERIZAÇÃO:")
            traceback.print_exc()

            page.clean()
            page.bgcolor = COLORS.get("input_bg", "#1E1E1E")

            page.add(
                ft.Container(
                    expand=True,
                    alignment=ft.alignment.center,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(
                                ft.icons.ERROR_OUTLINE,
                                color=COLORS.get("error", "red"),
                                size=60,
                            ),
                            ft.Text(
                                "Erro Crítico na Interface",
                                size=20,
                                color=COLORS.get("error", "red"),
                                weight="bold",
                            ),
                            ft.Container(
                                bgcolor="#333333",
                                padding=15,
                                border_radius=8,
                                margin=20,
                                width=400,
                                content=ft.Text(
                                    str(e),
                                    color="white",
                                    font_family="Consolas",
                                    size=12,
                                ),
                            ),
                            ft.ElevatedButton(
                                "Tentar Reiniciar",
                                bgcolor=COLORS.get("primary", "blue"),
                                color="white",
                                on_click=lambda _: page.go("/"),
                            ),
                        ],
                    ),
                )
            )
            page.update()

    page.on_route_change = route_change

    # --- 2.6. Verificação de Pré-requisitos ---
    is_sim_mode: bool = config.get("modo_teste", False)

    if not config.get("pasta_raiz_rede") or is_sim_mode:
        if is_sim_mode:
            print("🧪 Modo Teste: Forçando onboarding recorrente...")
        build_onboarding_view(page)
    else:
        page.go("/")


if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets")
