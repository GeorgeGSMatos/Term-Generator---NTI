"""
Módulo de Configurações e Constantes Globais.

Gerencia variáveis de ambiente, resolução de caminhos, identidade visual,
segurança (Keyring) e persistência de preferências do usuário localmente.
"""

# ==============================================================================
# 1. IMPORTS E DEPENDÊNCIAS
# ==============================================================================

import json
import os
import sys
from typing import Any, Dict, List

import flet as ft
import keyring

# --- 1.1. Identificadores de Segurança (Keyring) ---
KEYRING_SERVICE_NAME: str = "GDT_Termos_NTI"
KEYRING_USERNAME_MDM: str = "mdm_admin"
KEYRING_USERNAME_GEMINI: str = "gemini_api"

# --- 1.2. Fallbacks de Segurança ---
DEFAULT_ADMIN_PASSWORD: str = "admin123"

# ==============================================================================
# 2. RESOLUÇÃO DE CAMINHOS E AMBIENTE
# ==============================================================================

# --- 2.1. Determinação da Raiz do Projeto ---
if getattr(sys, "frozen", False):
    BASE_DIR: str = os.path.dirname(sys.executable)
    PROJECT_ROOT: str = BASE_DIR
    PATH_ASSETS: str = os.path.join(sys._MEIPASS, "assets")
else:
    BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT: str = os.path.dirname(BASE_DIR)
    PATH_ASSETS: str = os.path.join(PROJECT_ROOT, "assets")

# --- 2.2. Diretórios de Aplicação (AppData) ---
PATH_LOCAL_USER: str = os.path.join(os.environ["APPDATA"], "GDT_Prefs")
os.makedirs(PATH_LOCAL_USER, exist_ok=True)

# --- 2.3. Persistência de Preferências ---
FILE_USER_PATHS: str = os.path.join(PATH_LOCAL_USER, "user_paths.json")


def get_setting_path() -> str:
    """Retorna o caminho absoluto do arquivo de configurações do usuário.

    Returns:
        str: Caminho completo para o arquivo JSON de preferências locais.
    """
    return FILE_USER_PATHS


# ==============================================================================
# 3. CONSTANTES E MAPEAMENTOS
# ==============================================================================

# --- 3.1. Dimensões da Janela ---
WINDOW_WIDTH: int = 1200
WINDOW_HEIGHT: int = 800
WINDOW_MIN_WIDTH: int = 1000
WINDOW_MIN_HEIGHT: int = 600

# --- 3.2. Assets e Recursos ---
TEMPLATE_FILENAME: str = "template_termo.docx"
APP_ICON: str = "app_icone.ico"

# --- 3.3. Dicionário de Meses ---
MONTH_MAP: Dict[int, str] = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}

# --- 3.4. Regras de Negócio: Movimentação ---
KEYWORDS_MOVEMENT: List[str] = [
    "movimentação interna",
    "movimentacao interna",
    "transferência",
    "troca",
    "substituição",
]

# --- 3.5. Estrutura de Pastas de Rede ---
NETWORK_FOLDERS: Dict[str, Dict[str, str]] = {
    "Entrega": {"pasta": "TE - ENTREGA", "prefixo": "TE"},
    "Devolução": {"pasta": "TD - DEVOLUÇÃO", "prefixo": "TD"},
    "Empréstimo": {"pasta": "TEM - EMPRÉSTIMO", "prefixo": "TEM"},
}

# ==============================================================================
# 4. DESIGN SYSTEM E IDENTIDADE VISUAL
# ==============================================================================

# --- 4.1. Tokens de Cores ---
COLORS: Dict[str, Any] = {
    # Cores Estruturais
    "primary": "#004EA8",
    "primary_light": "#EAF2FA",
    "secondary": "#002F6C",
    "tertiary": "#0072C6",
    # Feedback Semântico
    "green": "#107C10",
    "green_bg": "#E8F5E9",
    "error": "#E31C23",
    "error_bg": "#FDEDED",
    "orange": "#F26522",
    "orange_vibrant": "#F57C00",
    "orange_bg": "#FFF3E0",
    "purple": "#7B1FA2",
    "purple_bg": "#F3E5F5",
    "yellow": "#FFC107",
    # Ícones Técnicos
    "blue_word": "#2B579A",
    "blue_info": "#004EA8",
    # Tipografia
    "text": "#212121",
    "text_secondary": "#666666",
    "text_inverse": "#FFFFFF",
    # Superfícies e UI
    "input_bg": "#FFFFFF",
    "card_bg": "#FFFFFF",
    "background": "#F4F6F9",
    "border": "#D1D9E6",
    "grey_bg": "#F5F5F5",
    "grey_light": "#F8F9FB",
    "grey_icon": "#9E9E9E",
    # Navegação
    "tab_indicator": "#004EA8",
    "tab_text_selected": "#002F6C",
    "tab_text_unselected": "#9E9E9E",
    "tab_overlay": "#EAF2FA",
    # Dashboards
    "dash_grid": "#F5F5F5",
    "dash_border": "#EEEEEE",
    "dash_line_chart": "#004EA8",
    "dash_line_fill": "#EAF2FA",
    # Gráficos
    "dash_pie_entrega": "#002F6C",
    "dash_pie_devolucao": "#004EA8",
    "dash_pie_emprestimo": "#0072C6",
    "dash_pie_movimentacao": "#4FA6E0",
    "chart_sectors": "#004EA8",
    "chart_assets_palette": [
        "#001A33",
        "#00468B",
        "#0078D4",
        "#46A4F1",
        "#9ED1FA",
        "#D1E9FF",
    ],
    # Assets Manuais
    "manual_asset": "#00ACC1",
    "manual_asset_bg": "#E0F7FA",
}

DEFAULT_COLORS = COLORS.copy()


def apply_theme(is_test_mode: bool) -> None:
    """Aplica o tema visual baseado no modo de operação (Produção vs Simulação).

    Modifica o dicionário global COLORS.

    Args:
        is_test_mode (bool): Se verdadeiro, aplica a paleta de cores de teste (Laranja).
    """
    if is_test_mode:
        c_orange = DEFAULT_COLORS.get("orange", "orange")
        c_orange_v = DEFAULT_COLORS.get("orange_vibrant", "orange")

        COLORS.update(
            {
                "primary": c_orange_v,
                "secondary": c_orange,
                "tab_indicator": c_orange_v,
                "tab_text_selected": c_orange,
                "blue_info": c_orange_v,
                "dash_line_chart": c_orange_v,
                "dash_pie_entrega": c_orange,
                "chart_sectors": c_orange_v,
                "chart_assets_palette": [
                    "#610000",
                    "#B71C1C",
                    "#E65100",
                    "#FF9800",
                    "#FFCC80",
                    "#FFF3E0",
                ],
            }
        )
    else:
        COLORS.update(DEFAULT_COLORS)


def get_header_color(is_test_mode: bool) -> str:
    """Calcula a cor de fundo do cabeçalho conforme o modo operacional.

    Args:
        is_test_mode (bool): Flag de ambiente de teste.

    Returns:
        str: Código hexadecimal da cor do cabeçalho.
    """
    return (
        COLORS.get("orange", "orange")
        if is_test_mode
        else COLORS.get("secondary", "#002F6C")
    )


# --- 4.2. Estilos Semânticos por Operação ---
OP_STYLES: Dict[str, Dict[str, Any]] = {
    "Entrega": {
        "icon": ft.icons.ARROW_UPWARD,
        "color": COLORS["green"],
        "bg": COLORS["green_bg"],
    },
    "Devolução": {
        "icon": ft.icons.ARROW_DOWNWARD,
        "color": COLORS["error"],
        "bg": COLORS["error_bg"],
    },
    "Empréstimo": {
        "icon": ft.icons.ACCESS_TIME,
        "color": COLORS["orange_vibrant"],
        "bg": COLORS["orange_bg"],
    },
    "Movimentação": {
        "icon": ft.icons.SWAP_HORIZ,
        "color": COLORS["purple"],
        "bg": COLORS["purple_bg"],
    },
    "Desconhecido": {
        "icon": ft.icons.QUESTION_MARK,
        "color": COLORS["text_secondary"],
        "bg": COLORS["grey_bg"],
    },
}

# ==============================================================================
# 5. SEGURANÇA E GERENCIAMENTO DE CREDENCIAIS
# ==============================================================================


# --- 5.1. Gestão de Senha Administrativa (MDM) ---


def get_mdm_admin_password() -> str:
    """Recupera a senha do MDM do cofre do sistema (Keyring).

    Returns:
        str: Senha administrativa recuperada ou valor padrão.
    """
    try:
        passwd = keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_USERNAME_MDM)
        return passwd if passwd else DEFAULT_ADMIN_PASSWORD
    except Exception as e:
        print(f"⚠️ Erro ao ler senha MDM do Keyring: {e}")
        return DEFAULT_ADMIN_PASSWORD


def set_mdm_admin_password(password: str) -> None:
    """Persiste a senha do MDM no cofre do sistema.

    Args:
        password (str): Nova senha administrativa.
    """
    try:
        keyring.set_password(KEYRING_SERVICE_NAME, KEYRING_USERNAME_MDM, password)
    except Exception as e:
        print(f"❌ Erro ao salvar senha MDM no Keyring: {e}")


# --- 5.2. Gestão de API Key (Gemini) ---


def get_gemini_api_key() -> str:
    """Recupera a chave de API do Gemini do cofre do sistema (Keyring).

    Returns:
        str: API Key do Gemini ou string vazia se não configurada.
    """
    try:
        key = keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_USERNAME_GEMINI)
        return key if key else ""
    except Exception as e:
        print(f"⚠️ Erro ao ler API Key do Keyring: {e}")
        return ""


def set_gemini_api_key(api_key: str) -> None:
    """Persiste a chave de API do Gemini no cofre do sistema.

    Args:
        api_key (str): Chave de API fornecida pelo usuário.
    """
    try:
        keyring.set_password(KEYRING_SERVICE_NAME, KEYRING_USERNAME_GEMINI, api_key)
    except Exception as e:
        print(f"❌ Erro ao salvar API Key no Keyring: {e}")


# ==============================================================================
# 6. PERSISTÊNCIA DE PREFERÊNCIAS E CACHE
# ==============================================================================


def _read_user_paths() -> Dict[str, Any]:
    """Realiza a leitura bruta das preferências do usuário no disco.

    Returns:
        Dict[str, Any]: Conteúdo do arquivo JSON de preferências.
    """
    if os.path.exists(FILE_USER_PATHS):
        try:
            with open(FILE_USER_PATHS, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Aviso: Falha ao ler {FILE_USER_PATHS}: {e}")
    return {}


_settings_cache: Dict[str, Any] = {}


def _invalidate_settings_cache() -> None:
    """Limpa o cache de configurações para forçar releitura do disco."""
    _settings_cache.clear()


def load_setting() -> Dict[str, Any]:
    """Carrega as configurações ativas com suporte a cache.

    Mescla valores default, variáveis de ambiente e preferências do usuário.

    Returns:
        Dict[str, Any]: Dicionário consolidado de configurações do sistema.
    """
    if _settings_cache:
        return dict(_settings_cache)

    # --- 6.1. Configurações Base e Fallbacks ---
    setting = {
        "modo_teste": False,
        "pasta_raiz_rede": "",
        "pasta_pdf": "",
        "cidade": "Salvador",
        "senha_admin": get_mdm_admin_password(),
        "gemini_api_key": get_gemini_api_key(),
    }

    user_home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    default_network_path = os.path.join(
        user_home, "Seu_Diretorio_Aqui", "Sua_Pasta_de_Termos_Aqui"
    )

    user_prefs = _read_user_paths()
    setting.update(user_prefs)

    if not setting.get("pasta_raiz_rede"):
        setting["pasta_raiz_rede"] = default_network_path

    _settings_cache.update(setting)
    return dict(setting)


def save_setting(new_data: Dict[str, Any]) -> None:
    """Persiste as configurações de usuário no disco e cofre.

    Realiza filtragem de chaves para garantir integridade e segurança.

    Args:
        new_data (Dict[str, Any]): Novos dados a serem persistidos.
    """
    allowed_keys: List[str] = ["pasta_raiz_rede", "pasta_pdf", "modo_teste", "cidade"]
    data_to_save = _read_user_paths()

    for key, val in new_data.items():
        if key in allowed_keys:
            data_to_save[key] = val
        elif key == "gemini_api_key":
            set_gemini_api_key(str(val))
        elif key == "senha_admin":
            set_mdm_admin_password(str(val))

    try:
        with open(FILE_USER_PATHS, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=4)
        _invalidate_settings_cache()
    except Exception as e:
        print(f"❌ Erro ao salvar preferências: {e}")
