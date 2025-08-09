# main.py (VERSÃO DE DIAGNÓSTICO)

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

print("==============================================")
print("  INICIANDO AGENTE SHA - MODO DE DIAGNÓSTICO  ")
print("==============================================")

# --- INICIALIZAÇÃO E CHAVES SECRETAS ---
app = Flask(__name__)
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
REDIS_URL = os.environ.get("REDIS_URL")

# --- MÓDULOS (O código completo do agente) ---
# (Colamos todo o nosso código aqui para que ele esteja pronto para rodar após o diagnóstico)

# MÓDULO DE MEMÓRIA (REDIS)
memoria_cache = None
try:
    if REDIS_URL:
        memoria_cache = redis.from_url(REDIS_URL, decode_responses=True)
        memoria_cache.ping()
except Exception as e:
    print(f"ERRO NA INICIALIZAÇÃO DO REDIS: {e}", file=sys.stderr)
    memoria_cache = None

# MÓDULO DO GOOGLE SHEETS
planilha = None
try:
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', scope)
    client = gspread.authorize(creds)
    planilha = client.open("SHA - Base de Conhecimento")
except Exception as e:
    print(f"ERRO NA INICIALIZAÇÃO DO GOOGLE SHEETS: {e}", file=sys.stderr)
    planilha = None

# MÓDULO DA IA (GEMINI)
model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        print(f"ERRO NA INICIALIZAÇÃO DO GEMINI: {e}", file=sys.stderr)
        model = None

# (Todas as nossas funções que já criamos)
def carregar_historico(id_cliente):
    # ... (código que já tínhamos)
    pass
def salvar_historico(id_cliente, historico):
    # ... (código que já tínhamos)
    pass
def encontrar_ou_criar_cliente(id_canal, nome, canal):
    # ... (código que já tínhamos)
    pass
# ... e assim por diante para todas as outras funções ...

# --- ROTA PRINCIPAL DO WEBHOOK ---
@app.route("/mensagem", methods=["GET", "POST"])
def receber_mensagem():
    # ... (código do webhook que já tínhamos) ...
    return "Message processed", 200

# --- FUNÇÃO DE DIAGNÓSTICO ---
def run_diagnostic_checks():
    """
    Executa uma série de testes de conexão no momento da inicialização
    e imprime os resultados nos logs.
    """
    print("\n\n--- INICIANDO VERIFICAÇÃO DE DIAGNÓSTICO ---\n")
    
    # Check 1: Variáveis de Ambiente
    print("1. Verificando Variáveis de Ambiente...")
    chaves_ok = True
    keys_to_check = ["GEMINI_API_KEY", "PAGE_ACCESS_TOKEN", "VERIFY_TOKEN", "REDIS_URL"]
    for key in keys_to_check:
        if not os.environ.get(key):
            print(f"  ❌ FALHA: Variável de ambiente '{key}' não foi encontrada.")
            chaves_ok = False
    if chaves_ok:
        print("  ✅ SUCESSO: Todas as variáveis de ambiente foram carregadas.")
    print("-" * 40)

    # Check 2: Conexão com Google Sheets
    print("2. Verificando Conexão com Google Sheets...")
    if planilha:
        try:
            planilha.worksheet("diretrizes") # Tenta acessar uma aba para confirmar a conexão
            print("  ✅ SUCESSO: Conexão com a planilha 'SHA - Base de Conhecimento' está OK.")
        except Exception as e:
            print(f"  ❌ FALHA: Conectado ao Google, mas não foi possível ler a planilha. Erro: {e}")
    else:
        print("  ❌ FALHA: A conexão inicial com o Google Sheets falhou. Verifique o 'service_account.json'.")
    print("-" * 40)

    # Check 3: Conexão com Redis
    print("3. Verificando Conexão com a Memória (Redis)...")
    if memoria_cache:
        print("  ✅ SUCESSO: Conexão com o servidor Redis está OK.")
    else:
        print("  ❌ FALHA: A conexão com o Redis falhou. Verifique a REDIS_URL.")
    print("-" * 40)

    # Check 4: Verificação do Token da Meta (Page Access Token)
    print("4. Verificando Token de Acesso da Página da Meta...")
    if PAGE_ACCESS_TOKEN:
        try:
            url_teste_meta = f"https://graph.facebook.com/v20.0/me/messenger_profile?access_token={PAGE_ACCESS_TOKEN}"
            resposta = requests.get(url_teste_meta, timeout=10)
            if resposta.status_code == 200:
                print("  ✅ SUCESSO: O Page Access Token é válido e a API da Meta respondeu.")
            else:
                print(f"  ❌ FALHA: O Page Access Token parece ser inválido. A Meta respondeu com erro: {resposta.json()}")
        except Exception as e:
            print(f"  ❌ FALHA: Erro de rede ao tentar validar o token com a Meta. Erro: {e}")
    else:
        print("  ❌ FALHA: A variável PAGE_ACCESS_TOKEN não está configurada.")
    print("\n--- VERIFICAÇÃO DE DIAGNÓSTICO CONCLUÍDA ---\n")


# --- INICIA O SERVIDOR ---
if __name__ == "__main__":
    # Roda o diagnóstico primeiro
    run_diagnostic_checks()
    # Depois, inicia o servidor web
    app.run(host='0.0.0.0', port=5000)

# (Aqui abaixo, cole TODAS as funções que já tínhamos, para que o app possa rodar normalmente depois do diagnóstico)
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
# ... E assim por diante, cole todas as outras funções aqui:
# encontrar_ou_criar_cliente, atualizar_dados_cliente, buscar_resposta_inteligente, gerar_resposta, extrair_dados_da_conversa, enviar_resposta
