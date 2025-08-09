# main.py - SHA Agent (Versão Final - Arquitetura de Conhecimento)
import os
import sys
import uuid
import json
import time
import re
import requests
from datetime import timedelta, datetime
from flask import Flask, request
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import redis
import google.generativeai as genai

# ---------------------------
# 1) CONFIG / ENV
# ---------------------------
APP_NAME = "SHA - Agente Comercial"
print("="*50)
print(f"Iniciando {APP_NAME}")
print("="*50)

# ENV (Render)
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
REDIS_URL = os.environ.get("REDIS_URL")
ZAPI_INSTANCE_ID = os.environ.get("ZAPI_INSTANCE_ID")
ZAPI_TOKEN = os.environ.get("ZAPI_TOKEN")
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN")

# Globals
planilha = None
memoria_cache = None
model = None

# ---------------------------
# 2) APERTO DE MÃO DIGITAL: Conectar Google Sheets
# ---------------------------
def conectar_planilha_retries(path_service_account='service_account.json', spreadsheet_name="SHA - Base de Conhecimento", tries=3, delay=2):
    global planilha
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    for attempt in range(1, tries+1):
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name(path_service_account, scope)
            client = gspread.authorize(creds)
            planilha = client.open(spreadsheet_name)
            print("✅ Conexão com Google Sheets OK.")
            return
        except Exception as e:
            print(f"❌ ERRO Sheets (tentativa {attempt}/{tries}): {e}", file=sys.stderr)
            if attempt < tries:
                time.sleep(delay)
    print("❌ Falha crítica ao conectar com Google Sheets.", file=sys.stderr)

conectar_planilha_retries()

# ---------------------------
# 3) Inicializar Redis (cache/histórico)
# ---------------------------
def conectar_redis():
    global memoria_cache
    if not REDIS_URL:
        print("⚠️ REDIS_URL não fornecido. Histórico em memória desativado.")
        return
    try:
        memoria_cache = redis.from_url(REDIS_URL, decode_responses=True)
        memoria_cache.ping()
        print("✅ Conexão com Redis OK.")
    except Exception as e:
        memoria_cache = None
        print(f"❌ ERRO Redis: {e}", file=sys.stderr)

conectar_redis()

# ---------------------------
# 4) Inicializar Gemini (LLM)
# ---------------------------
def conectar_gemini():
    global model
    if not GEMINI_API_KEY:
        print("⚠️ GEMINI_API_KEY não fornecido. Respostas LLM desativadas.", file=sys.stderr)
        return
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        print("✅ Módulo Gemini OK.")
    except Exception as e:
        model = None
        print(f"❌ ERRO Gemini: {e}", file=sys.stderr)

conectar_gemini()

# ---------------------------
# 5) UTILIDADES / I/O com planilha
# ---------------------------
def _ler_aba_como_dicionario(nome_aba):
    try:
        aba = planilha.worksheet(nome_aba)
        return aba.get_all_records()
    except Exception as e:
        print(f"ERRO ao ler a aba '{nome_aba}': {e}", file=sys.stderr)
        return []

def _get_worksheet(nome_aba):
    try:
        return planilha.worksheet(nome_aba)
    except Exception as e:
        print(f"ERRO ao obter worksheet '{nome_aba}': {e}", file=sys.stderr)
        return None

# ---------------------------
# 6) PERSONALIDADE
# ---------------------------
def ler_personalidade():
    try:
        with open('personalidade.txt', 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        print(f"⚠️ não encontrou personalidade.txt: {e}", file=sys.stderr)
        return "Um agente prestativo e simpático."

# ---------------------------
# 7) CRM: encontrar ou criar cliente (usa número como chave única)
# ---------------------------
def encontrar_ou_criar_cliente(numero, nome_social, canal_col_name="WhatsApp"):
    """
    - Usa o número como base primária.
    - Se não existir, cria nova linha preenchendo valores vazios (ou placeholders).
    - Retorna um dicionário com os dados do cliente (inclusive ID_Cliente).
    """
    try:
        aba_crm = _get_worksheet("CRM_DATA")
        if aba_crm is None:
            return {}

        todos = aba_crm.get_all_records()
        # Busca cliente existente pela coluna do número (usar col canal_col_name)
        for cliente in todos:
            # compara strings sem espaços
            if str(cliente.get(canal_col_name, "")).strip() == str(numero).strip():
                print(f"Cliente existente encontrado: {numero}")
                return cliente

        # Criar novo cliente
        print(f"Criando novo cliente para o número {numero}")
        id_cliente = str(uuid.uuid4())
        # Montar um dicionário com as colunas da primeira linha (cabeçalho)
        cabecalhos = aba_crm.row_values(1)
        novo = {h: "" for h in cabecalhos}
        # Preencher campos básicos (ajuste conforme seus cabeçalhos reais)
        if "ID_Cliente" in novo:
            novo["ID_Cliente"] = id_cliente
        elif "ID" in novo:
            novo["ID"] = id_cliente
        else:
            # se não existir coluna de ID, adicionamos em primeira coluna
            pass

        # Preencher campos fixos (não repetitivos)
        novo["Nome_Social"] = nome_social
        novo[canal_col_name] = str(numero).strip()
        # Exemplos de campos fixos — se existirem nos cabeçalhos, serão preenchidos:
        for k, v in {
            "Email_Principal": "",
            "CPF": "",
            "Endereco": "",
            "Cidade": "",
            "Estado": ""
        }.items():
            if k in novo:
                novo[k] = v

        # Construir linha na ordem dos cabeçalhos
        nova_linha = [novo.get(h, "") for h in cabecalhos]
        aba_crm.append_row(nova_linha)
        print(f"Novo cliente criado com ID {id_cliente}")
        return novo

    except Exception as e:
        print(f"ERRO em encontrar_ou_criar_cliente: {e}", file=sys.stderr)
        return {}

# ---------------------------
# 8) Histórico em Redis
# ---------------------------
def carregar_historico(id_cliente):
    if not memoria_cache:
        return []
    try:
        historico_json = memoria_cache.get(id_cliente)
        return json.loads(historico_json) if historico_json else []
    except Exception as e:
        print(f"ERRO ao carregar histórico: {e}", file=sys.stderr)
        return []

def salvar_historico(id_cliente, historico, ttl_hours=24):
    if not memoria_cache:
        return
    try:
        memoria_cache.setex(id_cliente, timedelta(hours=ttl_hours), json.dumps(historico, ensure_ascii=False))
    except Exception as e:
        print(f"ERRO ao salvar histórico: {e}", file=sys.stderr)

# ---------------------------
# 9) Extração de dados da conversa (email, cpf, telefone adicional)
# ---------------------------
def extrair_dados_da_conversa(texto):
    encontrados = {}
    if not texto:
        return encontrados
    # Emails
    m = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", texto)
    if m:
        encontrados["Email_Principal"] = m.group()
    # CPF (formato comum)
    m = re.search(r"\d{3}\.\d{3}\.\d{3}-\d{2}", texto)
    if m:
        encontrados["CPF"] = m.group()
    # Telefone (simples)
    m = re.search(r"(?:\+55)?\s*0*\(?\d{2}\)?\s*\d{4,5}-?\d{4}", texto)
    if m:
        existentes_tel = m.group().replace(" ", "")
        encontrados["Telefone_Adicional"] = existentes_tel
    return encontrados

def atualizar_dados_cliente_por_id(id_cliente, campo, valor):
    """
    Encontra a linha onde a coluna ID_Cliente (ou ID) == id_cliente e atualiza o campo (se existir).
    """
    try:
        aba_crm = _get_worksheet("CRM_DATA")
        if not aba_crm:
            return False
        # tenta achar célula com ID_Cliente ou ID
        possible_ids = ["ID_Cliente", "ID"]
        first_col_values = aba_crm.col_values(1)
        # procurar por correspondência em toda a planilha
        cell = None
        for header_name in possible_ids:
            try:
                # procura na coluna inteira
                # gspread.find procura por string em toda a sheet; usaremos find para id exato
                cell = aba_crm.find(id_cliente)
                if cell:
                    break
            except Exception:
                cell = None
        if not cell:
            # tentar encontrar pelo número de telefone (se o id_cliente for um número)
            try:
                col_names = aba_crm.row_values(1)
                if "WhatsApp" in col_names:
                    phones = aba_crm.col_values(col_names.index("WhatsApp")+1)
                    for idx, ph in enumerate(phones, start=1):
                        if str(ph).strip() == str(id_cliente).strip():
                            cell = aba_crm.cell(idx, 1)  # linha idx
                            break
            except Exception:
                pass

        if not cell:
            print(f"⚠️ Não foi possível localizar linha para ID/telefone '{id_cliente}' ao atualizar dados.")
            return False

        headers = aba_crm.row_values(1)
        if campo not in headers:
            print(f"⚠️ Cabeçalho '{campo}' não existe na aba CRM_DATA. Ignorando atualização.")
            return False
        col_index = headers.index(campo) + 1
        aba_crm.update_cell(cell.row, col_index, valor)
        print(f"✅ Atualizado {campo} para {valor} no cliente (linha {cell.row}).")
        return True
    except Exception as e:
        print(f"ERRO atualizar_dados_cliente_por_id: {e}", file=sys.stderr)
        return False

# ---------------------------
# 10) Busca inteligente de contexto (produtos -> diretrizes -> abas relacionadas)
# ---------------------------
def buscar_resposta_inteligente(mensagem):
    """
    1) Tenta casar a mensagem com um produto na aba 'produtos' por overlap de palavras.
    2) Se não achar, testa keywords na aba 'diretrizes' para apontar qual aba buscar (faq, objeções etc).
    3) Retorna contexto (linha inteira) ou None.
    """
    try:
        if not mensagem:
            return None
        texto = mensagem.lower()
        # 1) Produtos
        produtos = _ler_aba_como_dicionario("produtos")
        melhor = None
        melhor_score = 0
        palavras = re.findall(r"\w+", texto)
        palavras_set = set([p for p in palavras if len(p) > 2])
        for p in produtos:
            nome = str(p.get("nome", "")).lower()
            if not nome:
                continue
            nome_tokens = set(re.findall(r"\w+", nome))
            overlap = len(palavras_set & nome_tokens)
            if overlap > melhor_score:
                melhor_score = overlap
                melhor = p
        if melhor and melhor_score > 0:
            # Retornar contexto formatado sobre o produto
            return {"tipo": "produto", "linha": melhor, "score": melhor_score}

        # 2) Diretrizes -> busca por palavra-chave e indicação de aba alvo
        diretrizes = _ler_aba_como_dicionario("diretrizes")
        for d in diretrizes:
            # assumimos diretrizes tem colunas 'keyword' e 'alvo' (nome da aba)
            keywords = str(d.get("keywords", "")).lower().split(",")
            for kw in keywords:
                kw = kw.strip()
                if not kw:
                    continue
                if kw in texto:
                    alvo = d.get("alvo") or d.get("target")
                    if alvo and alvo.strip():
                        # busca na aba alvo pela melhor linha (pode ser por similaridade simples)
                        linha_alvo = _ler_aba_como_dicionario(alvo)
                        # procurar melhor correspondência por overlap de palavras na aba alvo (coluna 'pergunta' ou 'titulo')
                        best = None
                        best_score = 0
                        for row in linha_alvo:
                            candidato = " ".join([str(v) for v in row.values() if v]).lower()
                            cand_tokens = set(re.findall(r"\w+", candidato))
                            sc = len(palavras_set & cand_tokens)
                            if sc > best_score:
                                best_score = sc
                                best = row
                        if best:
                            return {"tipo": "diretriz", "linha": best, "alvo": alvo, "match_kw": kw}
                        else:
                            return {"tipo": "diretriz", "linha": None, "alvo": alvo, "match_kw": kw}
        # nada encontrado
        return None
    except Exception as e:
        print(f"ERRO buscar_resposta_inteligente: {e}", file=sys.stderr)
        return None

# ---------------------------
# 11) Gerar resposta com Gemini (super-prompt)
# ---------------------------
def gerar_resposta(prompt_text):
    if not model:
        # fallback simples
        return "Desculpe, estou com problemas para acessar o modelo de linguagem no momento."
    try:
        # chamando Gemini (exemplo simples)
        response = model.generate_content(prompt_text)
        # Dependendo da versão da sdk, ajuste
        if hasattr(response, "text"):
            return response.text
        # fallback
        return str(response)
    except Exception as e:
        print(f"ERRO gerar_resposta (Gemini): {e}", file=sys.stderr)
        return "Desculpe, meu cérebro está fora do ar agora."

# ---------------------------
# 12) Envio via Z-API
# ---------------------------
def enviar_resposta_zapi(numero_destino, texto_da_resposta):
    try:
        if not ZAPI_INSTANCE_ID or not ZAPI_TOKEN:
            print("⚠️ Z-API não configurada. Não será enviado mensagem.")
            return False

        url_api_zapi = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-text"
        payload = {"phone": numero_destino, "message": texto_da_resposta}
        headers = {"Content-Type": "application/json"}
        # se tiver client token, prefere usá-lo (conforme doc)
        if ZAPI_CLIENT_TOKEN:
            headers["Client-Token"] = ZAPI_CLIENT_TOKEN

        resp = requests.post(url_api_zapi, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        try:
            print(f"✅ Enviado -> Z-API: {resp.json()}")
        except Exception:
            print(f"✅ Enviado -> Z-API (status {resp.status_code})")
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ ERRO ao enviar pela Z-API: {getattr(e, 'response', str(e))}", file=sys.stderr)
        return False

# ---------------------------
# 13) Processor: pipeline principal que implementa a dissertação SHA
# ---------------------------
def processar_mensagem_zapi(dados):
    """
    Pipeline:
    1) Ignora mensagens fromMe
    2) Identifica numero, nome e texto (conforme payload Z-API real)
    3) Encontrar ou criar cliente no CRM_DATA
    4) Ler personalidade
    5) Buscar contexto (produtos/diretrizes)
    6) Extrair dados e atualizar CRM
    7) Montar super-prompt e gerar resposta
    8) Salvar histórico e enviar resposta
    """
    try:
        # 1) Ignorar mensagens enviadas pelo próprio número
        if dados.get("fromMe"):
            print("Mensagem fromMe -> ignorando.")
            return

        # 2) Parse do payload (adaptado ao seu log)
        sender_phone = dados.get("phone") or dados.get("connectedPhone")
        sender_name = dados.get("senderName") or dados.get("chatName") or "Cliente WhatsApp"
        # texto encontra-se em dados["text"]["message"] no seu exemplo
        pergunta_usuario = None
        if isinstance(dados.get("text"), dict):
            pergunta_usuario = dados["text"].get("message")
        else:
            # fallback se outro formato
            pergunta_usuario = dados.get("message") or dados.get("body") or None

        if not sender_phone or not pergunta_usuario:
            print("⚠️ Sem número ou sem texto -> ignorando.")
            return

        # 3) CRM
        cliente = encontrar_ou_criar_cliente(sender_phone, sender_name, canal_col_name="WhatsApp")
        # determinar id_cliente para histórico (usar ID_Cliente ou WhatsApp)
        id_cliente_interno = cliente.get("ID_Cliente") or cliente.get("ID") or cliente.get("WhatsApp") or sender_phone

        # 4) Personalidade
        personalidade = ler_personalidade()

        # 5) Buscar contexto (produtos/diretrizes)
        contexto = buscar_resposta_inteligente(pergunta_usuario)

        # 6) Extrair dados e atualizar CRM
        encontrados = extrair_dados_da_conversa(pergunta_usuario)
        for campo, valor in encontrados.items():
            # atualiza conforme cabeçalho
            atualizar_dados_cliente_por_id(id_cliente_interno, campo, valor)

        # 7) Carregar histórico, montar prompt e gerar resposta
        historico = carregar_historico(id_cliente_interno)
        historico.append({"role": "user", "content": pergunta_usuario})

        # montar bloco de contexto:
        contexto_texto = ""
        if contexto is None:
            contexto_texto = "Sem contexto específico de produto ou diretriz."
        elif contexto.get("tipo") == "produto":
            produto = contexto.get("linha", {})
            contexto_texto = f"Produto encontrado: {json.dumps(produto, ensure_ascii=False)}"
        elif contexto.get("tipo") == "diretriz":
            contexto_texto = f"Diretriz apontada: alvo={contexto.get('alvo')} match_kw={contexto.get('match_kw')} linha={json.dumps(contexto.get('linha', {}), ensure_ascii=False)}"

        prompt_final = (
            f"Você é o Agente SHA com a seguinte personalidade:\n{personalidade}\n\n"
            f"Dados do cliente (nome / telefone): {sender_name} / {sender_phone}\n"
            f"Contexto recolhido: {contexto_texto}\n"
            f"Histórico resumido: {json.dumps(historico[-10:], ensure_ascii=False)}\n\n"
            f"Pergunta do cliente: \"{pergunta_usuario}\"\n\n"
            "Responda de forma profissional, seguindo as diretrizes da planilha (se houver)."
        )

        resposta_ia_texto = gerar_resposta(prompt_final)
        historico.append({"role": "model", "content": resposta_ia_texto})
        salvar_historico(id_cliente_interno, historico)

        # 8) Envio via Z-API
        enviado = enviar_resposta_zapi(sender_phone, resposta_ia_texto)
        if not enviado:
            # fallback: log
            print("⚠️ Falha ao enviar resposta via Z-API; manter resposta no log/histórico.")
        return

    except Exception as e:
        print(f"ERRO ao processar mensagem Z-API: {e}", file=sys.stderr)
        return

# ---------------------------
# 14) Flask Webhook (recebe do Z-API)
# ---------------------------
from flask import Flask, request
app = Flask(__name__)

@app.route("/", methods=["GET"])
def raiz():
    return f"{APP_NAME} ativo", 200

@app.route("/mensagem", methods=["GET", "POST"])
def receber_mensagem():
    # validação GET (opcional)
    if request.method == "GET":
        token_sent = request.args.get("hub.verify_token")
        return (request.args.get("hub.challenge"), 200) if token_sent == VERIFY_TOKEN else ('Token inválido', 403)

    # POST - payload da Z-API
    data = request.get_json(force=True, silent=True)
    print(f"--- DADO BRUTO RECEBIDO: {json.dumps(data, ensure_ascii=False, indent=2)}")
    if not data:
        return "Sem payload", 200

    # Processa somente se for uma notificação de mensagem
    # Ex.: a Z-API envia campos como instanceId, phone, text:{message: "..."}
    if data.get("instanceId"):
        processar_mensagem_zapi(data)
        return "OK", 200

    # outros tipos de payload podem ser logados
    print("Payload ignorado (sem instanceId).")
    return "Ignorado", 200

# ---------------------------
# 15) RUN
# ---------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
    print(f"Rodando em 0.0.0.0:{port} (debug={debug})")
    app.run(host="0.0.0.0", port=port, debug=debug)
