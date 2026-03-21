"""
Módulo de Fábrica de Gateways (Controller Layer).

Centraliza a lógica de seleção entre gateways de produção e simulação,
permitindo a alternância dinâmica de ambientes sem afetar a lógica de negócio.
"""

# ==============================================================================
# 1. IMPORTS E DEPENDÊNCIAS
# ==============================================================================

from core.simulation_mode import IAssetGateway, ITermGateway

# ==============================================================================
# 2. PRODUÇÃO DE INSTÂNCIAS
# ==============================================================================


# --- 2.1. Gateway de Ativos ---
def get_asset_gateway(is_test_mode: bool) -> IAssetGateway:
    """Instancia a implementação correta do gateway de busca de ativos.

    Args:
        is_test_mode (bool): Flag indicando se o sistema está em modo simulação.

    Returns:
        IAssetGateway: Instância de gateway adequada ao ambiente atual.
    """
    if is_test_mode:
        from core.simulation_mode import SimulatedAssetGateway

        return SimulatedAssetGateway()

    from core.production_mode import RealAssetGateway

    return RealAssetGateway()


# --- 2.2. Gateway de Termos ---
def get_term_gateway(is_test_mode: bool) -> ITermGateway:
    """Instancia a implementação correta do gateway de processamento de termos.

    Args:
        is_test_mode (bool): Flag indicando se o sistema está em modo simulação.

    Returns:
        ITermGateway: Instância de gateway adequada ao ambiente atual.
    """
    if is_test_mode:
        from core.simulation_mode import SimulatedTermGateway

        return SimulatedTermGateway()

    from core.production_mode import RealTermGateway

    return RealTermGateway()
