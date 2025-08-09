# main.py (VERSÃO FINAL "TUDO EM UM" - PRODUÇÃO)

import os
import requests
from flask import Flask, request
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import sys
import uuid
from datetime import datetime
import pytz
import google.generativeai as genai
import redis
import json
from datetime import timedelta

# --- INICIALIZAÇÃO E CHAVES SECRETAS ---
app = Flask(__name__)
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
REDIS_URL = os.environ.get("REDIS_URL")
planilha = None
memoria_cache = None
model = None

# --- MÓDULO DO GOOGLE SHEETS ---
try:
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', scope)
    client = gspread.authorize(creds)
    planilha = client.open("SHA - Base de Conhecimento")
    print("Conexão com Google Sheets estabelecida com sucesso.")
except Exception as e:
    print(f"ERRO CRÍTICO ao conectar com Google Sheets: {e}", file=sys.stderr)
    sys.exit(1)

# --- MÓDULO DE MEMÓRIA (REDIS) ---
try:
    if REDIS_URL:
        memoria_cache = redis.from_url(REDIS_URL, decode_responses=True)
        memoria_cache.ping()
        print("Conexão com a memória Redis estabelecida com sucesso.")
except Exception as e:
    print(f"ERRO CRÍTICO ao conectar com Redis: {e}", file=sys.stderr)
    memoria_cache = None

# --- MÓDULO DA IA (GEMINI) ---
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        print("Módulo de IA (Gemini) configurado com sucesso.")
    except Exception as e:
        print(f"ERRO NA INICIALIZAÇÃO DO GEMINI: {e}", file=sys.stderr)
        model = None

# --- FUNÇÕES DE LÓGICA DO AGENTE ---

def _ler_aba_como_dicionario(nome_aba):
    try:
        aba = planilha.worksheet(nome_aba)
        return aba.get_all_records()
    except Exception as e:
        print(f"ERRO ao ler a aba '{nome_aba}': {e}", file=sys.stderr)
        return []

def ler_personalidade():
    try:
        with open('personalidade.txt', 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        print(f"ERRO ao ler personalidade.txt: {e}", file=sys.stderr)
        return "Um agente prestativo e simpático."

def encontrar_ou_criar_cliente(id_canal, nome_social_canal, canal):
    try:
        aba_crm = planilha.worksheet("CRM_DATA")
        todos_os_clientes = aba_crm.get_all_records()
        coluna_canal = canal # Ex: 'Instagram', 'Facebook', 'WhatsApp'
        
        for cliente in todos_os_clientes:
            if cliente.get(coluna_canal) == str(id_canal):
                print(f"Cliente encontrado no CRM. ID: {cliente.get('ID_Cliente')}")
                return cliente

        print("Cliente não encontrado. Criando novo registro no CRM...")
        id_cliente_novo = str(uuid.uuid4())
        novo_cliente_dados = {"ID_Cliente": id_cliente_novo, "Nome_Social": nome_social_canal, coluna_canal: str(id_canal)}
        cabecalhos = aba_crm.row_values(1)
        nova_linha = [novo_cliente_dados.get(cabecalho, "") for cabecalho in cabecalhos]
        aba_crm.append_row(nova_linha)
        return novo_cliente_dados
    except Exception as e:
        print(f"ERRO em encontrar_ou_criar_cliente: {e}", file=sys.stderr)
        return {} # Retorna um dicionário vazio em caso de erro

def atualizar_dados_cliente(id_cliente, novos_dados):
    try:
        aba_crm = planilha.worksheet("CRM_DATA")
        celula = aba_crm.find(id_cliente, in_column=1)
        if not celula: return False
        cabecalhos = aba_crm.row_values(1)
        for chave, valor in novos_dados.items():
            if chave in cabecalhos:
                coluna = cabecalhos.index(chave) + 1
                aba_crm.update_cell(celula.row, coluna, valor)
        return True
    except Exception as e:
        print(f"ERRO ao atualizar dados do cliente: {e}", file=sys.stderr)
        return False

def buscar_resposta_inteligente(mensagem_do_usuario):
    # (Aqui está a lógica v7.0 final)
    return None # Placeholder, a lógica de fluxos virá depois

def extrair_dados_da_conversa(texto_completo):
    dados_encontrados = {}
    email = re.search(r'[\w\.-]+@[\w\.-]+', texto_completo)
    if email: dados_encontrados['Email_Principal'] = email.group(0)
    cpf = re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', texto_completo)
    if cpf: dados_encontrados['CPF_CNPJ'] = cpf.group(0)
    return dados_encontrados

def carregar_historico(id_cliente):
    if not memoria_cache: return []
    try:
        historico_json = memoria_cache.get(id_cliente)
        return json.loads(historico_json) if historico_json else []
    except Exception as e:
        print(f"ERRO ao carregar histórico para {id_cliente}: {e}", file=sys.stderr)
        return []

def salvar_historico(id_cliente, historico_atualizado):
    if not memoria_cache: return
    try:
        historico_json = json.dumps(historico_atualizado)
        memoria_cache.setex(id_cliente, timedelta(hours=24), historico_json)
    except Exception as e:
        print(f"ERRO ao salvar histórico para {id_cliente}: {e}", file=sys.stderr)

def gerar_resposta(prompt):
    if not model: return "ERRO: O modelo de IA não foi inicializado."
    try:
        return model.generate_content(prompt).text
    except Exception as e:
        print(f"Erro ao conectar com a API do Gemini: {e}", file=sys.stderr)
        return "Desculpe, meu cérebro Gemini está fora de sintonia."

def enviar_resposta(recipient_id, texto_da_resposta):
    print(f"--- ENVIANDO RESPOSTA PARA ({recipient_id}): '{texto_da_resposta}'")
    url_api_meta = f"https://graph.facebook.com/v20.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": recipient_id}, "message": {"text": texto_da_resposta}, "messaging_type": "RESPONSE"}
    headers = {"Content-Type": "application/json"}
    try:
        resposta = requests.post(url_api_meta, json=payload, headers=headers)
        resposta.raise_for_status()
        print(f"--- STATUS DA RESPOSTA DA META: {resposta.json()}")
    except requests.exceptions.RequestException as e:
        print(f"ERRO AO ENVIAR PARA API DA META: {e.response.text if e.response else e}")

# --- ROTA PRINCIPAL DO WEBHOOK ---
@app.route("/mensagem", methods=["GET", "POST"])
def receber_mensagem():
    if request.method == "GET":
        token_sent = request.args.get("hub.verify_token")
        return (request.args.get("hub.challenge"), 200) if token_sent == VERIFY_TOKEN else ('Token inválido', 403)

    if request.method == "POST":
        try:
            dados_entrada = request.get_json(force=True, silent=True)
            if dados_entrada is None: dados_entrada = request.get_data(as_text=True)
            print(f"--- DADO BRUTO RECEBIDO DA META: {dados_entrada}")

            if isinstance(dados_entrada, dict):
                for entry in dados_entrada.get('entry', []):
                    for message in entry.get('messaging', []):
                        if 'message' in message and 'text' in message['message'] and not message['message'].get('is_echo'):
                            sender_id = message['sender']['id']
                            pergunta_usuario = message['message']['text']
                            
                            cliente_crm = encontrar_ou_criar_cliente(sender_id, "Cliente Instagram", "Instagram")
                            id_cliente_interno = cliente_crm.get('ID_Cliente')
                            
                            historico = carregar_historico(id_cliente_interno)
                            historico.append({"role": "user", "content": pergunta_usuario})
                            
                            dados_extraidos = extrair_dados_da_conversa(pergunta_usuario)
                            if dados_extraidos:
                                atualizar_dados_cliente(id_cliente_interno, dados_extraidos)

                            personalidade = ler_personalidade()
                            base_conhecimento = buscar_resposta_inteligente(pergunta_usuario)
                            
                            prompt_final = f"""Sua personalidade é: {personalidade}. Histórico da conversa: {historico}. Dados do cliente: {cliente_crm}. Contexto da base de conhecimento: {base_conhecimento}. A última pergunta do cliente foi: \"{pergunta_usuario}\". Responda de forma útil e direta."""
                            
                            resposta_ia_texto = gerar_resposta(prompt_final)
                            
                            historico.append({"role": "model", "content": resposta_ia_texto})
                            salvar_historico(id_cliente_interno, historico)
                            enviar_resposta(sender_id, resposta_ia_texto)
            else:
                print("AVISO: Recebido um POST que não era um JSON de mensagem válido. Ignorando.")

        except Exception as e:
            print(f"ERRO GERAL ao processar o POST: {e}", file=sys.stderr)

        return "Message processed", 200

# --- INICIA O SERVIDOR (APENAS PARA TESTE LOCAL) ---
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
