import os
import json
import time
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, request

# ================== CONFIG ==================
GOOGLE_CREDS_FILE = "google_service_account.json"  # credenciais do Google
SHEET_NAME = "SHA_CRM"  # nome da planilha no Google Sheets
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")  # token de acesso da Meta
VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN")  # usado para webhook
PERSONALIDADE_FILE = "personalidade.txt"

# ================== CARREGAR PERSONALIDADE ==================
if os.path.exists(PERSONALIDADE_FILE):
    with open(PERSONALIDADE_FILE, "r", encoding="utf-8") as f:
        PERSONALIDADE = f.read().strip()
else:
    PERSONALIDADE = "Sou SHA, seu assistente inteligente."

# ================== GOOGLE SHEETS ==================
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDS_FILE, scope)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).worksheet("CRM_data")

# ================== FUNÇÕES AUXILIARES ==================
def enviar_mensagem_whatsapp(numero, texto):
    url = f"https://graph.facebook.com/v17.0/{os.getenv('WHATSAPP_PHONE_ID')}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "text": {"body": texto}
    }
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    requests.post(url, headers=headers, json=payload)

def obter_dados_meta(user_id):
    """Pega dados do perfil no Facebook/Instagram"""
    campos = "name,profile_pic,email,phone,birthday,location"
    url = f"https://graph.facebook.com/v17.0/{user_id}?fields={campos}&access_token={META_ACCESS_TOKEN}"
    r = requests.get(url)
    if r.status_code == 200:
        return r.json()
    return {}

def salvar_no_crm(dados):
    """Salva/atualiza cliente no CRM"""
    clientes = sheet.get_all_records()
    for i, cliente in enumerate(clientes, start=2):
        if cliente["user_id"] == dados.get("user_id"):
            sheet.update(f"A{i}:F{i}", [[
                dados.get("user_id", ""),
                dados.get("nome", ""),
                dados.get("telefone", ""),
                dados.get("email", ""),
                dados.get("aniversario", ""),
                dados.get("localizacao", "")
            ]])
            return
    sheet.append_row([
        dados.get("user_id", ""),
        dados.get("nome", ""),
        dados.get("telefone", ""),
        dados.get("email", ""),
        dados.get("aniversario", ""),
        dados.get("localizacao", "")
    ])

def gerar_resposta(mensagem_usuario):
    """Responde usando a personalidade"""
    return f"{PERSONALIDADE}\n\n{mensagem_usuario}"

# ================== FLASK WEBHOOK ==================
app = Flask(__name__)

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Token inválido", 403

    data = request.get_json()
    print("📩 Recebido:", json.dumps(data, indent=2, ensure_ascii=False))

    try:
        entry = data["entry"][0]
        changes = entry.get("changes") or []
        messaging = entry.get("messaging") or []

        # Facebook/Instagram
        if changes:
            for change in changes:
                user_id = change["value"]["from"]["id"]
                mensagem = change["value"].get("message", "")
                dados_perfil = obter_dados_meta(user_id)
                salvar_no_crm({
                    "user_id": user_id,
                    "nome": dados_perfil.get("name"),
                    "telefone": dados_perfil.get("phone"),
                    "email": dados_perfil.get("email"),
                    "aniversario": dados_perfil.get("birthday"),
                    "localizacao": dados_perfil.get("location", {}).get("name")
                })
                resposta = gerar_resposta(mensagem)
                enviar_mensagem_whatsapp(user_id, resposta)

        # WhatsApp
        if messaging:
            for message in messaging:
                numero = message["sender"]["id"]
                texto = message["message"]["text"]
                dados_perfil = obter_dados_meta(numero)
                salvar_no_crm({
                    "user_id": numero,
                    "nome": dados_perfil.get("name"),
                    "telefone": dados_perfil.get("phone"),
                    "email": dados_perfil.get("email"),
                    "aniversario": dados_perfil.get("birthday"),
                    "localizacao": dados_perfil.get("location", {}).get("name")
                })
                resposta = gerar_resposta(texto)
                enviar_mensagem_whatsapp(numero, resposta)

    except Exception as e:
        print("❌ Erro no processamento:", e)

    return "ok", 200

# ================== RODAR ==================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
