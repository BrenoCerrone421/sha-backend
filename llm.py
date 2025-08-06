# llm.py

import requests
import json

# A URL pública do nosso serviço de LLM rodando no Fly.io
# Certifique-se de que o nome 'sha-llm' está correto
OLLAMA_URL = "https://sha-llm.fly.dev/api/generate"

def gerar_resposta(prompt):
    """
    Envia um prompt para o modelo Mistral via API do Ollama e retorna a resposta.
    """
    try:
        # Monta o corpo da requisição no formato que o Ollama espera
        payload = {
            "model": "mistral",
            "prompt": prompt,
            "stream": False  # Queremos a resposta completa de uma vez
        }
        
        # Envia a requisição POST para a nossa URL
        # O timeout é uma boa prática para não ficar esperando para sempre
        resposta = requests.post(OLLAMA_URL, json=payload, timeout=90)

        # Verifica se a requisição foi bem-sucedida (código 200)
        resposta.raise_for_status()
        
        # Extrai o conteúdo da resposta JSON e a parte específica da "response"
        return resposta.json()["response"]

    except requests.exceptions.RequestException as e:
        # Em caso de erro de conexão, timeout, etc.
        print(f"Erro ao conectar com o Ollama: {e}")
        return "Desculpe, estou com problemas para me conectar ao meu cérebro. Tente novamente em um instante."