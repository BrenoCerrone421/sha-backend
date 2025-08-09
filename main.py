# main.py (VERSÃO DE DIAGNÓSTICO - CORRIGIDA)

import os
import requests
from flask import Flask, request, jsonify
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
planilha = None
memoria_cache = None
model = None

# --- MÓDULO DO GOOGLE SHEETS ---
try:
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', scope)
    client = gspread.authorize(creds)
    planilha = client.open("SHA - Base de Conhecimento")
except Exception as e:
    print(f"ERRO NA INICIALIZAÇÃO DO GOOGLE SHEETS: {e}", file=sys.stderr)

# --- MÓDULO DE MEMÓRIA (REDIS) ---
try:
    if REDIS_URL:
        memoria_cache = redis.from_url(REDIS_URL, decode_responses=True)
        memoria_cache.ping()
except Exception as e:
    print(f"ERRO NA INICIALIZAÇÃO DO REDIS: {e}", file=sys.stderr)

# --- MÓDULO DA IA (GEMINI) ---
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        print(f"ERRO NA INICIALIZAÇÃO DO GEMINI: {e}", file=sys.stderr)

# --- DEFINIÇÃO DE TODAS AS FUNÇÕES ---
# (Todas as nossas funções que já criamos antes)
def _ler_aba_como_dicionario(nome_aba):
    # ... (código que já tínhamos)
    pass
# ... cole aqui TODAS as outras funções que tínhamos no main.py "Tudo em Um" ...
# (ler_personalidade, encontrar_ou_criar_cliente, atualizar_dados_cliente,
# buscar_resposta_inteligente, gerar_resposta, extrair_dados_da_conversa,
# carregar_historico, salvar_historico, enviar_resposta)

# --- ROTA PRINCIPAL DO WEBHOOK ---
@app.route("/mensagem", methods=["GET", "POST"])
def receber_mensagem():
    # ... (código do webhook que já tínhamos) ...
    return "Message processed", 200

# --- FUNÇÃO DE DIAGNÓSTICO ---
def run_diagnostic_checks():
    print("\n\n--- INICIANDO VERIFICAÇÃO DE DIAGNÓSTICO ---\n")
    # Check 1: Variáveis de Ambiente
    print("1. Verificando Variáveis de Ambiente...")
    chaves_ok = True
    keys_to_check = ["GEMINI_API_KEY", "PAGE_ACCESS_TOKEN", "VERIFY_TOKEN", "REDIS_URL"]
    for key in keys_to_check:
        if not os.environ.get(key):
            print(f"  ❌ FALHA: Variável de ambiente '{key}' não foi encontrada.")
            chaves_ok = False
    if chaves_ok: print("  ✅ SUCESSO: Todas as variáveis de ambiente foram carregadas.")
    print("-" * 40)
    # Check 2: Conexão com Google Sheets
    print("2. Verificando Conexão com Google Sheets...")
    if planilha:
        try:
            planilha.worksheet("diretrizes")
            print("  ✅ SUCESSO: Conexão com a planilha 'SHA - Base de Conhecimento' está OK.")
        except Exception as e:
            print(f"  ❌ FALHA: Conectado ao Google, mas não foi possível ler a planilha. Erro: {e}")
    else:
        print("  ❌ FALHA: A conexão inicial com o Google Sheets falhou.")
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

# --- EXECUÇÃO DO DIAGNÓSTICO E INICIALIZAÇÃO ---
# Colocamos o diagnóstico aqui, FORA do if __name__ == "__main__",
# para que ele rode quando o Render/Gunicorn iniciar o app.
run_diagnostic_checks()

print("\nServidor Flask pronto e aguardando requisições...")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)

# (Lembre-se de colar as definições das funções aqui se estiver recriando o arquivo)
