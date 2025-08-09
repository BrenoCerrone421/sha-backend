# main_teste.py - Agente de Teste Simples
import os
from flask import Flask, request

app = Flask(__name__)
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")

@app.route("/mensagem", methods=["GET", "POST"])
def receber_mensagem():
    # Lógica de verificação para o GET (continua a mesma)
    if request.method == "GET":
        token_sent = request.args.get("hub.verify_token")
        if token_sent == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
        return 'Invalid verification token', 403

    # Lógica de recebimento para o POST (super simplificada)
    if request.method == "POST":
        # Pega os dados brutos que chegam
        dados_brutos = request.get_data(as_text=True)

        # O LOG MAIS IMPORTANTE DE TODOS:
        # Se a mensagem da Meta chegar, isto vai aparecer no log do Render.
        print("=================================")
        print("!!! MENSAGEM RECEBIDA DA META !!!")
        print("=================================")
        print(dados_brutos)
        print("=================================")

        # Apenas responde OK para a Meta
        return "OK", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
