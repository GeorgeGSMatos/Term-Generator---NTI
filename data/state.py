"""
Módulo de Gerenciamento de Estado Global (Application State Manager).

Implementa o padrão Singleton/Observer para manter uma fonte única de verdade
(Single Source of Truth) e reatividade entre diferentes telas (Home, Histórico,
Configurações) durante o tempo de execução (runtime).
"""

# ==============================================================================
# 1. IMPORTS E DEPENDÊNCIAS
# ==============================================================================

from typing import Any, Callable, Dict, List, Optional

# --- 1.1. Definições de Tipos ---
Observer = Callable[[], None]

# ==============================================================================
# 2. CLASSE DE ESTADO GLOBAL
# ==============================================================================


class AppState:
    """Gerenciador central do estado mutável da aplicação.

    Persiste o ciclo de vida dos dados na memória enquanto o usuário navega
    pelas diferentes visualizações (tabs/views) do sistema.
    """

    def __init__(self) -> None:
        """Inicializa o estado e define contêineres para injeção de dependências."""

        # --- 2.1. Callbacks de Atualização de Sub-Views ---
        self.fn_update_history: Optional[Callable[[], None]] = None
        self.fn_update_dashboard: Optional[Callable[[], None]] = None

        # --- 2.2. Callbacks Injetados Pela Home View ---
        self.fn_generate_term: Optional[Callable[[], None]] = None
        self.fn_clear_form: Optional[Callable[[], None]] = None

        # --- 2.3. Flags de Controle ---
        self.is_generating: bool = False
        self.is_adding_quick: bool = False

        # --- 2.4. Infraestrutura do Padrão Observer ---
        self._observers: List[Observer] = []

        # --- 2.5. Atributos de Dados ---
        self.chamado: str = ""
        self.nome: str = ""
        self.area: str = ""
        self.operacao: str = "Entrega"
        self.obs: str = ""
        self.patrimonio: str = ""
        self.insumo_qtd: str = "1"
        self.insumo_tipo: str = ""
        self.lista_ativos_memoria: List[Dict[str, Any]] = []

    def _reset_values(self) -> None:
        """Limpa as variáveis de dados (Reset Interno)."""
        self.chamado = ""
        self.nome = ""
        self.area = ""
        self.operacao = "Entrega"
        self.obs = ""
        self.patrimonio = ""
        self.insumo_qtd = "1"
        self.insumo_tipo = ""
        self.lista_ativos_memoria = []

    def reset_state(self) -> None:
        """Restaura o estado aos seus valores originais padrão.

        Notifica todos os componentes registrados (Observers) para atualizar
        a interface visual após a limpeza.
        """
        self._reset_values()
        self.notify_observers()

    def to_dict(self) -> Dict[str, Any]:
        """Extrai um snapshot do estado em formato dicionário.

        Returns:
            Dict[str, Any]: Variáveis atuais consolidadas em um dicionário.
        """
        return {
            "chamado": self.chamado,
            "nome": self.nome,
            "area": self.area,
            "operacao": self.operacao,
            "obs": self.obs,
            "patrimonio": self.patrimonio,
            "insumo_tipo": self.insumo_tipo,
            "insumo_qtd": self.insumo_qtd,
            "total_ativos": len(self.lista_ativos_memoria),
        }

    # ==========================================================================
    # 3. MÉTODOS DO PADRÃO OBSERVER
    # ==========================================================================

    def attach(self, observer: Observer) -> None:
        """Registra um novo observador para mudanças de estado.

        Args:
            observer (Observer): Função callback de atualização da View.
        """
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer: Observer) -> None:
        """Remove a reatividade de um componente (ex: tela destruída).

        Args:
            observer (Observer): Função callback para desvincular.
        """
        if observer in self._observers:
            self._observers.remove(observer)

    def notify_observers(self) -> None:
        """Dispara a atualização (refresh) em todos os ouvintes registrados."""
        for observer in self._observers:
            try:
                observer()
            except Exception as e:
                print(f"⚠️ Erro ao notificar Observer: {e}")
