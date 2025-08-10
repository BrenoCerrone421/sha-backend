import os
import json
import requests
from flask import Flask, request
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

app = Flask(__name__)

# =========================
# Carrega personalidade
# =========================
try:
    with open("personalidade.txt", "r", encoding="utf-8") as f:
        PERSONALIDADE = f.read().strip()
except FileNotFoundError:
    PERSONALIDADE = "Você é um assistente amigável e útil."

# =========================
# Variáveis de ambiente
# =========================
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GOOGLE_CREDS_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")

# =========================
# Config Google Sheets
# =========================
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_info(json.loads(GOOGLE_CREDS_JSON), scopes=scopes)
client = gspread.authorize(creds)

SHEET_NAME = "SuaPlanilha"
crm_sheet = client.open(SHEET_NAME).worksheet("CRM_data")
interacoes_sheet = client.open(SHEET_NAME).worksheet("interações")

# =========================
# Funções auxiliares
# =========================
def get_user_profile(user_id):
    """Obtém nome e foto do perfil do usuário no Meta"""
    url = f"https://graph.facebook.com/v18.0/{user_id}"
    params = {
        "fields": "name,profile_pic",
        "access_token": PAGE_ACCESS_TOKEN
    }
    r = requests.get(url, params=params)
    if r.status_code == 200:
        return r.json()
    return {}

def send_message(recipient_id, message_text):
    """Envia mensagem via API Graph"""
    url = f"https://graph.facebook.com/v18.0/me/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    headers = {"Content-Type": "application/json"}
    requests.post(url, params={"access_token": PAGE_ACCESS_TOKEN}, headers=headers, json=payload)

def gemini_reply(user_message):
    """Gera resposta usando Gemini API com a personalidade"""
    prompt = f"{PERSONALIDADE}\nUsuário: {user_message}\nResposta:"
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    body = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    r = requests.post(url, headers=headers, json=body)
    try:
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except:
        return "Desculpe, tive um problema ao processar sua mensagem."

def registrar_crm(sender_id, nome="", telefone="", email="", foto=""):
    """Adiciona ou atualiza dados no CRM"""
    registros = crm_sheet.get_all_records()
    existente = next((r for r in registros if str(r.get("ID_Cliente")) == str(sender_id)), None)
    if not existente:
        crm_sheet.append_row([
            sender_id, nome, "", "", "", "", "", "", "", email,
            telefone, telefone, "", "", "", "", "", foto
        ])

def registrar_interacao(sender_id, canal, resumo):
    """Salva interação na planilha"""
    interacoes_sheet.append_row([
        f"INT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        sender_id,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        canal,
        resumo
    ])

# =========================
# Rotas
# =========================
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    """Valida Webhook com Meta"""
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Erro de verificação", 403

@app.route("/webhook", methods=["POST"])
def handle_webhook():
    """Recebe mensagens do Messenger/Instagram"""
    data = request.json
    if data.get("entry"):
        for entry in data["entry"]:
            # Messenger/Instagram events
            if "messaging" in entry:
                for event in entry["messaging"]:
                    sender_id = event["sender"]["id"]

                    if "message" in event and "text" in event["message"]:
                        user_message = event["message"]["text"]

                        # Coleta dados do perfil
                        perfil = get_user_profile(sender_id)
                        nome = perfil.get("name", "Desconhecido")
                        foto = perfil.get("profile_pic", "")

                        # Gera resposta com Gemini
                        resposta = gemini_reply(user_message)

                        # Envia resposta
                        send_message(sender_id, resposta)

                        # Registra no Sheets
                        registrar_crm(sender_id, nome=nome, foto=foto)
                        registrar_interacao(sender_id, "Messenger/Instagram", user_message)

    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
