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

# sheets.py (Versão 6.0 - Final com Busca Proativa de Produto)

def buscar_resposta_inteligente(mensagem_do_usuario):
    """
    Versão 6.0: Lógica final. Busca proativamente por nomes de produtos na mensagem
    antes de consultar as diretrizes para outros tipos de pergunta.
    """
    mensagem_lower = mensagem_do_usuario.lower()

    # --- BUSCA PROATIVA DE PRODUTOS ---
    # O agente sempre tentará encontrar um produto primeiro.
    todos_os_produtos = _ler_aba_como_dicionario("produtos")
    if todos_os_produtos:
        melhor_produto_encontrado = None
        maior_pontuacao = 0

        for produto_row in todos_os_produtos:
            nome_produto_lower = produto_row.get("produto", "").lower()
            if not nome_produto_lower:
                continue

            palavras_no_nome_produto = set(nome_produto_lower.split())
            palavras_na_mensagem = set(mensagem_lower.split())

            palavras_em_comum = palavras_no_nome_produto.intersection(palavras_na_mensagem)

            pontuacao_atual = len(palavras_em_comum)

            if pontuacao_atual > maior_pontuacao:
                maior_pontuacao = pontuacao_atual
                melhor_produto_encontrado = produto_row

        # Se encontrarmos qualquer correspondência de produto, retornamos
        if maior_pontuacao > 0:
            print(f"Busca proativa encontrou o produto: {melhor_produto_encontrado}")
            return melhor_produto_encontrado

    # --- LÓGICA GENÉRICA PARA FAQ/OBJEÇÕES (Se nenhum produto for encontrado) ---
    diretrizes = _ler_aba_como_dicionario("diretrizes")
    for regra in diretrizes:
        palavras_chave = [palavra.strip() for palavra in regra.get("quando_usar", "").split(',')]
        if any(chave in mensagem_lower for chave in palavras_chave):
            nome_da_aba = regra["nome_planilha"]
            todos_os_dados = _ler_aba_como_dicionario(nome_da_aba)

            # Para FAQ e Objeções, a primeira correspondência é suficiente
            if todos_os_dados:
                print(f"Contexto genérico encontrado na aba '{nome_da_aba}': {todos_os_dados[0]}")
                return todos_os_dados[0]

    print("Nenhum contexto específico foi encontrado por nenhuma das lógicas.")
    return None