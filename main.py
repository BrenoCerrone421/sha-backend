# main.py (Versão Final v2.0 - Com Anotação no CRM)

import os
import requests
from flask import Flask, request
import re # Importamos a biblioteca de expressões regulares

# Nossos módulos
from sheets import (
    ler_personalidade,
    buscar_resposta_inteligente,
    encontrar_ou_criar_cliente,
    atualizar_dados_cliente,
    registrar_interacao
)
from llm import gerar_resposta
from memoria import carregar_historico, salvar_historico

# --- INICIALIZAÇÃO E CHAVES SECRETAS ---
app = Flask(__name__)
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")

# --- FUNÇÃO AUXILIAR PARA EXTRAIR DADOS ---
def extrair_dados_da_conversa(texto_completo):
    """Usa expressões regulares para encontrar padrões de dados no texto."""
    dados_encontrados = {}
    # Encontra um email
    email = re.search(r'[\w\.-]+@[\w\.-]+', texto_completo)
    if email:
        dados_encontrados['Email_Principal'] = email.group(0)

    # Encontra um CPF (formato XXX.XXX.XXX-XX)
    cpf = re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', texto_completo)
    if cpf:
        dados_encontrados['CPF_CNPJ'] = cpf.group(0)

    # (Adicionar mais regras para telefone, CEP, etc. no futuro)
    return dados_encontrados

# --- ROTA PRINCIPAL DO WEBHOOK ---
@app.route("/mensagem", methods=["GET", "POST"])
def receber_mensagem():
    if request.method == "GET":
        token_sent = request.args.get("hub.verify_token")
        if token_sent == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
        return 'Token de verificação inválido', 403

    if request.method == "POST":
        dados_entrada = request.json
        try:
            for entry in dados_entrada.get('entry', []):
                for message in entry.get('messaging', []):
                    if 'message' in message and 'text' in message['message'] and 'is_echo' not in message['message']:
                        sender_id = message['sender']['id']
                        pergunta_usuario = message['message']['text']
                        nome_usuario = "Cliente" # Placeholder, vamos capturar o nome real no futuro

                        # --- LÓGICA DE CRM E MEMÓRIA ---
                        cliente_crm = encontrar_ou_criar_cliente(sender_id, nome_usuario, "Instagram")
                        id_cliente_interno = cliente_crm.get('ID_Cliente')
                        historico = carregar_historico(id_cliente_interno)
                        historico.append({"role": "user", "content": pergunta_usuario})

                        # --- NOVA LÓGICA DE ANOTAÇÃO ---
                        # O agente agora "ouve" a resposta do usuário por dados importantes
                        dados_extraidos = extrair_dados_da_conversa(pergunta_usuario)
                        if dados_extraidos:
                            print(f"Dados extraídos da mensagem: {dados_extraidos}")
                            atualizar_dados_cliente(id_cliente_interno, dados_extraidos)

                        # --- CÉREBRO E PROMPT ---
                        personalidade = ler_personalidade()
                        base_conhecimento = buscar_resposta_inteligente(pergunta_usuario)
                        prompt_final = f"Sua personalidade é: {personalidade}. Histórico da conversa: {historico}. Dados do cliente: {cliente_crm}. Contexto da base de conhecimento: {base_conhecimento}. A última pergunta do cliente foi: \"{pergunta_usuario}\". Continue a conversa."
                        resposta_ia_texto = gerar_resposta(prompt_final)

                        # --- ATUALIZA MEMÓRIA E ENVIA RESPOSTA ---
                        historico.append({"role": "model", "content": resposta_ia_texto})
                        salvar_historico(id_cliente_interno, historico)
                        enviar_resposta(sender_id, resposta_ia_texto)
        except Exception as e:
            print(f"ERRO ao processar a mensagem: {e}")

    return "Message processed", 200

# (A função enviar_resposta continua a mesma)
def enviar_resposta(recipient_id, texto_da_resposta):
    # ... (código existente sem alterações)
    print(f"--- ENVIANDO RESPOSTA PARA ({recipient_id}): '{texto_da_resposta}'")
    url_api_meta = f"https://graph.facebook.com/v20.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": recipient_id}, "message": {"text": texto_da_resposta}, "messaging_type": "RESPONSE"}
    headers = {"Content-Type": "application/json"}
    try:
        resposta = requests.post(url_api_meta, json=payload, headers=headers)
        resposta.raise_for_status()
        print(f"--- STATUS DA RESPOSTA DA META: {resposta.json()}")
    except requests.exceptions.RequestException as e:
        print(f"ERRO ao enviar mensagem para a API da Meta: {e}")

# --- INICIA O SERVIDOR ---
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)