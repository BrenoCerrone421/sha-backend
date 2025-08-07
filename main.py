# main.py (Versão Completa - Fase 2: CRM + Memória Redis)

import os
import requests
from flask import Flask, request

# Importa as funções dos nossos outros módulos
from sheets import ler_personalidade, buscar_resposta_inteligente, encontrar_ou_criar_cliente
from llm import gerar_resposta
from memoria import carregar_historico, salvar_historico

# --- INICIALIZAÇÃO E CHAVES SECRETAS ---
app = Flask(__name__)

# Pega as chaves secretas que configuramos no ambiente do Render
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")


# --- ROTA PRINCIPAL QUE RECEBE AS MENSAGENS ---
@app.route("/mensagem", methods=["GET", "POST"])
def receber_mensagem():
    # Se a requisição for GET, é o desafio de verificação da Meta
    if request.method == "GET":
        token_sent = request.args.get("hub.verify_token")
        if token_sent == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
        return 'Token de verificação inválido', 403

    # Se a requisição for POST, é uma mensagem de um usuário
    if request.method == "POST":
        dados_entrada = request.json
        print(f"--- DADO RECEBIDO DA META: {dados_entrada}")
        try:
            for entry in dados_entrada.get('entry', []):
                for message in entry.get('messaging', []):
                    # Verifica se é uma mensagem de texto padrão
                    if 'message' in message and 'text' in message['message'] and 'is_echo' not in message['message']:
                        
                        # --- 1. EXTRAI DADOS BÁSICOS ---
                        sender_id = message['sender']['id']  # ID do usuário no Instagram/Facebook
                        pergunta_usuario = message['message']['text']
                        
                        # --- 2. LÓGICA DE CRM ---
                        # Encontra o cliente no CRM_DATA ou cria um novo registro.
                        # Por enquanto, estamos salvando na coluna "WhatsApp" como padrão.
                        cliente_crm = encontrar_ou_criar_cliente(sender_id, "Nome de Perfil Provisório", "WhatsApp")
                        id_cliente_interno = cliente_crm.get('ID_Cliente')
                        
                        # --- 3. LÓGICA DE MEMÓRIA (REDIS) ---
                        historico = carregar_historico(id_cliente_interno)
                        historico.append({"role": "user", "content": pergunta_usuario})
                        
                        # --- 4. CÉREBRO DO AGENTE (BUSCA NA BASE DE CONHECIMENTO) ---
                        personalidade = ler_personalidade()
                        base_conhecimento = buscar_resposta_inteligente(pergunta_usuario)
                        
                        # --- 5. MONTAGEM DO PROMPT PARA O GEMINI ---
                        prompt_final = f"""
                        Sua personalidade é: {personalidade}.
                        
                        Aqui está o histórico da sua conversa com o cliente: {historico}.
                        
                        Aqui estão os dados que você já sabe sobre este cliente: {cliente_crm}.
                        
                        Aqui está um contexto específico que você encontrou na sua base de conhecimento sobre a pergunta dele: {base_conhecimento}.

                        A última pergunta do cliente foi: "{pergunta_usuario}".

                        Com base em TUDO isso, continue a conversa de forma natural e útil. Se a base de conhecimento te deu uma resposta direta, use-a. Se não, use o histórico e a personalidade para responder.
                        """
                        
                        resposta_ia_texto = gerar_resposta(prompt_final)
                        
                        # --- 6. ATUALIZA A MEMÓRIA E ENVIA A RESPOSTA ---
                        historico.append({"role": "model", "content": resposta_ia_texto})
                        salvar_historico(id_cliente_interno, historico)
                        
                        enviar_resposta(sender_id, resposta_ia_texto)
        
        except Exception as e:
            print(f"ERRO ao processar a mensagem: {e}")

        # Responde 200 OK para a Meta para indicar que a mensagem foi recebida
        return "Message processed", 200


# --- FUNÇÃO PARA ENVIAR MENSAGENS DE VOLTA PARA A META ---
def enviar_resposta(recipient_id, texto_da_resposta):
    print(f"--- ENVIANDO RESPOSTA PARA ({recipient_id}): '{texto_da_resposta}'")
    url_api_meta = f"https://graph.facebook.com/v20.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": texto_da_resposta},
        "messaging_type": "RESPONSE"
    }
    headers = {"Content-Type": "application/json"}
    
    try:
        resposta = requests.post(url_api_meta, json=payload, headers=headers)
        resposta.raise_for_status() # Lança um erro se a resposta não for 200 OK
        print(f"--- STATUS DA RESPOSTA DA META: {resposta.json()}")
    except requests.exceptions.RequestException as e:
        print(f"ERRO ao enviar mensagem para a API da Meta: {e}")

# --- INICIA O SERVIDOR ---
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)