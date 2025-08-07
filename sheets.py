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

def buscar_resposta_inteligente(mensagem_do_usuario):
    """
    Busca em duas etapas: primeiro encontra a aba correta usando as diretrizes,
    depois encontra a linha específica dentro daquela aba.
    """
    diretrizes = ler_diretrizes()
    palavras_na_mensagem = mensagem_do_usuario.lower().split()

    # NÍVEL 1: Encontrar a planilha correta
    for regra in diretrizes:
        palavras_chave = [palavra.strip() for palavra in regra["quando_usar"].split(',')]
        for chave in palavras_chave:
            if chave in mensagem_do_usuario.lower():
                # Encontramos a aba correta! Agora vamos procurar a linha.
                nome_da_aba = regra["nome_planilha"]
                aba_alvo = planilha.worksheet(nome_da_aba)
                todos_os_dados = aba_alvo.get_all_records()

                # NÍVEL 2: Encontrar a linha correta dentro da planilha
                for linha in todos_os_dados:
                    # Pega o valor da primeira coluna (ex: 'pergunta', 'produto', 'objeção')
                    valor_primeira_coluna = list(linha.values())[0]
                    for palavra in palavras_na_mensagem:
                        if palavra in valor_primeira_coluna.lower():
                            print(f"Contexto encontrado na aba '{nome_da_aba}': {linha}")
                            return linha # Retorna a linha exata que correspondeu!

    print("Nenhum contexto específico encontrado.")
    return None # Retorna None se nada for encontrado