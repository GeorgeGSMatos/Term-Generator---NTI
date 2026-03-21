"""
Módulo de Higienização de Dados Brutos (Silver Layer — ETL Middleware).

Opera como middleware de transparência e qualidade, consumindo extrações
difusas de IA ou CSV, aplicando dicionários formais de MDM, correção Fuzzy Logic
de strings erráticas e formatadores sintáticos padronizados antes de submeter
os dados à base Gold (Relacional).
"""

# ==============================================================================
# 1. IMPORTS E DEPENDÊNCIAS
# ==============================================================================

import json
import os
import re
from difflib import get_close_matches
from typing import Any, Dict, List

# ==============================================================================
# 2. CONFIGURAÇÕES E ENGINE DE REGRAS
# ==============================================================================

# --- 2.1. Caminhos e Arquivos de Regras ---
BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
FILE_CLEANING_RULES: str = os.path.join(BASE_DIR, "cleaning_rules.json")

# --- 2.2. Esquema de Fallback Seguro ---
DEFAULT_FALLBACK_RULES: Dict[str, Any] = {
    "dicionarios": {"fabricantes": {}, "tipos": {}},
    "limiares": {"confianca_fuzzy": 80, "tamanho_minimo_fuzzy": 3},
}


def load_cleaning_rules(filepath: str = FILE_CLEANING_RULES) -> Dict[str, Any]:
    """Carrega regras MDM dinâmicas de um manifesto JSON.

    Traz à memória os aliases e sinônimos aprovados. Atua de forma defensiva,
    provendo fallbacks puros em caso de ausência ou corrupção do arquivo.

    Args:
        filepath (str): Endereço absoluto do arquivo de regras JSON.

    Returns:
        Dict[str, Any]: Objeto estruturado com as regras de higienização.
    """
    if not os.path.exists(filepath):
        print(f"⚠️ Aviso: Arquivo de regras ausente em '{filepath}'.")
        return DEFAULT_FALLBACK_RULES

    try:
        with open(filepath, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, Exception) as e:
        print(f"❌ Erro Crítico ao carregar regras (JSON Corrompido?): {e}")
        return DEFAULT_FALLBACK_RULES


# --- 2.3. Inicialização do Cache Global de Regras ---
CLEANING_RULES: Dict[str, Any] = load_cleaning_rules()


# ==============================================================================
# 3. MOTOR CENTRAL DE NORMALIZAÇÃO
# ==============================================================================


def normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Esteriliza e uniformiza propriedades de um dicionário de ativo.

    Executa múltiplas baterias de correções sequenciais: Match Exato,
    Fuzzy String e Heurísticas de Fallback para garantir a qualidade final.

    Args:
        item (Dict[str, Any]): Fragmento JSON bruto (IA, CSV ou Manual).

    Returns:
        Dict[str, Any]: Registro higienizado com 'descricao_visual' consolidada.
    """
    # --- 3.1. Captura e Limpeza de Espaços ---
    raw_type: str = str(item.get("tipo", "")).strip()
    raw_fab: str = str(item.get("fabricante", "")).strip()
    raw_model: str = str(item.get("modelo", "")).strip()

    # --- 3.2. Carregamento de Dicionários Locais ---
    dict_tipos: Dict[str, str] = CLEANING_RULES.get("dicionarios", {}).get("tipos", {})
    dict_fabs: Dict[str, str] = CLEANING_RULES.get("dicionarios", {}).get(
        "fabricantes", {}
    )

    # --- 3.3. Tradução Iterativa ---
    max_hops = 3

    new_type, hops_t = raw_type, 0
    while new_type in dict_tipos and hops_t < max_hops:
        next_type = dict_tipos[new_type]
        if next_type == new_type:
            break
        new_type = next_type
        hops_t += 1

    new_fab, hops_f = raw_fab, 0
    while new_fab in dict_fabs and hops_f < max_hops:
        next_fab = dict_fabs[new_fab]
        if next_fab == new_fab:
            break
        new_fab = next_fab
        hops_f += 1

    new_model: str = raw_model

    # --- 3.4. Motor Fuzzy Matching ---
    valores_padrao_fabs: List[str] = list(set(dict_fabs.values()))
    limiar_conf = CLEANING_RULES.get("limiares", {}).get("confianca_fuzzy", 80)
    cutoff = float(limiar_conf) / 100.0 if limiar_conf > 1 else float(limiar_conf)
    min_size = CLEANING_RULES.get("limiares", {}).get("tamanho_minimo_fuzzy", 3)

    if new_fab not in valores_padrao_fabs and len(new_fab) >= min_size:
        matches = get_close_matches(new_fab, valores_padrao_fabs, n=1, cutoff=cutoff)
        if matches:
            new_fab = matches[0]

    # --- 3.5. Heurísticas de Fallback por Palavras-Chave ---
    analysis_text = f"{new_type} {new_model}".lower()

    if new_type not in dict_tipos.values():
        if "notebook" in analysis_text or "laptop" in analysis_text:
            new_type = "Notebook"
        elif any(
            x in analysis_text
            for x in ["desktop", "computador", "pc", "all in one", "workstation"]
        ):
            new_type = "Desktop"
        elif "monitor" in analysis_text or "tela" in analysis_text:
            new_type = "Monitor"
        elif "tv" in analysis_text or "televis" in analysis_text:
            new_type = "TV"
        elif "projetor" in analysis_text or "datashow" in analysis_text:
            new_type = "Projetor"
        else:
            new_type = "Equipamento"

    # --- 3.6. Correção de Legacy/Dirty Data (Ex: LOG-, DATEN) ---
    if ("LOG-" in new_fab.upper() or "DATEN" in new_fab.upper()) and len(new_fab) > 10:
        if not new_model:
            new_model = new_fab
        if "LOG" in new_fab.upper():
            new_fab = "Login"
        elif "DATEN" in new_fab.upper():
            new_fab = "Daten"

    # --- 3.7. Desduplicação de Fabricante no Nome do Modelo ---
    if (
        new_fab
        and new_fab.lower() in new_model.lower()
        and new_fab.lower() not in ["genérico", "generic"]
    ):
        pattern = re.compile(re.escape(new_fab), re.IGNORECASE)
        new_model = pattern.sub("", new_model).strip()

    # --- 3.8. Formatação e Capitalização Estética ---
    new_model = new_model.replace("- -", "-").lstrip("- ").strip()
    new_fab = new_fab.title() if new_fab else "Genérico"

    upper_brands = ["HP", "LG", "AOC", "IBM"]
    if new_fab.upper() in upper_brands:
        new_fab = new_fab.upper()

    # --- 3.9. Consolidação dos Campos ---
    item["tipo"] = new_type
    item["fabricante"] = new_fab
    item["modelo"] = new_model
    item["descricao_visual"] = f"{new_type} {new_fab} - {new_model}".replace(
        " - - ", " - "
    ).strip(" -")

    return item


# ==============================================================================
# 4. GESTÃO DE REGRAS MDM (PUBLIC API)
# ==============================================================================


def mdm_get_rules() -> List[Dict[str, str]]:
    """Extrai e compila as regras JSON em formato plano para a UI.

    Returns:
        List[Dict[str, str]]: Lista de mapeamentos (Target, Busca, Substituto).
    """
    rules_data: Dict[str, Any] = load_cleaning_rules()
    flat_rules: List[Dict[str, str]] = []
    dicionarios = rules_data.get("dicionarios", {})

    for key in ["fabricantes", "tipos"]:
        mapping = dicionarios.get(key, {})
        ui_label = "Fabricante" if key == "fabricantes" else "Tipo"

        for search, replace in mapping.items():
            flat_rules.append(
                {"target": ui_label, "search": search, "replace": replace}
            )

    return flat_rules


def _save_cleaning_rules(rules_data: Dict[str, Any], action_desc: str) -> bool:
    """Invólucro privado para persistir alterações no arquivo físico (DRY).

    Args:
        rules_data (Dict[str, Any]): Novas regras para salvar.
        action_desc (str): Descrição da ação para logs (ex: 'adicionar').

    Returns:
        bool: True se a escrita foi bem-sucedida.
    """
    global CLEANING_RULES
    try:
        with open(FILE_CLEANING_RULES, "w", encoding="utf-8") as file:
            json.dump(rules_data, file, indent=4, ensure_ascii=False)
        CLEANING_RULES = rules_data
        return True
    except Exception as e:
        print(f"❌ Erro ao {action_desc} regra (I/O Exception): {e}")
        return False


def mdm_add_rule(target: str, search: str, replace: str) -> bool:
    """Injeta uma nova regra de limpeza no repositório MDM.

    Args:
        target (str): Categoria-alvo ('Fabricante' ou 'Tipo').
        search (str): Valor bruto/sujo mapeado.
        replace (str): Valor limpo aprovado.

    Returns:
        bool: Condição de sucesso do salvamento.
    """
    if search.lower() == replace.lower():
        print("⚠️ Bloqueio: Alvo e substituição são idênticos.")
        return False

    rules_data = load_cleaning_rules()

    if "dicionarios" not in rules_data:
        rules_data["dicionarios"] = {"fabricantes": {}, "tipos": {}}

    dict_key = "fabricantes" if target.lower() == "fabricante" else "tipos"
    rules_data["dicionarios"][dict_key][search] = replace

    return _save_cleaning_rules(rules_data, "salvar")


def mdm_delete_rule(target: str, search_key: str) -> bool:
    """Remove uma regra específica do repositório MDM.

    Args:
        target (str): Categoria-alvo ('Fabricante' ou 'Tipo').
        search_key (str): Chave identificadora da regra.

    Returns:
        bool: True se removida e persistida com sucesso.
    """
    rules_data = load_cleaning_rules()
    dict_key = "fabricantes" if target.lower() == "fabricante" else "tipos"

    mapping = rules_data.get("dicionarios", {}).get(dict_key, {})
    if search_key in mapping:
        del mapping[search_key]
        return _save_cleaning_rules(rules_data, "deletar")

    return False


# ==============================================================================
# 5. TESTE DE UNIDADE
# ==============================================================================

if __name__ == "__main__":
    test_items: List[Dict[str, Any]] = [
        {"tipo": "Laptop", "fabricante": "Dell Inc.", "modelo": "Latitude 5420"},
        {"tipo": "Display", "fabricante": "Samsumg", "modelo": "Smart TV 50"},
        {"tipo": "All in One", "fabricante": "LOG-LN3000X64", "modelo": ""},
    ]

    print("--- TESTE DE HIGIENIZAÇÃO (NORMALIZAÇÃO) ---")
    for item in test_items:
        clean = normalize_item(item)
        print(f"RESULTADO: {clean['descricao_visual']}")
