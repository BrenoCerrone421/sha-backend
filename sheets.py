# sheets.py

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Define os "escopos" ou permissões que estamos solicitando ao Google
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

# Autoriza o acesso usando nosso arquivo de credencial JSON
# Ele procura pelo arquivo 'service_account.json' nesta mesma pasta
creds = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', scope)
client = gspread.authorize(creds)

# Abre a nossa planilha "SHA - Base de Conhecimento" pelo nome
planilha = client.open("SHA - Base de Conhecimento")

# --- Funções para ler dados da planilha ---

def ler_personalidade():
    """Lê a personalidade do agente na aba 'personalidade', célula A2."""
    aba_personalidade = planilha.worksheet("personalidade")
    # .cell(2, 1) significa linha 2, coluna 1 (A2)
    return aba_personalidade.cell(2, 1).value

def ler_diretrizes():
    """Lê todas as regras da aba 'diretrizes'."""
    aba_diretrizes = planilha.worksheet("diretrizes")
    return aba_diretrizes.get_all_records()

def buscar_resposta(mensagem_do_usuario):
    """
    Busca na aba 'diretrizes' uma palavra-chave da mensagem do usuário
    para saber qual outra aba consultar.
    """
    diretrizes = ler_diretrizes()

    for regra in diretrizes:
        # Verifica se a palavra-chave da diretriz está na mensagem do usuário
        if regra["quando_usar"].lower() in mensagem_do_usuario.lower():
            nome_da_aba = regra["nome_planilha"]
            aba_alvo = planilha.worksheet(nome_da_aba)
            dados = aba_alvo.get_all_records()
            
            # Por simplicidade, este código inicial retorna a primeira linha de dados
            # da aba encontrada. Ex: O primeiro produto, a primeira FAQ, etc.
            # No futuro, isso pode ser melhorado para buscar a linha específica.
            return dados
            
    return None # Retorna None se nenhuma diretriz corresponder