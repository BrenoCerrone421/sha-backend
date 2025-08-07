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

# sheets.py (nova função de busca v2.0)

def buscar_resposta_inteligente(mensagem_do_usuario):
    """
    Versão 2.0: Busca pela MELHOR correspondência, não apenas pela primeira.
    Prioriza palavras-chave mais específicas.
    """
    diretrizes = ler_diretrizes()
    mensagem_lower = mensagem_do_usuario.lower()

    melhor_contexto = None
    maior_pontuacao = 0

    # NÍVEL 1: Encontrar a planilha correta
    for regra in diretrizes:
        palavras_chave = [palavra.strip() for palavra in regra["quando_usar"].split(',')]
        for chave in palavras_chave:
            if chave in mensagem_lower:
                # Encontramos uma aba relevante, agora vamos procurar a melhor linha.
                nome_da_aba = regra["nome_planilha"]
                aba_alvo = planilha.worksheet(nome_da_aba)
                todos_os_dados = aba_alvo.get_all_records()

                # NÍVEL 2: Encontrar a MELHOR linha dentro da planilha
                for linha in todos_os_dados:
                    valor_primeira_coluna = list(linha.values())[0].lower()

                    # Calcula uma pontuação de relevância
                    pontuacao_atual = 0
                    palavras_na_primeira_coluna = valor_primeira_coluna.split()

                    for palavra in mensagem_lower.split():
                        if palavra in palavras_na_primeira_coluna:
                            pontuacao_atual += 1 # Aumenta a pontuação para cada palavra correspondente

                    # Se esta linha for mais relevante que a anterior, salve-a
                    if pontuacao_atual > maior_pontuacao:
                        maior_pontuacao = pontuacao_atual
                        melhor_contexto = linha
                        print(f"Novo melhor contexto encontrado na aba '{nome_da_aba}': {melhor_contexto} (Pontuação: {maior_pontuacao})")

    if melhor_contexto:
        return melhor_contexto

    print("Nenhum contexto específico encontrado.")
    return None