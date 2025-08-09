# main.py (VERSÃO FINAL - Z-API + META)
import os
import requests
from flask import Flask, request
# ... (todos os outros imports que já tínhamos)
import json, uuid, re, pytz, gspread, redis, google.generativeai as genai
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

# --- INICIALIZAÇÃO E CHAVES SECRETAS ---
app = Flask(__name__)
# Chaves da Meta
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
# Chaves do Gemini
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
# Chaves do Redis
REDIS_URL = os.environ.get("REDIS_URL")
# Chaves da Z-API
ZAPI_INSTANCE_ID = os.environ.get("ZAPI_INSTANCE_ID")
ZAPI_TOKEN = os.environ.get("ZAPI_TOKEN")
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN") # Opcional, mas bom ter

# --- INICIALIZAÇÃO DOS MÓDULOS ---
# (Todo o código de inicialização do Sheets, Redis, Gemini que já tínhamos)
planilha = None
memoria_cache = None
model = None
try:
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', scope)
    client = gspread.authorize(creds)
    planilha = client.open("SHA - Base de Conhecimento")
    print("Conexão com Google Sheets OK.")
except Exception as e: print(f"ERRO Sheets: {e}")
try:
    if REDIS_URL:
        memoria_cache = redis.from_url(REDIS_URL, decode_responses=True)
        memoria_cache.ping()
        print("Conexão com Redis OK.")
except Exception as e: print(f"ERRO Redis: {e}")
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        print("Módulo Gemini OK.")
    except Exception as e: print(f"ERRO Gemini: {e}")

# (Todas as nossas funções de lógica que já criamos antes)
# _ler_aba_como_dicionario, ler_personalidade, encontrar_ou_criar_cliente,
# atualizar_dados_cliente, buscar_resposta_inteligente, extrair_dados_da_conversa,
# carregar_historico, salvar_historico, gerar_resposta

# --- ROTA PRINCIPAL DO WEBHOOK (O ROTEADOR) ---
@app.route("/mensagem", methods=["GET", "POST"])
def receber_mensagem():
    if request.method == "GET": # Verificação da Meta
        token_sent = request.args.get("hub.verify_token")
        return (request.args.get("hub.challenge"), 200) if token_sent == VERIFY_TOKEN else ('Token inválido', 403)

    if request.method == "POST":
        dados_entrada = request.json
        print(f"--- DADO BRUTO RECEBIDO: {dados_entrada}")

        # ROTEADOR: Detecta se a mensagem veio da Z-API ou da Meta
        if dados_entrada.get("instanceId"):
            print(">>> Mensagem da Z-API (WhatsApp) detectada.")
            processar_mensagem_zapi(dados_entrada)
        elif dados_entrada.get("object") in ["instagram", "page"]:
            print(">>> Mensagem da Meta (Instagram/Facebook) detectada.")
            processar_mensagem_meta(dados_entrada)
        else:
            print(f"AVISO: Webhook não reconhecido.")

        return "OK", 200

# --- PROCESSADOR DE MENSAGENS DA Z-API (WHATSAPP) ---
def processar_mensagem_zapi(dados):
    try:
        # Extrai os dados importantes do JSON da Z-API
        if dados.get("text"):
            sender_id = dados.get("phone")
            pergunta_usuario = dados.get("text", {}).get("message")
            nome_usuario = dados.get("senderName", "Cliente WhatsApp")

            if not sender_id or not pergunta_usuario: return

            # Lógica de CRM, Memória e IA (a mesma que já temos!)
            cliente_crm = encontrar_ou_criar_cliente(sender_id, nome_usuario, "WhatsApp")
            id_cliente_interno = cliente_crm.get('ID_Cliente')
            historico = carregar_historico(id_cliente_interno)
            historico.append({"role": "user", "content": pergunta_usuario})
            # ... (resto da lógica: busca, extração de dados, prompt, etc.)
            resposta_ia_texto = "Olá do Agente SHA no WhatsApp!" # Resposta de teste

            # Salva o histórico e envia a resposta
            historico.append({"role": "model", "content": resposta_ia_texto})
            salvar_historico(id_cliente_interno, historico)
            enviar_resposta_zapi(sender_id, resposta_ia_texto)
    except Exception as e:
        print(f"ERRO ao processar mensagem Z-API: {e}")

# --- PROCESSADOR DE MENSAGENS DA META (INSTAGRAM/FACEBOOK) ---
def processar_mensagem_meta(dados):
    # Aqui entra a mesma lógica que já tínhamos para o Instagram
    pass # Por enquanto, focamos no WhatsApp

# --- FUNÇÃO DE ENVIO DE RESPOSTA PELA Z-API ---
def enviar_resposta_zapi(numero_destino, texto_da_resposta):
    print(f"--- ENVIANDO RESPOSTA Z-API PARA ({numero_destino}): '{texto_da_resposta}'")
    url_api_zapi = f"https://api.z-api.io/v2/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-text"
    payload = {"phone": numero_destino, "message": texto_da_resposta}
    headers = {"Content-Type": "application/json", "Client-Token": ZAPI_CLIENT_TOKEN}

    try:
        resposta = requests.post(url_api_zapi, json=payload, headers=headers)
        resposta.raise_for_status()
        print(f"--- STATUS DA RESPOSTA DA Z-API: {resposta.json()}")
    except requests.exceptions.RequestException as e:
        print(f"ERRO ao enviar para API da Z-API: {e.response.text if e.response else e}")

# ... (cole aqui a função `enviar_resposta` da Meta que já tínhamos) ...
# ... (cole aqui TODAS as outras funções que estavam no main.py "Tudo em Um") ...
