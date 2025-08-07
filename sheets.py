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
    Versão 3.0: Implementa uma busca direcionada e exata para produtos,
    enquanto mantém a busca por palavras-chave para outras seções.
    """
    diretrizes = ler_diretrizes()
    mensagem_lower = mensagem_do_usuario.lower()

    # --- LÓGICA DE BUSCA DE PRODUTOS (ALTA PRIORIDADE) ---
    aba_produtos_info = next((regra for regra in diretrizes if regra["nome_planilha"] == "produtos"), None)
    if aba_produtos_info:
        palavras_chave_produto = [palavra.strip() for palavra in aba_produtos_info["quando_usar"].split(',')]

        # Verifica se a mensagem é sobre produtos
        if any(chave in mensagem_lower for chave in palavras_chave_produto):
            aba_produtos = planilha.worksheet("produtos")
            todos_os_produtos = aba_produtos.get_all_records()

            # Procura pelo nome do produto exato na mensagem
            for produto_row in todos_os_produtos:
                nome_produto = produto_row["produto"].lower()
                # Se o nome do produto da planilha (ex: "produto b") estiver na mensagem do usuário
                if nome_produto in mensagem_lower:
                    print(f"Produto encontrado por correspondência exata: {produto_row}")
                    return produto_row # Retorna a linha exata do produto!

    # --- LÓGICA GENÉRICA PARA OUTRAS ABAS (FAQ, OBJEÇÕES) ---
    for regra in diretrizes:
        if regra["nome_planilha"] == "produtos":
            continue # Já cuidamos dos produtos, pule esta regra

        palavras_chave = [palavra.strip() for palavra in regra["quando_usar"].split(',')]
        if any(chave in mensagem_lower for chave in palavras_chave):
            nome_da_aba = regra["nome_planilha"]
            aba_alvo = planilha.worksheet(nome_da_aba)
            todos_os_dados = [dict(zip(lista_de_valores[0], linha)) for linha in lista_de_valores[1:]]

            # Para FAQ e Objeções, a primeira correspondência de palavra-chave ainda é uma boa abordagem
            for linha in todos_os_dados:
                valor_primeira_coluna = list(linha.values())[0].lower()
                if any(palavra in valor_primeira_coluna for palavra in mensagem_lower.split()):
                    print(f"Contexto genérico encontrado na aba '{nome_da_aba}': {linha}")
                    return linha

    print("Nenhum contexto específico encontrado.")
    return None