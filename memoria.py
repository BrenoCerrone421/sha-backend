# memoria.py
import redis
import os
import json
from datetime import timedelta

# --- CONFIGURAÇÃO DA CONEXÃO COM O REDIS ---
try:
    # Pega a URL do Redis que configuramos no ambiente do Render
    redis_url = os.environ.get("REDIS_URL")
    # Conecta ao banco de dados de memória
    memoria_cache = redis.from_url(redis_url, decode_responses=True)
    # Testa a conexão
    memoria_cache.ping()
    print("Conexão com a memória Redis estabelecida com sucesso.")
except Exception as e:
    print(f"ERRO CRÍTICO ao conectar com Redis: {e}")
    # Se não conseguirmos conectar à memória, não há como continuar.
    memoria_cache = None

# --- FUNÇÕES DE GERENCIAMENTO DE HISTÓRICO ---

def carregar_historico(id_cliente):
    """
    Carrega o histórico de conversa de um cliente a partir do Redis.
    """
    if not memoria_cache:
        return [] # Retorna vazio se a conexão com o Redis falhou

    try:
        historico_json = memoria_cache.get(id_cliente)
        if historico_json:
            # Se encontrarmos um histórico, o convertemos de texto (JSON) para uma lista Python
            return json.loads(historico_json)
        else:
            # Se não houver histórico, é a primeira mensagem
            return []
    except Exception as e:
        print(f"ERRO ao carregar histórico para o cliente {id_cliente}: {e}")
        return []

def salvar_historico(id_cliente, historico_atualizado):
    """
    Salva o histórico atualizado de um cliente no Redis.
    """
    if not memoria_cache:
        return

    try:
        # Converte a lista Python para texto (JSON) para poder salvar no Redis
        historico_json = json.dumps(historico_atualizado)
        # Salva o histórico e define um "prazo de validade" de 24 horas.
        # Se o cliente não falar por 24h, a memória da conversa é limpa.
        memoria_cache.setex(id_cliente, timedelta(hours=24), historico_json)
    except Exception as e:
        print(f"ERRO ao salvar histórico para o cliente {id_cliente}: {e}")
