"""
Módulo de Repositório de Strings (Core Layer).

Centraliza todas as mensagens, rótulos e constantes de texto utilizadas
na interface gráfica para garantir consistência e facilitar manutenção.
"""

# ==============================================================================
# 1. NOTIFICAÇÕES GERAIS E ALERTAS
# ==============================================================================

MSG_SUCESSO: str = "Sucesso!"
MSG_ERRO: str = "Erro"
MSG_PROCESSANDO: str = "Processando..."
MSG_INICIANDO: str = "Iniciando..."
MSG_VERIFICANDO_PASTAS: str = "Verificando pastas..."
MSG_ESCREVENDO_WORD: str = "Escrevendo Word..."
MSG_GERANDO_PDF: str = "Gerando PDF..."
MSG_SALVANDO_HISTORICO: str = "Salvando Histórico..."
MSG_CONCLUIDO: str = "Concluído!"
MSG_ERRO_DB: str = "Salvo (Erro DB)"
MSG_CAMPO_OBRIGATORIO: str = "Campo obrigatório"
MSG_NENHUM_ITEM: str = "Nenhum item adicionado"
MSG_ARQUIVO_NAO_ENCONTRADO: str = "Arquivo Word não encontrado."

# --- 1.1. Alertas Específicos ---
MSG_ATIVO_NAO_ENCONTRADO: str = (
    "Ativo não encontrado! Clique no '+' para adicionar manualmente."
)
MSG_OFFLINE_PRODUCAO: str = "Offline: Cadastro bloqueado em Produção."
MSG_RESUMO_COPIADO: str = "Resumo copiado para a área de transferência!"
MSG_ERRO_REDE_OBRIGATORIA: str = "A pasta de rede é obrigatória!"
MSG_CONFIG_SALVA: str = "Configurações salvas com sucesso!"
MSG_SISTEMA_CONECTADO: str = "Sistema configurado e conectado!"
MSG_REGISTRO_REMOVIDO: str = "Registro removido com sucesso."

# --- 1.2. Validações ---
MSG_BUSCA_INVALIDA: str = "Busca Inválida ou Perigosa"
MSG_PREENCHER_NOME_SETOR: str = "Preencha Nome e Setor do Colaborador"
MSG_ADICIONAR_ATIVO: str = "Adicione pelo menos um ativo"


# ==============================================================================
# 2. CABEÇALHOS E TÍTULOS
# ==============================================================================

# --- 2.1. Main UI ---
TITLE_APP_HEADER: str = "GERENCIADOR DE TERMOS"
TITLE_SIMULATION_MODE: str = "MODO SIMULAÇÃO"
TITLE_INFO_CHAMADO: str = "Informações do Chamado"
TITLE_EQUIPAMENTOS: str = "Equipamentos e Insumos"

# --- 2.2. Dashboard ---
TITLE_DASH_GERAL: str = "Visão Geral"
TITLE_DASH_DISTRIBUICAO: str = "Distribuição Percentual"
TITLE_DASH_SETORES: str = "MAIORES SETORES SOLICITANTES"
TITLE_DASH_ATIVOS: str = "INTELIGÊNCIA DE ATIVOS"
TITLE_DASH_TIMELINE: str = "VOLUME TEMPORAL"
TITLE_DASH_TICKER: str = "Últimas Atividades"

# --- 2.3. Configurações ---
TITLE_CONFIG: str = "Configurações"
SUBTITLE_CONFIG: str = "Gerencie diretórios e preferências do sistema."
TITLE_ONBOARDING_MAIN: str = "Bem-vindo ao GDT"
SUBTITLE_ONBOARDING: str = "Sistema NTI Inteligente"
TITLE_ONBOARDING_STORAGE: str = "Configuração de Armazenamento"


# ==============================================================================
# 3. RÓTULOS E BOTÕES
# ==============================================================================

# --- 3.1. Formulários ---
LABEL_CHAMADO: str = "Chamado"
LABEL_COLABORADOR: str = "Colaborador(a)"
LABEL_AREA: str = "Área / Setor"
LABEL_TIPO_OP: str = "Tipo de Operação"
LABEL_BUSCA_PATRIMONIO: str = "Buscar Patrimônio..."
LABEL_INSUMO: str = "Insumos / Acessórios"
LABEL_OBS: str = "Observações"
LABEL_TOQUE_ADD: str = "Toque para adicionar:"

# --- 3.2. Botões ---
BTN_GERAR: str = "GERAR TERMO"
BTN_COPIAR_RESUMO: str = "Copiar Resumo p/ Chamado"
BTN_ABRIR_PASTA: str = "Abrir Pasta"
BTN_CONCLUIR: str = "Concluir"
BTN_FECHAR: str = "Fechar"
BTN_CANCELAR: str = "Cancelar"
BTN_SIM: str = "Sim"
BTN_EXCLUIR: str = "Excluir"
BTN_SALVAR_CONFIG: str = "Salvar Alterações"
BTN_INICIAR_SISTEMA: str = "Iniciar Sistema"


# ==============================================================================
# 4. DIÁLOGOS E PLACEHOLDERS
# ==============================================================================

DLG_TITLE_LIMPAR: str = "Deseja limpar tudo?"
DLG_TITLE_EXCLUIR: str = "Confirmar Exclusão"
DLG_BODY_EXCLUIR: str = "Tem certeza que deseja excluir permanentemente este registro?"
DLG_TITLE_ADD_MANUAL: str = "Adicionar Manualmente"
DLG_BODY_ADD_MANUAL: str = "Preencha os dados do ativo abaixo:"

PLACEHOLDER_NO_SECTOR_DATA: str = "Sem dados de setores."
PLACEHOLDER_NO_ASSET_DATA: str = "Sem métricas de ativos."
PLACEHOLDER_NO_ACTIVITY: str = "Nenhuma atividade recente."
PLACEHOLDER_NO_DETAILS: str = "Nenhum detalhe disponível para este registro."


# ==============================================================================
# 5. DADOS DE SIMULAÇÃO
# ==============================================================================

SIM_CHAMADO: str = "CH-SIMULACAO"
SIM_NOME: str = "Colaborador Teste"
SIM_AREA: str = "Engenharia de Software"
SIM_OPERACAO: str = "Entrega"
SIM_OBS: str = "Simulação de fluxo"


# ==============================================================================
# 6. SUGESTÕES DE TEXTO
# ==============================================================================

SUGESTOES_OBS: list[str] = [
    "Equipamento Novo;",
    "Equipamento Rotativo;",
    "Movimentação Interna;",
    "Entregue com Carregador;",
    "Devolvido com Carregador;",
    "Em Virtude do Desligamento de: ;",
    "Em Virtude da Substituição do: ;",
    "Será Utilizado com: ;",
    "Projeto: ;",
    "Regularização;",
    "2ª Tela;",
    "Empréstimo até a data: ;",
]
