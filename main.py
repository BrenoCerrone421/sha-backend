# main.py (VERSÃO DEFINITIVA E ROBUSTA)

# --- 1. IMPORTAÇÕES ---
import os
import requests
from flask import Flask, request
import re, gspread, redis, json, uuid, sys, pytz, google.generativeai as genai
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

# --- 2. CONFIGURAÇÃO E CHAVES SECRETAS ---
print("==============================================")
print("     INICIANDO AGENTE COMERCIAL SHA v1.0      ")
print("==============================================")

app = Flask(__name__)

# Carrega todas as chaves do ambiente do Render. Se alguma faltar, o log de erro inicial nos dirá.
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
REDIS_URL = os.environ.get("REDIS_URL")
ZAPI_INSTANCE_ID = os.environ.get("ZAPI_INSTANCE_ID")
ZAPI_TOKEN = os.environ.get("ZAPI_TOKEN")

# --- 3. INICIALIZAÇÃO DOS SERVIÇOS ---
planilha = None
memoria_cache = None
model = None

try:
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', scope)
    client = gspread.authorize(creds)
    planilha = client.open("SHA - Base de Conhecimento")
    print("✅ Conexão com Google Sheets estabelecida.")
except Exception as e:
    print(f"❌ ERRO CRÍTICO: Falha ao conectar com Google Sheets. Verifique o 'service_account.json'. Erro: {e}", file=sys.stderr)

try:
    if REDIS_URL:
        memoria_cache = redis.from_url(REDIS_URL, decode_responses=True)
        memoria_cache.ping()
        print("✅ Conexão com a Memória (Redis) estabelecida.")
except Exception as e:
    print(f"❌ ERRO CRÍTICO: Falha ao conectar com Redis. Verifique a REDIS_URL. Erro: {e}", file=sys.stderr)

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        print("✅ Cérebro de IA (Gemini) configurado com sucesso.")
    except Exception as e:
        print(f"❌ ERRO CRÍTICO: Falha ao configurar o Gemini. Verifique a GEMINI_API_KEY. Erro: {e}", file=sys.stderr)

# --- 4. MÓDULO DE MEMÓRIA (FUNÇÕES REDIS) ---
def carregar_historico(id_cliente):
    if not memoria_cache: return []
    try:
        historico_json = memoria_cache.get(id_cliente)
        return json.loads(historico_json) if historico_json else []
    except Exception as e:
        print(f"ERRO: Falha ao carregar histórico do Redis para o cliente {id_cliente}: {e}", file=sys.stderr)
        return []

def salvar_historico(id_cliente, historico):
    if not memoria_cache: return
    try:
        memoria_cache.setex(id_cliente, timedelta(hours=24), json.dumps(historico))
    except Exception as e:
        print(f"ERRO: Falha ao salvar histórico no Redis para o cliente {id_cliente}: {e}", file=sys.stderr)

# --- 5. MÓDULO DE CRM (FUNÇÕES GOOGLE SHEETS) ---
def encontrar_ou_criar_cliente(id_canal, nome_social, canal):
    try:
        aba_crm = planilha.worksheet("CRM_DATA")
        # get_all_records() pode ser lento, mas é mais simples. Para otimizar no futuro, usaríamos a API v4.
        todos_os_clientes = aba_crm.get_all_records()
        for cliente in todos_os_clientes:
            if cliente.get(canal) == str(id_canal):
                print(f"Cliente encontrado no CRM. ID Interno: {cliente.get('ID_Cliente')}")
                return cliente
        
        print(f"Cliente com ID de canal {id_canal} não encontrado. Criando novo registro...")
        id_cliente_novo = str(uuid.uuid4())
        novo_cliente_dados = {"ID_Cliente": id_cliente_novo, "Nome_Social": nome_social, canal: str(id_canal)}
        cabecalhos = aba_crm.row_values(1)
        nova_linha = [novo_cliente_dados.get(cabecalho, "") for cabecalho in cabecalhos]
        aba_crm.append_row(nova_linha)
        print(f"Novo cliente criado com ID Interno: {id_cliente_novo}")
        return novo_cliente_dados
    except Exception as e:
        print(f"ERRO em encontrar_ou_criar_cliente: {e}", file=sys.stderr)
        return {}

def atualizar_dados_cliente(id_cliente, novos_dados):
    try:
        aba_crm = planilha.worksheet("CRM_DATA")
        celula = aba_crm.find(id_cliente, in_column=1)
        if not celula:
            print(f"ERRO: Não foi possível encontrar a linha do cliente com ID {id_cliente} para atualizar.")
            return False
        
        cabecalhos = aba_crm.row_values(1)
        for chave, valor in novos_dados.items():
            if chave in cabecalhos:
                coluna = cabecalhos.index(chave) + 1
                aba_crm.update_cell(celula.row, coluna, valor)
                print(f"CRM do cliente {id_cliente} atualizado. Campo '{chave}' salvo.")
        return True
    except Exception as e:
        print(f"ERRO ao atualizar dados do cliente: {e}", file=sys.stderr)
        return False

# --- 6. MÓDULO DE INTELIGÊNCIA (BUSCA E GERAÇÃO DE RESPOSTA) ---
def buscar_resposta_inteligente(mensagem_do_usuario):
    # A lógica de busca que criamos. No futuro, aqui entrará a lógica de "Fluxos".
    return None

def extrair_dados_da_conversa(texto_completo):
    dados_encontrados = {}
    email = re.search(r'[\w\.-]+@[\w\.-]+', texto_completo)
    if email: dados_encontrados['Email_Principal'] = email.group(0)
    cpf = re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', texto_completo)
    if cpf: dados_encontrados['CPF_CNPJ'] = cpf.group(0)
    return dados_encontrados

def gerar_resposta(prompt):
    if not model: return "ERRO: O modelo de IA não foi inicializado. Verifique a GEMINI_API_KEY."
    try:
        return model.generate_content(prompt).text
    except Exception as e:
        print(f"ERRO na API do Gemini: {e}", file=sys.stderr)
        return "Desculpe, meu cérebro Gemini está temporariamente fora de sintonia."

# --- 7. MÓDULO DE COMUNICAÇÃO (ENVIO DE RESPOSTAS) ---
def processar_mensagem_zapi(dados):
    try:
        print(">>> [ZAPI-1] Iniciando processamento da mensagem...")
        if dados.get("text") and not dados.get("fromMe"):
            sender_id = dados.get("phone")
            pergunta_usuario = dados.get("text", {}).get("message")
            nome_usuario = dados.get("senderName", "Cliente WhatsApp")

            if not sender_id or not pergunta_usuario:
                print(">>> [ZAPI-FALHA] Remetente ou mensagem vazia. Abortando.")
                return

            print(f">>> [ZAPI-2] Mensagem de '{nome_usuario}' ({sender_id}): '{pergunta_usuario}'")
            
            # LÓGICA COMPLETA DO AGENTE
            cliente_crm = encontrar_ou_criar_cliente(sender_id, nome_usuario, "WhatsApp")
            id_cliente_interno = cliente_crm.get('ID_Cliente')
            print(f">>> [ZAPI-3] CRM OK. ID interno: {id_cliente_interno}")
            
            historico = carregar_historico(id_cliente_interno)
            historico.append({"role": "user", "content": pergunta_usuario})
            print(">>> [ZAPI-4] Memória Redis OK. Histórico carregado e atualizado.")
            
            # (A lógica de busca e fluxos virá aqui no futuro)
            personalidade = ler_personalidade()
            base_conhecimento = None 
            
            prompt_final = f"Sua personalidade é: {personalidade}. Histórico da conversa: {historico}. A última pergunta do cliente foi: \"{pergunta_usuario}\". Responda."
            print(">>> [ZAPI-5] Prompt final montado com sucesso.")

            resposta_ia_texto = gerar_resposta(prompt_final)
            print(f">>> [ZAPI-6] Resposta da IA (Gemini) recebida: '{resposta_ia_texto}'")
            
            historico.append({"role": "model", "content": resposta_ia_texto})
            salvar_historico(id_cliente_interno, historico)
            print(">>> [ZAPI-7] Histórico salvo de volta na memória Redis.")
            
            enviar_resposta_zapi(sender_id, resposta_ia_texto)
            print(">>> [ZAPI-8] Processamento concluído com sucesso.")

    except Exception as e:
        print(f"❌ ERRO GRAVE ao processar mensagem Z-API: {e}", file=sys.stderr)

def enviar_resposta_meta(recipient_id, texto_da_resposta):
    print(f"Enviando resposta para o Instagram/Facebook ({recipient_id})...")
    if not PAGE_ACCESS_TOKEN:
        print("ERRO: PAGE_ACCESS_TOKEN não configurado no ambiente.")
        return
    url = f"https://graph.facebook.com/v20.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": recipient_id}, "message": {"text": texto_da_resposta}, "messaging_type": "RESPONSE"}
    headers = {"Content-Type": "application/json"}
    try:
        resposta = requests.post(url, json=payload, headers=headers)
        resposta.raise_for_status()
        print(f"Resposta enviada com sucesso via Meta API.")
    except requests.exceptions.RequestException as e:
        print(f"❌ ERRO ao enviar para API da Meta: {e.response.text if e.response else e}", file=sys.stderr)

# --- 8. WEBHOOK (O PONTO DE ENTRADA) ---
@app.route("/mensagem", methods=["GET", "POST"])
def receber_mensagem():
    if request.method == "GET":
        token_sent = request.args.get("hub.verify_token")
        return (request.args.get("hub.challenge"), 200) if token_sent == VERIFY_TOKEN else ('Token inválido', 403)

    if request.method == "POST":
        try:
            dados_entrada = request.json
            print(f"\n--- DADO BRUTO RECEBIDO: {json.dumps(dados_entrada, indent=2)}")

            # ROTEADOR: Detecta a origem da mensagem
            if dados_entrada.get("instanceId"): # Veio da Z-API (WhatsApp)
                processar_mensagem_zapi(dados_entrada)
            elif dados_entrada.get("object") in ["instagram", "page"]: # Veio da Meta (Instagram/Facebook)
                processar_mensagem_meta(dados_entrada)
            else:
                print(f"AVISO: Webhook não reconhecido.")
        except Exception as e:
            print(f"ERRO GERAL no processamento do POST: {e}", file=sys.stderr)
        
        return "OK", 200

# --- 9. PROCESSADORES DE MENSAGEM ---
def processar_mensagem_zapi(dados):
    try:
        if dados.get("text") and not dados.get("fromMe"):
            remetente = dados.get("phone")
            mensagem = dados.get("text", {}).get("message")
            nome_remetente = dados.get("senderName", "Cliente WhatsApp")
            if not remetente or not mensagem: return

            # LÓGICA COMPLETA DO AGENTE
            cliente = encontrar_ou_criar_cliente(remetente, nome_remetente, "WhatsApp")
            id_cliente = cliente.get('ID_Cliente')
            historico = carregar_historico(id_cliente)
            historico.append({"role": "user", "content": mensagem})
            dados_extraidos = extrair_dados_da_conversa(mensagem)
            if dados_extraidos:
                atualizar_dados_cliente(id_cliente, dados_extraidos)
            
            personalidade = ler_personalidade()
            contexto = buscar_resposta_inteligente(mensagem)
            
            prompt = f"Sua personalidade é: {personalidade}. Histórico da conversa: {historico}. Dados que você tem do cliente: {cliente}. Contexto da base de conhecimento: {contexto}. A última mensagem do cliente foi: \"{mensagem}\". Responda."
            resposta_texto = gerar_resposta(prompt)
            
            historico.append({"role": "model", "content": resposta_texto})
            salvar_historico(id_cliente, historico)
            enviar_resposta_zapi(remetente, resposta_texto)
    except Exception as e:
        print(f"ERRO ao processar mensagem Z-API: {e}", file=sys.stderr)

def processar_mensagem_meta(dados):
    # Lógica similar à da Z-API, mas extraindo dados do payload da Meta
    try:
        for entry in dados.get('entry', []):
            for message in entry.get('messaging', []):
                if 'message' in message and 'text' in message['message'] and not message['message'].get('is_echo'):
                    remetente = message['sender']['id']
                    mensagem = message['message']['text']
                    
                    # Para pegar o nome, precisamos fazer uma chamada extra à API
                    url_user = f"https://graph.facebook.com/{remetente}?fields=first_name,last_name&access_token={PAGE_ACCESS_TOKEN}"
                    user_data = requests.get(url_user).json()
                    nome_remetente = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip() or "Cliente"

                    # LÓGICA COMPLETA DO AGENTE
                    cliente = encontrar_ou_criar_cliente(remetente, nome_remetente, "Instagram")
                    # ... resto da lógica (idêntica à da Z-API)
                    # ...
                    enviar_resposta_meta(remetente, "Resposta de teste do Instagram")

    except Exception as e:
        print(f"ERRO ao processar mensagem Meta: {e}", file=sys.stderr)

# --- 10. EXECUÇÃO LOCAL ---
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
