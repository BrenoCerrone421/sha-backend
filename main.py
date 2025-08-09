# main.py - SHA Agent (VERSão Final Completa)
import os
import sys
import time
import uuid
import json
import re
import requests
import pytz
from datetime import datetime, timedelta
from flask import Flask, request
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import redis
import google.generativeai as genai

# -----------------------
# Config / ENV
# -----------------------
APP_NAME = "SHA - Agente Comercial (FINAL)"
print("=" * 60)
print(f"INICIANDO {APP_NAME}")
print("=" * 60)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
ZAPI_INSTANCE_ID = os.environ.get("ZAPI_INSTANCE_ID")
ZAPI_TOKEN = os.environ.get("ZAPI_TOKEN")
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
REDIS_URL = os.environ.get("REDIS_URL")
SPREADSHEET_NAME = os.environ.get("SPREADSHEET_NAME", "SHA - Base de Conhecimento")
SERVICE_ACCOUNT_FILE = os.environ.get("SERVICE_ACCOUNT_FILE", "service_account.json")
TZ = pytz.timezone("America/Sao_Paulo")

app = Flask(__name__)

# -----------------------
# Sheets: nomes esperados (várias variantes para robustez)
# -----------------------
SHEET_NAME_VARIANTS = {
    "crm": ["crm data", "crm_data", "CRM_DATA", "CRM Data", "crm data ", "crmdata"],
    "interacoes": ["interações", "interacoes", "interações ", "interacoes ", "interacoes_sheet"],
    "produtos": ["produtos", "Produtos"],
    "diretrizes": ["diretrizes", "Diretrizes"],
    "faq": ["faq", "FAQ"],
    "objecoes": ["objeções", "objecoes", "Objeções", "objecoes"],
    "personalidade": ["personalidade", "Personalidade"],
    "fluxos": ["fluxos", "Fluxos"]
}

# Cabeçalhos obrigatórios (ordem para CRM e Interações)
CRM_HEADERS = [
    "ID_Cliente",
    "Nome_Completo",
    "Nome_Social",
    "CPF_CNPJ",
    "Data_Nascimento",
    "Genero",
    "Estado_Civil",
    "Foto_Perfil",
    "RG",
    "Email_Principal",
    "Telefone_Principal",
    "WhatsApp",
    "Endereco_1",
    "CEP_1",
    "Cidade_1",
    "Estado_1",
    "Pais_1"
]

INTER_HEADERS = [
    "ID_Interacao",
    "ID_Cliente",
    "Data_Hora",
    "Canal",
    "Resumo_Conversa"
]

# Globals
planilha = None
memoria_cache = None
model = None

# -----------------------
#  Helpers para Sheets
# -----------------------
def conectar_planilha_retries(path=SERVICE_ACCOUNT_FILE, spreadsheet_name=SPREADSHEET_NAME, tries=3, delay=2):
    global planilha
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    for attempt in range(1, tries + 1):
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name(path, scope)
            client = gspread.authorize(creds)
            planilha = client.open(spreadsheet_name)
            print("✅ Conexão com Google Sheets OK.")
            return True
        except Exception as e:
            print(f"❌ ERRO Sheets (tentativa {attempt}/{tries}): {e}", file=sys.stderr)
            if attempt < tries:
                time.sleep(delay)
    print("❌ Falha ao conectar Google Sheets.", file=sys.stderr)
    return False

def find_worksheet_by_variants(variants):
    if not planilha:
        return None
    for ws in planilha.worksheets():
        title_norm = ws.title.strip().lower()
        for v in variants:
            if title_norm == v.strip().lower():
                return ws
    return None

def ensure_worksheet(name, default_headers=None, rows=1000, cols=20):
    """
    Garante que exista a worksheet com algum dos nomes variantes.
    Se não existir, cria com o título da primeira variante.
    Também garante que os headers obrigatórios existam (append se faltar).
    Retorna a worksheet (gspread Worksheet).
    """
    global planilha
    # Try to find worksheet by variants of name
    variants = SHEET_NAME_VARIANTS.get(name, [name])
    ws = find_worksheet_by_variants(variants)
    if ws:
        # ensure headers
        if default_headers:
            ensure_headers(ws, default_headers)
        return ws
    # não existe -> cria com o primeiro nome variante
    titulo = variants[0]
    try:
        ws = planilha.add_worksheet(title=titulo, rows=rows, cols=cols)
        print(f"⚠️ Worksheet '{titulo}' não existia; criada nova.")
        if default_headers:
            ws.append_row(default_headers, value_input_option='USER_ENTERED')
        return ws
    except Exception as e:
        print(f"❌ Erro ao criar worksheet '{titulo}': {e}", file=sys.stderr)
        return None

def ensure_headers(ws, required_headers):
    """
    Se a primeira linha não existir, insere required_headers.
    Se existir, adiciona quaisquer cabeçalhos faltantes (append no final).
    Retorna a lista atualizada de headers.
    """
    try:
        existing = ws.row_values(1)
    except Exception as e:
        print(f"❌ Erro ao obter headers: {e}", file=sys.stderr)
        existing = []

    if not existing:
        try:
            ws.insert_row(required_headers, index=1, value_input_option='USER_ENTERED')
            return required_headers
        except Exception as e:
            print(f"❌ Erro ao inserir headers: {e}", file=sys.stderr)
            return required_headers

    missing = [h for h in required_headers if h not in existing]
    if missing:
        new_headers = existing + missing
        try:
            # Atualiza a primeira linha com o novo header list (inicia em A1)
            ws.update('A1', [new_headers], value_input_option='USER_ENTERED')
            print(f"⚠️ Headers atualizados (colocados {len(missing)} colunas faltantes).")
            return new_headers
        except Exception as e:
            print(f"❌ Erro ao atualizar headers: {e}", file=sys.stderr)
            return existing
    return existing

def get_headers_map(ws):
    headers = ws.row_values(1)
    return {h: i+1 for i, h in enumerate(headers)}  # 1-based index

def find_row_by_value(ws, column_name, value):
    headers_map = get_headers_map(ws)
    if column_name not in headers_map:
        return None
    col_idx = headers_map[column_name]
    try:
        col_vals = ws.col_values(col_idx)  # includes header
    except Exception as e:
        print(f"❌ Erro ao ler coluna {column_name}: {e}", file=sys.stderr)
        return None
    for i, v in enumerate(col_vals, start=1):
        if str(v).strip() == str(value).strip():
            return i  # row index (1-based)
    return None

def row_to_dict(ws, row_index):
    headers = ws.row_values(1)
    try:
        row_vals = ws.row_values(row_index)
    except Exception as e:
        print(f"❌ Erro ao ler linha {row_index}: {e}", file=sys.stderr)
        row_vals = []
    d = {}
    for i, h in enumerate(headers):
        d[h] = row_vals[i] if i < len(row_vals) else ""
    d['__row'] = row_index
    return d

# -----------------------
# Conexões iniciais
# -----------------------
conectar_planilha_retries()

def conectar_redis():
    global memoria_cache
    if not REDIS_URL:
        print("⚠️ REDIS_URL não definido. Histórico temporário via Redis desativado.")
        return
    try:
        memoria_cache = redis.from_url(REDIS_URL, decode_responses=True)
        memoria_cache.ping()
        print("✅ Redis OK.")
    except Exception as e:
        memoria_cache = None
        print(f"❌ Erro Redis: {e}", file=sys.stderr)

conectar_redis()

def conectar_gemini():
    global model
    if not GEMINI_API_KEY:
        print("⚠️ GEMINI_API_KEY não definido. Gemini desativado.")
        return
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        print("✅ Gemini OK.")
    except Exception as e:
        model = None
        print(f"❌ Erro Gemini: {e}", file=sys.stderr)

conectar_gemini()

# -----------------------
# Inicializar / garantir abas
# -----------------------
ws_crm = ensure_worksheet('crm', default_headers=CRM_HEADERS)
ws_inter = ensure_worksheet('interacoes', default_headers=INTER_HEADERS)
ws_produtos = ensure_worksheet('produtos', default_headers=None)
ws_diretrizes = ensure_worksheet('diretrizes', default_headers=None)
ws_faq = ensure_worksheet('faq', default_headers=None)
ws_obje = ensure_worksheet('objecoes', default_headers=None)
ws_person = ensure_worksheet('personalidade', default_headers=None)
ws_fluxos = ensure_worksheet('fluxos', default_headers=None)

# garantir headers obrigatórios se as abas existem
if ws_crm:
    ensure_headers(ws_crm, CRM_HEADERS)
if ws_inter:
    ensure_headers(ws_inter, INTER_HEADERS)

# -----------------------
# Funções do SHA (CRM / interações)
# -----------------------
def encontrar_ou_criar_cliente(whatsapp_num, nome_social):
    """
    Procura cliente na aba CRM pela coluna 'WhatsApp'. Se existir, retorna dict com dados e __row.
    Se não existir, cria nova linha preenchendo os cabeçalhos obrigatórios na ordem CRM_HEADERS.
    """
    try:
        ws = ws_crm
        if not ws:
            print("❌ Aba CRM não disponível.")
            return {"ID_Cliente": str(uuid.uuid4()), "__row": None}

        headers = ws.row_values(1)
        headers_map = {h: i+1 for i, h in enumerate(headers)}

        # buscar por WhatsApp
        if "WhatsApp" in headers_map:
            row = find_row_by_value(ws, "WhatsApp", whatsapp_num)
            if row:
                cliente = row_to_dict(ws, row)
                # Se não tiver ID_Cliente, gera e atualiza
                if not cliente.get("ID_Cliente"):
                    cliente_id = str(uuid.uuid4())
                    cliente["ID_Cliente"] = cliente_id
                    col_index = headers_map.get("ID_Cliente")
                    if col_index:
                        try:
                            ws.update_cell(row, col_index, cliente_id)
                        except Exception as e:
                            print(f"⚠️ Erro atualizando ID_Cliente: {e}", file=sys.stderr)
                return cliente

        # se não encontrado -> criar
        novo_id = str(uuid.uuid4())
        # montar novo dict preenchendo com "" e valores básicos
        novo = {h: "" for h in headers}
        # preferir Nome_Completo ou Nome_Social conforme disponíveis
        if "Nome_Social" in novo:
            novo["Nome_Social"] = nome_social
        elif "Nome_Completo" in novo:
            novo["Nome_Completo"] = nome_social
        # preencher ID e WhatsApp se colunas existem
        if "ID_Cliente" in novo:
            novo["ID_Cliente"] = novo_id
        if "WhatsApp" in novo:
            novo["WhatsApp"] = whatsapp_num
        if "Telefone_Principal" in novo:
            novo["Telefone_Principal"] = whatsapp_num

        # construir linha no formato dos headers atuais
        nova_linha = [novo.get(h, "") for h in headers]
        try:
            ws.append_row(nova_linha, value_input_option='USER_ENTERED')
            # recuperar linha criada (última)
            last_row_index = len(ws.get_all_values())
            novo_ret = {h: nova_linha[i] if i < len(nova_linha) else "" for i, h in enumerate(headers)}
            novo_ret["__row"] = last_row_index
            print(f"✅ Novo cliente criado (linha {last_row_index}) ID {novo_id}")
            return novo_ret
        except Exception as e:
            print(f"❌ Erro ao inserir novo cliente: {e}", file=sys.stderr)
            # retornar pelo menos o objeto mínimo
            return {"ID_Cliente": novo_id, "WhatsApp": whatsapp_num, "Nome_Social": nome_social, "__row": None}

    except Exception as e:
        print(f"ERRO encontrar_ou_criar_cliente: {e}", file=sys.stderr)
        return {"ID_Cliente": str(uuid.uuid4()), "__row": None}

def atualizar_campos_cliente_por_row(row_index, campos_dict):
    """
    Atualiza as colunas especificadas na linha 'row_index' da aba CRM.
    """
    try:
        ws = ws_crm
        if not ws or not row_index:
            return False
        headers = ws.row_values(1)
        for campo, valor in campos_dict.items():
            if campo not in headers:
                # opcional: podemos adicionar a coluna faltante
                headers.append(campo)
                try:
                    ws.update('A1', [headers], value_input_option='USER_ENTERED')
                    print(f"⚠️ Cabeçalho '{campo}' criado dinamicamente.")
                except Exception as e:
                    print(f"⚠️ Falha ao criar cabeçalho '{campo}': {e}", file=sys.stderr)
            # obter índice atualizado
            headers = ws.row_values(1)
            if campo in headers:
                col_idx = headers.index(campo) + 1
                try:
                    ws.update_cell(row_index, col_idx, valor)
                except Exception as e:
                    print(f"⚠️ Erro ao atualizar célula ({row_index},{col_idx}): {e}", file=sys.stderr)
        return True
    except Exception as e:
        print(f"ERRO atualizar_campos_cliente_por_row: {e}", file=sys.stderr)
        return False

def registrar_interacao(id_cliente, resumo_conversa, canal="WhatsApp"):
    """
    Adiciona linha à aba 'interações' seguindo INTER_HEADERS.
    """
    try:
        ws = ws_inter
        if not ws:
            print("❌ Aba de interações não disponível.")
            return False
        headers = ws.row_values(1)
        # garantir headers
        ensure_headers(ws, INTER_HEADERS)
        timestamp = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
        linha = [
            str(uuid.uuid4()),
            id_cliente,
            timestamp,
            canal,
            resumo_conversa
        ]
        ws.append_row(linha, value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        print(f"ERRO registrar_interacao: {e}", file=sys.stderr)
        return False

def carregar_ultimas_interacoes(id_cliente, limit=5):
    """
    Lê aba interações e retorna as últimas 'limit' interações do cliente (mais recentes).
    """
    try:
        ws = ws_inter
        if not ws:
            return []
        records = ws.get_all_records()
        # filtrar por ID_Cliente (respeitar capitalização)
        res = [r for r in records if str(r.get("ID_Cliente","")) == str(id_cliente)]
        # ordenar por Data_Hora se possível (assumindo formato YYYY-mm-dd HH:MM:SS)
        def key_func(r):
            ts = r.get("Data_Hora")
            try:
                return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            except Exception:
                return datetime.min
        res_sorted = sorted(res, key=key_func, reverse=True)
        return res_sorted[:limit]
    except Exception as e:
        print(f"ERRO carregar_ultimas_interacoes: {e}", file=sys.stderr)
        return []

# -----------------------
# Busca Inteligente (produtos -> diretrizes -> abas alvo)
# -----------------------
def _ler_aba(nome_variantes):
    ws = None
    # nome_variantes: key in SHEET_NAME_VARIANTS
    vs = SHEET_NAME_VARIANTS.get(nome_variantes, [nome_variantes])
    ws = find_worksheet_by_variants(vs)
    if not ws:
        return []
    try:
        return ws.get_all_records()
    except Exception as e:
        print(f"ERRO ao ler aba {ws.title}: {e}", file=sys.stderr)
        return []

def buscar_resposta_inteligente(mensagem):
    """
    1) Busca por produto com maior overlap de tokens no nome/descrição.
    2) Se não achar, busca diretrizes por keywords; se encontrada, busca aba alvo indicada.
    3) Retorna dict com tipo e dados.
    """
    try:
        if not mensagem:
            return None
        texto = mensagem.lower()
        tokens = set(re.findall(r"\w+", texto))
        # 1) Produtos
        produtos = _ler_aba("produtos")
        best = None
        best_score = 0
        for p in produtos:
            # procurar campos comuns (nome, nome_produto, title)
            nome = str(p.get("nome") or p.get("Nome") or p.get("titulo") or p.get("title") or "").lower()
            descricao = str(p.get("descricao") or p.get("descrição") or p.get("descricao_produto") or "").lower()
            tokens_prod = set(re.findall(r"\w+", nome + " " + descricao))
            score = len(tokens & tokens_prod)
            if score > best_score:
                best_score = score
                best = p
        if best and best_score > 0:
            return {"tipo": "produto", "linha": best, "score": best_score}

        # 2) Diretrizes
        diretrizes = _ler_aba("diretrizes")
        for d in diretrizes:
            # assumir colunas 'keywords' e 'alvo' ou 'keywords' e 'target'
            kw_field = d.get("keywords") or d.get("palavras-chave") or d.get("palavras_chave") or d.get("palavras")
            alvo = d.get("alvo") or d.get("target") or d.get("aba_alvo") or d.get("aba")
            if not kw_field or not alvo:
                continue
            kws = [k.strip().lower() for k in re.split(r"[,\;]", str(kw_field)) if k.strip()]
            for kw in kws:
                if kw and kw in texto:
                    # ler aba alvo
                    try:
                        target_sheet = find_worksheet_by_variants([alvo])
                        if not target_sheet:
                            # tentar ler pelo nome direto
                            rows = _ler_aba(alvo)
                        else:
                            rows = target_sheet.get_all_records()
                    except Exception:
                        rows = _ler_aba(alvo)
                    # pegar a primeira linha que melhor combina
                    if rows:
                        # procurar melhor por overlap
                        best_row = None
                        best_sc = 0
                        for r in rows:
                            candidate_text = " ".join([str(v) for v in r.values() if v]).lower()
                            sc = len(tokens & set(re.findall(r"\w+", candidate_text)))
                            if sc > best_sc:
                                best_sc = sc
                                best_row = r
                        return {"tipo": "diretriz", "alvo": alvo, "match_kw": kw, "linha": best_row}
                    else:
                        return {"tipo": "diretriz", "alvo": alvo, "match_kw": kw, "linha": None}
        return None
    except Exception as e:
        print(f"ERRO buscar_resposta_inteligente: {e}", file=sys.stderr)
        return None

# -----------------------
# Extração de dados (email, cpf, telefone)
# -----------------------
def extrair_dados_da_conversa(texto):
    encontrados = {}
    if not texto:
        return encontrados
    m = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", texto)
    if m:
        encontrados["Email_Principal"] = m.group()
    m = re.search(r"\d{3}\.\d{3}\.\d{3}-\d{2}", texto)
    if m:
        encontrados["CPF_CNPJ"] = m.group()
    m = re.search(r"(?:\+55\s?)?(?:0?\(?\d{2}\)?\s?)?(?:9?\d{4}-?\d{4}|\d{4}-?\d{4})", texto)
    if m:
        encontrados["Telefone_Principal"] = re.sub(r"\s+","", m.group())
    return encontrados

# -----------------------
# Histórico (Redis)
# -----------------------
def carregar_historico(id_cliente):
    if not memoria_cache:
        return []
    try:
        h = memoria_cache.get(id_cliente)
        return json.loads(h) if h else []
    except Exception as e:
        print(f"ERRO carregar_historico: {e}", file=sys.stderr)
        return []

def salvar_historico(id_cliente, historico, ttl_hours=24):
    if not memoria_cache:
        return
    try:
        memoria_cache.setex(id_cliente, timedelta(hours=ttl_hours), json.dumps(historico, ensure_ascii=False))
    except Exception as e:
        print(f"ERRO salvar_historico: {e}", file=sys.stderr)

# -----------------------
# Montar prompt e chamar Gemini
# -----------------------
def ler_personalidade_sheet():
    try:
        ws = ws_person
        if not ws:
            return ""
        rows = ws.get_all_values()
        # junta todas as células da primeira coluna (ou tudo)
        if not rows:
            return ""
        text_lines = []
        for r in rows:
            # r é lista de colunas; juntar colunas que não vazias
            line = " ".join([c for c in r if c])
            if line:
                text_lines.append(line)
        return "\n".join(text_lines).strip()
    except Exception as e:
        print(f"ERRO ler_personalidade_sheet: {e}", file=sys.stderr)
        return ""

def gerar_resposta_com_gemini(prompt_text):
    if not model:
        return "Desculpe, estou sem acesso ao modelo de linguagem no momento."
    try:
        resp = model.generate_content(prompt_text)
        if hasattr(resp, "text"):
            return resp.text
        return str(resp)
    except Exception as e:
        print(f"ERRO Gemini: {e}", file=sys.stderr)
        return "Desculpe, houve um problema ao gerar a resposta."

# -----------------------
# Envio Z-API
# -----------------------
def enviar_resposta_zapi(numero_destino, texto_da_resposta):
    if not ZAPI_INSTANCE_ID or not ZAPI_TOKEN:
        print("⚠️ Z-API não configurada (ZAPI_INSTANCE_ID/ZAPI_TOKEN faltando). Mensagem não será enviada.")
        return False
    url_api_zapi = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-text"
    payload = {"phone": numero_destino, "message": texto_da_resposta}
    headers = {"Content-Type": "application/json"}
    if ZAPI_CLIENT_TOKEN:
        headers["Client-Token"] = ZAPI_CLIENT_TOKEN
    try:
        r = requests.post(url_api_zapi, json=payload, headers=headers, timeout=10)
        r.raise_for_status()
        try:
            print(f"✅ Z-API enviado: {r.json()}")
        except Exception:
            print(f"✅ Z-API enviado (status {r.status_code})")
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao enviar Z-API: {e}", file=sys.stderr)
        if getattr(e, "response", None) is not None:
            try:
                print("Resposta Z-API:", e.response.text)
            except Exception:
                pass
        return False

# -----------------------
# Pipeline principal: processar mensagem Z-API
# -----------------------
def processar_mensagem_zapi(dados):
    try:
        # ignorar mensagens enviadas pelo próprio número
        if dados.get("fromMe"):
            print("Mensagem marcada fromMe -> ignorada.")
            return

        # Parse do payload com base no seu exemplo
        sender_phone = dados.get("phone") or dados.get("connectedPhone")
        sender_name = dados.get("senderName") or dados.get("chatName") or "Cliente WhatsApp"

        texto_usuario = None
        if isinstance(dados.get("text"), dict):
            texto_usuario = dados["text"].get("message")
        else:
            # fallback para outros formatos (message, body...)
            texto_usuario = dados.get("message") or dados.get("body") or None

        if not sender_phone or not texto_usuario:
            print("⚠️ Sem número ou sem texto -> ignorando.")
            return

        # 1) CRM: achar ou criar
        cliente = encontrar_ou_criar_cliente(sender_phone, sender_name)
        id_cliente = cliente.get("ID_Cliente") or cliente.get("ID") or sender_phone
        row_cliente = cliente.get("__row")

        # 2) Ler personalidade (sheet)
        personalidade_text = ler_personalidade_sheet() or ler_personalidade_file()

        # 3) Buscar contexto
        contexto = buscar_resposta_inteligente(texto_usuario)

        # 4) Extrair dados e atualizar CRM
        encontrados = extrair_dados_da_conversa(texto_usuario)
        if encontrados:
            # Atualiza apenas os campos encontrados
            atualizar_campos_cliente_por_row(row_cliente, encontrados)

        # 5) Histórico (Redis) e interações sheet
        historico = carregar_historico(id_cliente)
        historico.append({"role": "user", "content": texto_usuario, "ts": datetime.now(TZ).isoformat()})
        salvar_historico(id_cliente, historico)

        # registrar interação resumida (limit)
        resumo = texto_usuario if len(texto_usuario) <= 1000 else texto_usuario[:1000]
        registrar_interacao(id_cliente, resumo, canal="WhatsApp")

        # 6) montar prompt (super-prompt)
        context_lines = []
        if contexto is None:
            context_lines.append("Sem contexto específico encontrado.")
        else:
            if contexto.get("tipo") == "produto":
                context_lines.append("Produto relevante encontrado:")
                context_lines.append(json.dumps(contexto.get("linha", {}), ensure_ascii=False))
            elif contexto.get("tipo") == "diretriz":
                context_lines.append(f"Diretriz apontada (alvo={contexto.get('alvo')}, kw={contexto.get('match_kw')}):")
                context_lines.append(json.dumps(contexto.get("linha", {}), ensure_ascii=False))
            else:
                context_lines.append(str(contexto))

        ult_interacoes = carregar_ultimas_interacoes(id_cliente, limit=5)
        prompt = (
            f"Você é SHA — Agente Comercial.\n\n"
            f"Personalidade:\n{personalidade_text}\n\n"
            f"Dados do cliente:\nNome: {sender_name}\nTelefone: {sender_phone}\nID_Cliente: {id_cliente}\n\n"
            f"Contexto recolhido:\n{chr(10).join(context_lines)}\n\n"
            f"Últimas interações (resumidas):\n{json.dumps(ult_interacoes, ensure_ascii=False)}\n\n"
            f"Histórico recente (cache):\n{json.dumps(historico[-10:], ensure_ascii=False)}\n\n"
            f"Pergunta do cliente: \"{texto_usuario}\"\n\n"
            "Responda como um vendedor prestativo: ofereça produtos relevantes, tarifas, prazos, verifique estoque e confirme endereço/forma de pagamento quando necessário. Seja sucinto, objetivo e cordial."
        )

        # 7) gerar resposta IA
        resposta_texto = gerar_resposta_com_gemini(prompt)

        # 8) salvar no histórico e enviar via Z-API
        historico.append({"role": "assistant", "content": resposta_texto, "ts": datetime.now(TZ).isoformat()})
        salvar_historico(id_cliente, historico)

        enviado = enviar_resposta_zapi(sender_phone, resposta_texto)
        if not enviado:
            print("⚠️ Falha no envio; resposta salva no histórico.")
        else:
            print("✅ Resposta enviada e histórico atualizado.")
        return
    except Exception as e:
        print(f"ERRO processar_mensagem_zapi: {e}", file=sys.stderr)
        return

# fallback: ler personalidade de arquivo, caso não exista a aba com conteúdo
def ler_personalidade_file():
    try:
        if os.path.exists("personalidade.txt"):
            with open("personalidade.txt", "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception as e:
        print(f"⚠️ Erro lendo personalidade.txt: {e}", file=sys.stderr)
    return ""

# -----------------------
# Flask endpoints (webhook)
# -----------------------
@app.route("/", methods=["GET"])
def raiz():
    return f"{APP_NAME} ativo", 200

@app.route("/mensagem", methods=["GET", "POST"])
def receber_mensagem():
    # GET para verificação (opcional)
    if request.method == "GET":
        token_sent = request.args.get("hub.verify_token")
        return (request.args.get("hub.challenge"), 200) if token_sent == VERIFY_TOKEN else ('Token inválido', 403)

    # POST - payload da Z-API
    data = request.get_json(force=True, silent=True)
    print(f"--- DADO BRUTO RECEBIDO: {json.dumps(data, ensure_ascii=False, indent=2)}")
    if not data:
        return "Sem payload", 200

    # Processa somente notificações de mensagem (tem instanceId no seu exemplo)
    if data.get("instanceId"):
        # processar em background não é permitido no nosso modelo — processamos aqui
        processar_mensagem_zapi(data)
        return "OK", 200

    print("Payload ignorado (sem instanceId).")
    return "Ignorado", 200

# -----------------------
# Run
# -----------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
    print(f"Rodando {APP_NAME} em 0.0.0.0:{port} (debug={debug})")
    app.run(host="0.0.0.0", port=port, debug=debug)
