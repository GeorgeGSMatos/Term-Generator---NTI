"""
Módulo de Componentes de Interface (View Layer - UI Kit).

Centraliza a criação de widgets customizados, temas e animações do Flet,
garantindo consistência visual e reutilização de código em toda a aplicação.
"""

# ==============================================================================
# 1. IMPORTS E DEPENDÊNCIAS
# ==============================================================================
import asyncio
from typing import Any, Callable, Dict, List, Optional, Union

import flet as ft

from core.settings import COLORS

# ==============================================================================
# 2. ANIMAÇÕES E EFEITOS VISUAIS
# ==============================================================================


async def shake_control(control_ref: ft.Ref) -> None:
    """Aplica uma animação de tremor horizontal rápida para indicar erro ou entrada inválida.

    Invocado na camada de Validação sem travar a navegação (Event Loop assíncrono).

    Args:
        control_ref (ft.Ref): Referência ponteiro da classe Flet control-target.
    """
    if not control_ref.current:
        return

    original_offset = control_ref.current.offset or ft.transform.Offset(0, 0)
    control_ref.current.animate_offset = ft.animation.Animation(
        50, ft.AnimationCurve.BOUNCE_OUT
    )

    for _ in range(3):
        control_ref.current.offset = ft.transform.Offset(0.02, 0)
        control_ref.current.update()
        await asyncio.sleep(0.05)

        control_ref.current.offset = ft.transform.Offset(-0.02, 0)
        control_ref.current.update()
        await asyncio.sleep(0.05)

    control_ref.current.offset = original_offset
    control_ref.current.update()


# ==============================================================================
# 3. CONTAINERS MATRIZ
# ==============================================================================


def create_standard_card(
    content: ft.Control,
    padding: int = 20,
    border_radius: int = 12,
    expand: Union[bool, int] = False,
) -> ft.Container:
    """Fabrica um Card Branco Elevado com sombra macia padrão.

    Usado para Widgets do Dashboard, Enclosures de Tabelas de Histórico,
    e Seções de Configurações, padronizando elevações e arredondamentos.

    Args:
        content (ft.Control): O nó filho abraçado pelo contêiner.
        padding (int): Distanciamento Interno Padding (Padrão: 20).
        border_radius (int): Nível de chanfro da borda CSS (Padrão: 12).
        expand (Union[bool, int]): Escalonamento Flex.

    Returns:
        ft.Container: Instância enclausurada e renderizada.
    """
    return ft.Container(
        bgcolor=COLORS.get("card_bg", "white"),
        padding=padding,
        border_radius=border_radius,
        expand=expand,
        shadow=ft.BoxShadow(
            blur_radius=10,
            color=ft.colors.with_opacity(0.05, "black"),
            offset=ft.Offset(0, 2),
        ),
        content=content,
    )


def create_icon_row_card(
    title: str,
    subtitle: str,
    icon_name: str,
    accent_color: str,
    bg_icon_color: str,
    trailing_control: Optional[ft.Control] = None,
    left_border_color: Optional[str] = None,
) -> ft.Container:
    """Cria um Card List-Item com um ícone circular ancorado à esquerda do texto.

    Args:
        title (str): Texto Principal H1 do item.
        subtitle (str): Sub-texto ou detalhe da row.
        icon_name (str): Material Flet Icon Code.
        accent_color (str): Cor Primária (Ícone).
        bg_icon_color (str): Cor Secundária fundo (Círculo).
        trailing_control (Optional[ft.Control]): Nó livre na extrema direita (Lixeira, Botão).
        left_border_color (Optional[str]): Faixa grossa indicativa ancorada à esquerda.

    Returns:
        ft.Container: Row injetável Flet.
    """
    row_controls = [
        # --- 3.1. Coluna do Ícone ---
        ft.Container(
            content=ft.Icon(icon_name, color=accent_color, size=20),
            bgcolor=bg_icon_color,
            padding=10,
            border_radius=50,
        ),
        # --- 3.2. Textos Aninhados ---
        ft.Column(
            expand=True,
            spacing=2,
            controls=[
                ft.Text(
                    title,
                    weight=ft.FontWeight.W_600,
                    size=14,
                    color=COLORS.get("text", "black"),
                ),
                ft.Text(
                    subtitle,
                    size=12,
                    color=COLORS.get("text_secondary", "grey"),
                    no_wrap=True,
                ),
            ],
        ),
    ]

    if trailing_control:
        row_controls.append(trailing_control)

    container = ft.Container(
        margin=ft.margin.only(bottom=10),
        border_radius=ft.border_radius.only(
            top_right=10, bottom_right=10, top_left=4, bottom_left=4
        ),
        bgcolor=COLORS.get("card_bg", "white"),
        padding=ft.padding.symmetric(vertical=12, horizontal=15),
        shadow=ft.BoxShadow(
            blur_radius=15,
            color=ft.colors.with_opacity(0.08, "black"),
            offset=ft.Offset(0, 4),
        ),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.START, spacing=15, controls=row_controls
        ),
    )

    if left_border_color:
        container.border = ft.border.only(
            left=ft.BorderSide(width=5, color=left_border_color)
        )

    return container


# ==============================================================================
# 4. VARIAÇÕES DE CARDS CONTEXTUAIS
# ==============================================================================


def create_smart_asset_card(
    item: Dict[str, Any], on_delete: Optional[Callable] = None
) -> ft.Container:
    """Analisa inteligentemente se um Dicionário é um Ativo Real ou um Acessório.

    Retorna a renderização list-card inteiramente customada via regras e tipografias dinâmicas.

    Args:
        item (Dict): Dicionário Mapeado pela Silver Layer (Ativo físico limpo).
        on_delete (Optional[Callable]): Injeção da Callback Destrutiva da ListView.

    Returns:
        ft.Container: Card Pronto atrelado via closure contextualizada.
    """
    patrimonio = str(item.get("patrimonio", "S/N"))
    is_manual = item.get("origem") == "Manual"
    is_real_asset = (patrimonio not in ["S/N", "N/A", ""]) or is_manual

    trailing_control = None
    if on_delete:
        trailing_control = ft.IconButton(
            icon=ft.icons.CLOSE_ROUNDED,
            icon_color=COLORS.get("error", "red"),
            icon_size=20,
            on_click=on_delete,
        )

    if is_real_asset:
        title = patrimonio
        subtitle = f"{item.get('descricao_visual', 'Equipamento Genérico')} - SN: {item.get('serial', 'S/N')}"
        if is_manual:
            color, bg, icon = (
                COLORS.get("manual_asset", "#00ACC1"),
                COLORS.get("manual_asset_bg", "#E0F7FA"),
                ft.icons.COMPUTER,
            )
        else:
            color, bg, icon = (
                COLORS.get("tertiary", "blue"),
                COLORS.get("primary_light", "lightblue"),
                ft.icons.COMPUTER,
            )
    else:
        title = str(item.get("descricao_visual") or item.get("modelo") or "Acessório")
        subtitle = f"Qtd: {item.get('qtd', 1)}"
        color, bg, icon = (
            COLORS.get("orange_vibrant", "orange"),
            COLORS.get("orange_bg", "lightorange"),
            ft.icons.KEYBOARD_ALT,
        )

    return create_icon_row_card(
        title=title,
        subtitle=subtitle,
        icon_name=icon,
        accent_color=color,
        bg_icon_color=bg,
        trailing_control=trailing_control,
        left_border_color=color,
    )


def create_directory_picker_card(
    title: str,
    subtitle_path: str,
    icon_name: str,
    ref_field: ft.Ref,
    on_click: Callable[[ft.ControlEvent], None],
) -> ft.Container:
    """Cria um card com seletor de diretórios interativo.

    Args:
        title (str): Título da configuração.
        subtitle_path (str): Caminho atual exibido.
        icon_name (str): Nome do ícone.
        ref_field (ft.Ref): Referência para o campo de texto.
        on_click (Callable): Função chamada ao clicar para buscar pasta.

    Returns:
        ft.Container: Widget configurado.
    """
    txt_field = ft.TextField(
        ref=ref_field,
        value=subtitle_path,
        text_size=13,
        border="none",
        height=35,
        read_only=True,
        color=COLORS.get("text", "black"),
        hint_text="Caminho não configurado...",
    )

    btn_search = ft.IconButton(
        ft.icons.FOLDER_OPEN,
        icon_color=COLORS.get("text_secondary", "grey"),
        icon_size=24,
        tooltip="Procurar Pasta",
        on_click=on_click,
    )

    return ft.Container(
        margin=ft.margin.only(bottom=10),
        border_radius=ft.border_radius.only(
            top_right=10, bottom_right=10, top_left=4, bottom_left=4
        ),
        bgcolor=COLORS.get("card_bg", "white"),
        padding=ft.padding.all(20),
        border=ft.border.only(
            left=ft.BorderSide(width=5, color=COLORS.get("primary", "blue"))
        ),
        shadow=ft.BoxShadow(
            blur_radius=15,
            color=ft.colors.with_opacity(0.08, "black"),
            offset=ft.Offset(0, 4),
        ),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.START,
            spacing=15,
            controls=[
                # --- 4.1. Ícone Circular ---
                ft.Container(
                    content=ft.Icon(
                        icon_name, color=COLORS.get("primary", "blue"), size=20
                    ),
                    bgcolor=COLORS.get("primary_light", "lightblue"),
                    padding=10,
                    border_radius=50,
                ),
                # --- 4.2. Coluna Texto + Campo editável ---
                ft.Column(
                    expand=True,
                    spacing=2,
                    controls=[
                        ft.Text(
                            title,
                            weight=ft.FontWeight.W_600,
                            size=14,
                            color=COLORS.get("text", "black"),
                        ),
                        txt_field,
                    ],
                ),
                btn_search,
            ],
        ),
    )


# ==============================================================================
# 5. BOTÕES E CONTROLES
# ==============================================================================


def create_primary_button(
    text: str,
    icon_name: Optional[str] = None,
    on_click: Optional[Callable] = None,
    color_override: Optional[str] = None,
    full_width: bool = False,
) -> ft.ElevatedButton:
    """Fábrica do Padrão CTA do App (Call To Action Primário Vibrante).

    Args:
        text (str): String central.
        icon_name (Optional[str]): Ícone de ênfase esquerdo opcional.
        on_click (Optional[Callable]): Hook/Action engatilhado pelo click.
        color_override (Optional[str]): Subscreve o Background nativo (Verde).
        full_width (bool): Expansibilidade Inline Horizontal máxima.

    Returns:
        ft.ElevatedButton: Instância pronta para submissões.
    """
    bg_color = color_override or COLORS.get("green", "green")

    content_controls = []
    if icon_name:
        content_controls.append(ft.Icon(icon_name, size=20))
    content_controls.append(ft.Text(text, weight=ft.FontWeight.BOLD))

    return ft.ElevatedButton(
        content=ft.Row(content_controls, alignment=ft.MainAxisAlignment.CENTER),
        bgcolor=bg_color,
        color=COLORS.get("text_inverse", "white"),
        height=55,
        width=float("inf") if full_width else None,
        elevation=0,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
        on_click=on_click,
    )


def create_status_badge(
    text: str, icon_name: str, color: str, bg_color: str
) -> ft.Container:
    """Implementa o micro-selo visual indicador de estabilidade (Badge).

    Aplica fundos translúcidos elegantes imitando Pill-Shapes modernas.
    """
    return ft.Container(
        padding=10,
        bgcolor=bg_color,
        border_radius=8,
        content=ft.Row(
            [
                ft.Icon(icon_name, color=color, size=20),
                ft.Text(text, size=12, color=color, weight=ft.FontWeight.BOLD),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        ),
    )


# ==============================================================================
# 6. ENTRADAS E FILTROS
# ==============================================================================


def create_form_input(
    label: str,
    icon: str,
    ref: ft.Ref,
    value: str = "",
    on_change: Optional[Callable] = None,
    on_submit: Optional[Callable] = None,
    multiline: bool = False,
    lines: int = 1,
) -> ft.TextField:
    """Construção Unificada de Elementos Text-Field da View Form.

    Uniformiza tamanhos, paddings, cores de Focus Ring ao se clicar no input,
    isolando as verbosidades inerentes ao Componente Base.
    """
    return ft.TextField(
        ref=ref,
        label=label,
        value=value,
        on_change=on_change,
        on_submit=on_submit,
        text_size=13,
        label_style=ft.TextStyle(color=COLORS.get("text_secondary", "grey"), size=12),
        prefix_icon=icon,
        border_radius=8,
        bgcolor=COLORS.get("input_bg", "#F9FAFB"),
        border_color=COLORS.get("border", "#E0E0E0"),
        focused_border_color=COLORS.get("primary", "blue"),
        content_padding=15,
        multiline=multiline,
        min_lines=lines,
        max_lines=lines * 2 if multiline else 1,
    )


def create_filter_dropdown(
    label: str,
    options: List[tuple],
    value: Optional[str] = None,
    width: int = 140,
    on_change: Optional[Callable] = None,
    ref: Optional[ft.Ref] = None,
) -> ft.Dropdown:
    """Menu Seletor Submisso compacto engatilhado na Topbar para filtragens OLAP."""
    return ft.Dropdown(
        ref=ref,
        label=label,
        value=value,
        width=width,
        text_size=12,
        content_padding=8,
        border_radius=8,
        bgcolor=COLORS.get("input_bg", "#F9FAFB"),
        border_color=COLORS.get("border", "transparent"),
        focused_border_color=COLORS.get("primary", "blue"),
        label_style=ft.TextStyle(color=COLORS.get("text_secondary", "grey"), size=12),
        options=[ft.dropdown.Option(opt[0], opt[1]) for opt in options],
        on_change=on_change,
    )


def scale_dd(dd: ft.Dropdown) -> ft.Dropdown:
    """Manipulador de Responsividade Flex que escala instâncias de Selectors sob demandas."""
    dd.text_size = 14
    dd.label_style = ft.TextStyle(size=13, color=COLORS.get("text_secondary", "grey"))
    dd.content_padding = 18
    return dd


# ==============================================================================
# 7. REPRESENTAÇÃO GRÁFICA GERAL
# ==============================================================================


def create_progress_bar_row(
    name: str, display_value: str, ratio: float, bar_color: str
) -> ft.Column:
    """Gráfico Horizontal customizado de Barras Dinâmicas para os Cartões Dashboard.

    Args:
        name (str): Label Identificador.
        display_value (str): Valor em texto sendo exibido no final (ex: '45.2%').
        ratio (float): Razão preenchida da barra (0.0 até 1.0).
        bar_color (str): Hexcode da preenchimetría.

    Returns:
        ft.Column: O bloco visual compondo Label, Número e a Faixa Pintada.
    """

    return ft.Column(
        spacing=5,
        controls=[
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text(
                        name,
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=COLORS.get("text", "black"),
                        no_wrap=True,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        expand=True,
                    ),
                    ft.Text(
                        display_value,
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=COLORS.get("text", "black"),
                    ),
                ],
            ),
            ft.Container(
                height=10,
                border_radius=5,
                clip_behavior=ft.ClipBehavior.HARD_EDGE,
                content=ft.ProgressBar(
                    value=ratio,
                    color=bar_color,
                    bgcolor=COLORS.get("border", "#EEEEEE"),
                ),
            ),
        ],
    )


# ==============================================================================
# 8. AJUDANTES UNIVERSAIS REUTILIZÁVEIS
# ==============================================================================


def show_snackbar(
    page: ft.Page, message: str, color_key: str = "green", icon: Optional[str] = None
) -> None:
    """Implementa Notificações Toast/Alert flutuantes com Auto-Dismiss.

    Isola e resolve os encadeamentos complexos de Snackbar em Flet injetando diretamente no DOM Root Page.
    """
    content_controls = []
    if icon:
        content_controls.append(
            ft.Icon(icon, color=COLORS.get("text_inverse", "white"), size=18)
        )
    content_controls.append(
        ft.Text(message, size=16, color=COLORS.get("text_inverse", "white"))
    )

    page.snack_bar = ft.SnackBar(
        content=ft.Row(content_controls, spacing=10),
        bgcolor=COLORS.get(color_key, color_key),
    )
    page.snack_bar.open = True
    page.update()


def handle_filepicker_result(e: ft.FilePickerResultEvent, text_ref: ft.Ref) -> None:
    """Closure Pura que repassa interativamente os Mutáveis Eventos OS Picker Win32
    para um Input de Texto alvo amarrado pela ref.
    """
    if e.path:
        text_ref.current.value = e.path
        text_ref.current.update()


# ==============================================================================
# 9. MACRO-SEÇÕES: CABEÇALHOS E NAVEGAÇÃO
# ==============================================================================


def create_page_header(icon_name: str, title: str, subtitle: str) -> ft.Column:
    """Módulo base Header com hierarquia de Tipografia H1/H2 padronizada de Menu."""
    return ft.Column(
        [
            ft.Row(
                [
                    ft.Icon(icon_name, size=35, color=COLORS.get("primary", "blue")),
                    ft.Text(
                        title,
                        size=28,
                        weight=ft.FontWeight.BOLD,
                        color=COLORS.get("text", "black"),
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
                spacing=15,
            ),
            ft.Text(subtitle, size=14, color=COLORS.get("text_secondary", "grey")),
        ],
        spacing=5,
    )


def nav_icon(
    icon_name: str, size: int = 30, color: Optional[str] = None
) -> ft.Container:
    """Atua como Spacer Vertical de Paddings para ícones encapsulando o Rail Lateral Esquerdo."""
    return ft.Container(
        content=ft.Icon(icon_name, size=size, color=color),
        padding=ft.padding.symmetric(vertical=15),
    )


def create_hero_header(
    icon_name: str, title: str, subtitle: str, header_bg: str
) -> ft.Container:
    """Configura o cabeçalho gigante imersivo "Hero" das Views Secundárias Analíticas (Dash, Logs).

    Aplica elevação BoxShadow de desfoque amplo, texto claro legível em fundo vívido e padding relaxado
    garantindo imersão UX coesa respeitando DRY e Clean View Architect.
    """
    return ft.Container(
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
                        icon_name, color=COLORS.get("text_inverse", "white"), size=45
                    ),
                ),
                ft.Column(
                    [
                        ft.Text(
                            title,
                            size=32,
                            weight="bold",
                            color=COLORS.get("text_inverse", "white"),
                        ),
                        ft.Text(
                            subtitle,
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
