# sheets.py (Versão 4.0 - Final)

import gspread
from oauth2client.service_account import ServiceAccountCredentials
import sys # Usado para imprimir erros

# --- CONFIGURAÇÃO DA CONEXÃO ---
# Esta seção tenta se conectar ao Google Sheets. Se falhar, o programa não inicia.
try:
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', scope)
    client = gspread.authorize(creds)
    planilha = client.open("SHA - Base de Conhecimento")
    print("Conexão com Google Sheets estabelecida com sucesso.")
except FileNotFoundError:
    print("ERRO CRÍTICO: O arquivo 'service_account.json' não foi encontrado.", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"ERRO CRÍTICO ao conectar com Google Sheets: {e}", file=sys.stderr)
    sys.exit(1)

# --- FUNÇÕES DE LEITURA DE DADOS ---

def _ler_aba_como_dicionario(nome_aba):
    """
    Função auxiliar robusta para ler qualquer aba e convertê-la em uma lista de dicionários.
    Retorna uma lista vazia em caso de erro.
    """
    try:
        aba = planilha.worksheet(nome_aba)
        lista_de_valores = aba.get_all_values()
        if not lista_de_valores or len(lista_de_valores) < 2:
            return [] # Retorna vazio se a planilha tiver menos de 2 linhas (cabeçalho + dado)
        
        cabecalho = lista_de_valores[0]
        dados = [dict(zip(cabecalho, linha)) for linha in lista_de_valores[1:]]
        return dados
    except gspread.exceptions.WorksheetNotFound:
        print(f"AVISO: A aba '{nome_aba}' não foi encontrada na planilha.", file=sys.stderr)
        return []
    except Exception as e:
        print(f"ERRO ao ler a aba '{nome_aba}': {e}", file=sys.stderr)
        return []

def ler_personalidade():
    """Lê a personalidade do agente na aba 'personalidade'."""
    try:
        aba_personalidade = planilha.worksheet("personalidade")
        return aba_personalidade.cell(2, 1).value
    except Exception as e:
        print(f"ERRO ao ler a personalidade: {e}", file=sys.stderr)
        return "Um agente prestativo e simpático." # Retorna uma personalidade padrão em caso de erro

# sheets.py (nova função de busca v5.0)

def buscar_resposta_inteligente(mensagem_do_usuario):
    """
    Versão 5.0: Lógica de busca final. Procura por palavras inteiras e ignora
    palavras comuns para evitar correspondências falsas.
    """
    diretrizes = _ler_aba_como_dicionario("diretrizes")
    mensagem_lower = mensagem_do_usuario.lower()

    # Palavras comuns a serem ignoradas na busca para evitar ruído
    palavras_ignoradas = {'a', 'o', 'e', 'de', 'do', 'da', 'para', 'com', 'um', 'uma', 'qual', 'quais', 'como', 'voce', 'tem'}

    # --- LÓGICA DE BUSCA DE PRODUTOS (ALTA PRIORIDADE) ---
    aba_produtos_info = next((regra for regra in diretrizes if regra.get("nome_planilha") == "produtos"), None)
    if aba_produtos_info:
        palavras_chave_produto = [palavra.strip() for palavra in aba_produtos_info.get("quando_usar", "").split(',')]
        if any(chave in mensagem_lower for chave in palavras_chave_produto):
            todos_os_produtos = _ler_aba_como_dicionario("produtos")

            # Procura pelo nome do produto que melhor corresponde, ignorando palavras curtas
            melhor_produto = None
            maior_correspondencia = 0

            for produto_row in todos_os_produtos:
                nome_produto = produto_row.get("produto", "").lower()
                palavras_do_nome_produto = set(nome_produto.split()) - palavras_ignoradas

                # Conta quantas palavras importantes do nome do produto estão na mensagem
                correspondencia_atual = len([palavra for palavra in palavras_do_nome_produto if palavra in mensagem_lower])

                if correspondencia_atual > maior_correspondencia:
                    maior_correspondencia = correspondencia_atual
                    melhor_produto = produto_row

            if melhor_produto:
                print(f"Produto encontrado pela melhor correspondência: {melhor_produto}")
                return melhor_produto

    # --- LÓGICA GENÉRICA PARA OUTRAS ABAS (FAQ, OBJEÇÕES) ---
    # (Esta parte pode continuar como estava, pois funciona bem para frases)
    for regra in diretrizes:
        if regra.get("nome_planilha") == "produtos":
            continue
        palavras_chave = [palavra.strip() for palavra in regra.get("quando_usar", "").split(',')]
        if any(chave in mensagem_lower for chave in palavras_chave):
            nome_da_aba = regra["nome_planilha"]
            todos_os_dados = _ler_aba_como_dicionario(nome_da_aba)
            for linha in todos_os_dados:
                valor_primeira_coluna = list(linha.values())[0].lower()
                if any(palavra in valor_primeira_coluna for palavra in mensagem_lower.split() if palavra not in palavras_ignoradas):
                    print(f"Contexto genérico encontrado na aba '{nome_da_aba}': {linha}")
                    return linha

    return None

# --- NOVA FUNÇÃO RELEVANTE ---

def listar_todos_produtos():
    """
    Nova função: Retorna uma lista com o nome de todos os produtos do catálogo.
    Útil para responder "o que vocês vendem?".
    """
    todos_os_produtos = _ler_aba_como_dicionario("produtos")
    if not todos_os_produtos:
        return "Parece que nosso catálogo de produtos está vazio no momento."
    
    # Extrai apenas os nomes dos produtos da lista de dicionários
    nomes_dos_produtos = [produto.get("produto", "Produto sem nome") for produto in todos_os_produtos]
    
    # Formata a lista para uma string amigável
    return "Aqui estão nossos produtos: " + ", ".join(nomes_dos_produtos) + "."