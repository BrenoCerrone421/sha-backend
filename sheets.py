# sheets.py (Versão 7.0 - Final, com Personalidade)
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import sys

# --- CONFIGURAÇÃO DA CONEXÃO ---
try:
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', scope)
    client = gspread.authorize(creds)
    planilha = client.open("SHA - Base de Conhecimento")
    print("Conexão com Google Sheets estabelecida com sucesso.")
except Exception as e:
    print(f"ERRO CRÍTICO ao conectar com Google Sheets: {e}", file=sys.stderr)
    sys.exit(1)

# --- FUNÇÕES AUXILIARES ---
def _ler_aba_como_dicionario(nome_aba):
    try:
        aba = planilha.worksheet(nome_aba)
        lista_de_valores = aba.get_all_values()
        if not lista_de_valores or len(lista_de_valores) < 2: return []
        cabecalho = lista_de_valores[0]
        dados = [dict(zip(cabecalho, linha)) for linha in lista_de_valores[1:]]
        return dados
    except Exception as e:
        print(f"ERRO ao ler a aba '{nome_aba}': {e}", file=sys.stderr)
        return []

# --- FUNÇÕES PRINCIPAIS DE LEITURA ---
def ler_personalidade():
    try:
        return planilha.worksheet("personalidade").cell(2, 1).value
    except Exception as e:
        print(f"ERRO ao ler a personalidade: {e}", file=sys.stderr)
        return "Um agente prestativo e simpático."

def buscar_resposta_inteligente(mensagem_do_usuario):
    mensagem_lower = mensagem_do_usuario.lower()

    # --- BUSCA PROATIVA DE PRODUTOS ---
    todos_os_produtos = _ler_aba_como_dicionario("produtos")
    if todos_os_produtos:
        melhor_produto_encontrado = None
        maior_pontuacao = 0
        for produto_row in todos_os_produtos:
            nome_produto_lower = produto_row.get("produto", "").lower()
            if not nome_produto_lower: continue
            palavras_no_nome_produto = set(nome_produto_lower.split())
            palavras_na_mensagem = set(mensagem_lower.split())
            palavras_em_comum = palavras_no_nome_produto.intersection(palavras_na_mensagem)
            if len(palavras_em_comum) > maior_pontuacao:
                maior_pontuacao = len(palavras_em_comum)
                melhor_produto_encontrado = produto_row
        if maior_pontuacao > 0:
            print(f"Busca proativa encontrou o produto: {melhor_produto_encontrado}")
            return melhor_produto_encontrado

    # --- BUSCA REATIVA POR DIRETRIZES (FAQ, OBJEÇÕES, PERSONALIDADE) ---
    diretrizes = _ler_aba_como_dicionario("diretrizes")
    for regra in diretrizes:
        palavras_chave = [palavra.strip() for palavra in regra.get("quando_usar", "").split(',')]
        if any(chave in mensagem_lower for chave in palavras_chave):
            nome_da_aba = regra["nome_planilha"]
            # Caso especial: se a diretriz aponta para 'personalidade',
            # usamos a função que já temos para ler o texto.
            if nome_da_aba == 'personalidade':
                personalidade_texto = ler_personalidade()
                print(f"Contexto encontrado na aba 'personalidade'.")
                return {'contexto_personalidade': personalidade_texto}

            # Lógica padrão para outras abas como FAQ e Objeções
            todos_os_dados = _ler_aba_como_dicionario(nome_da_aba)
            for linha in todos_os_dados:
                valor_primeira_coluna = list(linha.values())[0].lower()
                if any(palavra in valor_primeira_coluna for palavra in mensagem_lower.split()):
                    print(f"Contexto genérico encontrado na aba '{nome_da_aba}': {linha}")
                    return linha

    print("Nenhum contexto específico foi encontrado.")
    return None