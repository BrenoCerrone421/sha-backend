# main.py

from flask import Flask, request, jsonify
# Importamos as funções que criamos nos outros arquivos
from sheets import buscar_resposta, ler_personalidade
from llm import gerar_resposta

# Cria a aplicação web com Flask
app = Flask(__name__)

@app.route("/mensagem", methods=["POST"])
def receber_mensagem():
    """
    Esta função é o coração do agente. Ela é executada sempre que
    uma mensagem chega na URL /mensagem.
    """
    # 1. Extrai a mensagem do usuário que veio na requisição
    dados = request.json
    if not dados or "mensagem" not in dados:
        return jsonify({"erro": "Nenhuma mensagem enviada."}), 400
    
    pergunta_usuario = dados["mensagem"]
    # Adicionamos um print para vermos a mensagem chegando no terminal. Ótimo para depuração!
    print(f"--- Mensagem Recebida: '{pergunta_usuario}'")

    # 2. Busca a personalidade e a base de conhecimento na planilha
    personalidade = ler_personalidade()
    base_conhecimento = buscar_resposta(pergunta_usuario)

    # 3. Monta o prompt para a Inteligência Artificial
    # Um bom prompt é a chave para uma boa resposta!
    prompt_final = f"""
    Sua personalidade é: {personalidade}.
    O usuário te enviou a seguinte mensagem: "{pergunta_usuario}"
    Use a seguinte informação de base para formular sua resposta: "{base_conhecimento}"
    Responda apenas com base nas informações fornecidas.
    Se a informação de base for 'None' ou vazia, significa que você não encontrou um dado específico sobre a pergunta. Nesse caso, responda de forma simpática que você pode ajudar com dúvidas sobre produtos e preços.
    """
    
    print("--- Prompt Enviado para a IA ---")
    print(prompt_final)
    print("---------------------------------")

    # 4. Envia o prompt final para a LLM e obtém a resposta
    resposta_gerada = gerar_resposta(prompt_final)

    print(f"--- Resposta da IA: '{resposta_gerada}'")

    # 5. Retorna a resposta final para quem chamou a API
    return jsonify({"resposta": resposta_gerada})

# Esta parte permite que a gente execute o servidor localmente para testes
if __name__ == "__main__":
    # O comando abaixo inicia o servidor. debug=True ajuda a ver erros com mais detalhes.
    app.run(host='0.0.0.0', port=5000, debug=True)