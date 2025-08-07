# sheets.py (Versão CRM - Com poder de Escrita)
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import sys
import uuid # Para gerar IDs únicos
from datetime import datetime
import pytz # Para lidar com fusos horários (fuso de São Paulo)

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

# --- FUNÇÃO AUXILIAR DE LEITURA ---
def _ler_aba_como_dicionario(nome_aba):
    try:
        aba = planilha.worksheet(nome_aba)
        return aba.get_all_records()
    except Exception as e:
        print(f"ERRO ao ler a aba '{nome_aba}': {e}", file=sys.stderr)
        return []

# --- FUNÇÕES DE LEITURA (As que já tínhamos) ---
def ler_personalidade():
    try:
        with open('personalidade.txt', 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        print(f"ERRO ao ler a personalidade: {e}", file=sys.stderr)
        return "Um agente prestativo e simpático."

# (A função de busca inteligente será movida para um novo arquivo 'fluxos.py' depois, por organização)

# --- NOVAS FUNÇÕES DE ESCRITA (O Poder do CRM) ---

def encontrar_ou_criar_cliente(id_canal, nome_social_canal, canal):
    """
    Verifica se um cliente já existe com base no seu ID do canal (ex: ID do Instagram).
    Se não existir, cria uma nova linha no CRM_DATA.
    Retorna os dados do cliente (existente ou novo).
    """
    print(f"Procurando cliente com ID do canal: {id_canal}")
    aba_crm = planilha.worksheet("CRM_DATA")
    # A coluna que armazena o ID da rede social será o nome do canal (ex: "WhatsApp", "Instagram")
    todos_os_clientes = aba_crm.get_all_records()
    
    for cliente in todos_os_clientes:
        if cliente.get(canal) == id_canal:
            print("Cliente encontrado no CRM.")
            return cliente

    # Se o loop terminar e não encontrar, cria um novo cliente
    print("Cliente não encontrado. Criando novo registro no CRM...")
    id_cliente_novo = str(uuid.uuid4()) # Gera um ID único universal
    
    novo_cliente_dados = {
        "ID_Cliente": id_cliente_novo,
        "Nome_Social": nome_social_canal,
        canal: id_canal # Salva o ID do canal na coluna correta
    }

    # Pega os cabeçalhos da planilha para garantir a ordem correta
    cabecalhos = aba_crm.row_values(1)
    # Cria a linha na ordem correta, preenchendo com vazio o que não temos
    nova_linha = [novo_cliente_dados.get(cabecalho, "") for cabecalho in cabecalhos]

    aba_crm.append_row(nova_linha)
    print("Novo cliente criado com sucesso.")
    return novo_cliente_dados


def atualizar_dados_cliente(id_cliente, novos_dados):
    """
    Atualiza uma ou mais colunas para um cliente específico usando seu ID_Cliente.
    'novos_dados' deve ser um dicionário. Ex: {'Email_Principal': 'cliente@email.com'}
    """
    try:
        aba_crm = planilha.worksheet("CRM_DATA")
        # Encontra a linha que corresponde ao ID do cliente
        celula = aba_crm.find(id_cliente, in_column=1) # Procura na primeira coluna (ID_Cliente)
        if not celula:
            print(f"ERRO: Não foi possível encontrar o cliente com ID {id_cliente} para atualizar.")
            return False

        # Para cada item que queremos atualizar, encontra a coluna e atualiza a célula
        cabecalhos = aba_crm.row_values(1)
        for chave, valor in novos_dados.items():
            if chave in cabecalhos:
                coluna = cabecalhos.index(chave) + 1
                aba_crm.update_cell(celula.row, coluna, valor)
                print(f"Cliente {id_cliente} atualizado. Campo '{chave}' definido como '{valor}'.")
        return True
    except Exception as e:
        print(f"ERRO ao atualizar dados do cliente: {e}", file=sys.stderr)
        return False


def registrar_interacao(id_cliente, canal, resumo):
    """
    Adiciona uma nova linha na planilha INTERACOES.
    """
    try:
        aba_interacoes = planilha.worksheet("INTERACOES")
        id_interacao = str(uuid.uuid4())
        # Fuso horário de São Paulo
        fuso_horario_sp = pytz.timezone('America/Sao_Paulo')
        data_hora_atual = datetime.now(fuso_horario_sp).strftime("%Y-%m-%d %H:%M:%S")

        nova_linha = [id_interacao, id_cliente, data_hora_atual, canal, resumo]
        aba_interacoes.append_row(nova_linha)
        print(f"Nova interação registrada para o cliente {id_cliente}.")
        return True
    except Exception as e:
        print(f"ERRO ao registrar interação: {e}", file=sys.stderr)
        return False