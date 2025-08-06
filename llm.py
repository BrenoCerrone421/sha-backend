# llm.py
import os
import google.generativeai as genai

# Pega a chave da API das variáveis de ambiente que vamos configurar
api_key = os.environ.get("GEMINI_API_KEY")

# Configura a biblioteca do Google AI com a chave
genai.configure(api_key=api_key)

# Define qual modelo da família Gemini vamos usar
model = genai.GenerativeModel('gemini-1.5-flash')

def gerar_resposta(prompt):
    """
    Envia um prompt para o modelo Gemini e retorna a resposta.
    """
    # Verifica se a chave de API foi carregada. Se não, retorna um erro claro.
    if not api_key:
        return "ERRO: A chave GEMINI_API_KEY não foi configurada no ambiente."

    try:
        # Gera o conteúdo com base no prompt
        resposta = model.generate_content(prompt)
        return resposta.text
    except Exception as e:
        # Em caso de erro na API do Google
        print(f"Erro ao conectar com a API do Gemini: {e}")
        return "Desculpe, meu cérebro Gemini está temporariamente fora de sintonia. Tente novamente."