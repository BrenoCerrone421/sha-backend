# main.py (VERSÃO DEFINITIVA E COMPLETA - COM CLIENT TOKEN)

import os
import requests
from flask import Flask, request
import re, gspread, redis, json, uuid, sys, pytz, google.generativeai as genai
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO E CARREGAMENTO DE CHAVES SECRETAS ---
print("==============================================")
print("     INICIANDO AGENTE COMERCIAL SHA v3.0      ")
print("==============================================")

app = Flask(__name__)

# Carrega TODAS as chaves do ambiente do Render.
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
REDIS_URL = os.environ.get("REDIS_URL")
ZAPI_INSTANCE_ID = os.environ.get("ZAPI_INSTANCE_ID")
ZAPI_TOKEN = os.environ.get("ZAPI_TOKEN")
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN") # <<< CHAVE CORRIGIDA E ADICIONADA

planilha = None
memoria_cache = None
model = None

# --- 2. INICIALIZAÇÃO DOS SERVIÇOS ---
try:
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', scope)
    client = gspread.authorize(creds)
    planilha = client.open("SHA - Base de Conhecimento")
    print("✅ Conexão com Google Sheets OK.")
except Exception as e: print(f"❌ ERRO CRÍTICO Sheets: {e}", file=sys.stderr)

try:
    if REDIS_URL:
        memoria_cache = redis.from_url(REDIS_URL, decode_responses=True)
        memoria_cache.ping()
        print("✅ Conexão com Redis OK.")
except Exception as e: print(f"❌ ERRO CRÍTICO Redis: {e}", file=sys.stderr)

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        print("✅ Módulo Gemini OK.")
    except Exception as e: print(f"❌ ERRO CRÍTICO Gemini: {e}", file=sys.stderr)

# --- 3. FUNÇÕES DE LÓGICA DO AGENTE ---
def _ler_aba_como_dicionario(nome_aba):
    try:
        aba = planilha.worksheet(nome_aba)
        return aba.get_all_records()
    except Exception as e:
        print(f"ERRO ao ler a aba '{nome_aba}': {e}", file=sys.stderr)
        return []

def ler_personalidade():
    try:
        with open('personalidade.txt', 'r', encoding='utf-8') as f: return f.read().strip()
    except: return "Um agente prestativo e simpático."

def encontrar_ou_criar_cliente(id_canal, nome_social, canal):
    try:
        aba_crm = planilha.worksheet("CRM_DATA")
        todos_os_clientes = aba_crm.get_all_records()
        for cliente in todos_os_clientes:
            if cliente.get(canal) == str(id_canal):
                print(f"Cliente encontrado: {cliente.get('ID_Cliente')}")
                return cliente
        print("Cliente não encontrado. Criando novo...")
        id_cliente_novo = str(uuid.uuid4())
        novo_cliente_dados = {"ID_Cliente": id_cliente_novo, "Nome_Social": nome_social, canal: str(id_canal)}
        cabecalhos = aba_crm.row_values(1)
        nova_linha = [novo_cliente_dados.get(cabecalho, "") for cabecalho in cabecalhos]
        aba_crm.append_row(nova_linha)
        return novo_cliente_dados
    except Exception as e:
        print(f"ERRO em encontrar_ou_criar_cliente: {e}", file=sys.stderr)
        return {}
    
def carregar_historico(id_cliente):
    if not memoria_cache: return []
    try:
        historico_json = memoria_cache.get(id_cliente)
        return json.loads(historico_json) if historico_json else []
    except: return []

def salvar_historico(id_cliente, historico):
    if not memoria_cache: return
    try:
        memoria_cache.setex(id_cliente, timedelta(hours=24), json.dumps(historico))
    except Exception as e: print(f"ERRO ao salvar histórico: {e}", file=sys.stderr)

def gerar_resposta(prompt):
    if not model: return "ERRO: O modelo de IA não foi inicializado."
    try: return model.generate_content(prompt).text
    except Exception as e:
        print(f"Erro na API do Gemini: {e}", file=sys.stderr)
        return "Desculpe, meu cérebro Gemini está fora de sintonia."

# --- 4. PROCESSADOR DE MENSAGENS ---
def processar_mensagem_zapi(dados):
    try:
        if dados.get("text") and not dados.get("fromMe"):
            sender_id = dados.get("phone")
            pergunta_usuario = dados.get("text", {}).get("message")
            nome_usuario = dados.get("senderName", "Cliente WhatsApp")
            if not sender_id or not pergunta_usuario: return
            
            cliente_crm = encontrar_ou_criar_cliente(sender_id, nome_usuario, "WhatsApp")
            id_cliente_interno = cliente_crm.get('ID_Cliente')
            historico = carregar_historico(id_cliente_interno)
            historico.append({"role": "user", "content": pergunta_usuario})
            
            personalidade = ler_personalidade()
            base_conhecimento = None # Lógica de busca e fluxos virá aqui
            
            prompt_final = f"Sua personalidade é: {personalidade}. Histórico da conversa: {historico}. A última pergunta do cliente foi: \"{pergunta_usuario}\". Responda."
            resposta_ia_texto = gerar_resposta(prompt_final)
            
            historico.append({"role": "model", "content": resposta_ia_texto})
            salvar_historico(id_cliente_interno, historico)
            enviar_resposta_zapi(sender_id, resposta_ia_texto)
    except Exception as e:
        print(f"ERRO ao processar mensagem Z-API: {e}", file=sys.stderr)

# --- 5. FUNÇÃO DE ENVIO DE RESPOSTA ---
def enviar_resposta_zapi(numero_destino, texto_da_resposta):
    print(f"--- ENVIANDO RESPOSTA Z-API PARA ({numero_destino}): '{texto_da_resposta}'")
    
    url_api_zapi = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-text"
    
    payload = {"phone": numero_destino, "message": texto_da_resposta}
    
    # Cabeçalho final e correto, incluindo o Client-Token.
    headers = {
        "Content-Type": "application/json",
        "Client-Token": ZAPI_CLIENT_TOKEN
    }
    
    try:
        resposta = requests.post(url_api_zapi, json=payload, headers=headers)
        resposta.raise_for_status()
        print(f"--- SUCESSO! Resposta enviada via Z-API. Status: {resposta.json()}")
    except requests.exceptions.RequestException as e:
        print(f"❌ ERRO AO ENVIAR PELA Z-API: {e.response.text if e.response else e}", file=sys.stderr)

# --- 6. ROTA PRINCIPAL DO WEBHOOK ---
@app.route("/mensagem", methods=["GET", "POST"])
def receber_mensagem():
    if request.method == "GET":
        token_sent = request.args.get("hub.verify_token")
        return (request.args.get("hub.challenge"), 200) if token_sent == VERIFY_TOKEN else ('Token inválido', 403)

    if request.method == "POST":
        dados_entrada = request.json
        print(f"--- DADO BRUTO RECEBIDO: {json.dumps(dados_entrada, indent=2)}")
        if dados_entrada.get("instanceId"):
            processar_mensagem_zapi(dados_entrada)
        return "OK", 200

# --- 7. EXECUÇÃO LOCAL ---
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
