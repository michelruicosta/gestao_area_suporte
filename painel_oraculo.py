import os
import json
import copy
import calendar
import math
import unicodedata
import pytz
import re
import smtplib
import requests
from config.categorias import categoria_display
import xml.etree.ElementTree as ET
import time # [AJUSTE] Para controle de cache financeiro
import logging  # 🔍 SISTEMA DE LOG EM ARQUIVO
from dateutil import parser
from email.header import decode_header as email_decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
# [AJUSTE] Adicionada biblioteca flash para mensagens de feedback
from flask import Flask, jsonify, render_template, send_from_directory, request, redirect, url_for, flash
from datetime import datetime, timedelta, date
from dotenv import load_dotenv
from openai import OpenAI
# [AJUSTE] Adicionadas funções de segurança para Hash de Senha
from werkzeug.security import generate_password_hash, check_password_hash
# [AJUSTE] Bibliotecas de Segurança (Login)
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

# 🔍 CONFIGURAR LOGGING EM ARQUIVO (salvo em logs/avulso/, mesmo padrão do executar_tudo)
_raiz_painel = os.path.dirname(os.path.abspath(__file__))
PASTA_LOG_PAINEL = os.path.join(_raiz_painel, 'logs', 'avulso')
os.makedirs(PASTA_LOG_PAINEL, exist_ok=True)
_ARQUIVO_LOG_PAINEL = os.path.join(PASTA_LOG_PAINEL, 'painel_debug.log')
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(_ARQUIVO_LOG_PAINEL, encoding='utf-8'),
        logging.StreamHandler()  # Também mostra no console
    ]
)
logger = logging.getLogger(__name__)

# [MONITOR DE CUSTOS IA] - Importação Segura com Try/Except
try:
    from scripts.monitor_consumo_ia import ler_estatisticas
except ImportError:
    # Função dummy caso o arquivo não exista, para não derrubar o servidor
    def ler_estatisticas(): return {}

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

app = Flask(__name__)
# [AJUSTE] Chave de Segurança para Sessão (Obrigatório para Login)
app.secret_key = os.getenv("SECRET_KEY", "chave_seguranca_finaud_nexus_2026")

# 🔍 MIDDLEWARE: Log de TODAS as requisições (inclusive as que falham)
@app.before_request
def log_request():
    logger.info("="*70)
    logger.info("📥 REQUISIÇÃO RECEBIDA")
    logger.info("="*70)
    logger.info(f"   Método: {request.method}")
    logger.info(f"   URL: {request.url}")
    logger.info(f"   Path: {request.path}")
    logger.info(f"   Autenticado: {current_user.is_authenticated if hasattr(current_user, 'is_authenticated') else 'N/A'}")
    logger.info("="*70)

# --- CONFIGURAÇÃO DO LOGIN MANAGER ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Se não logar, manda pra cá
login_manager.login_message = None  # Não exibe "Please log in to access this page."

# --- CONFIGURAÇÃO DE CAMINHOS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
import sys as _sys
_scripts_dir = os.path.join(BASE_DIR, 'scripts')
if _scripts_dir not in _sys.path:
    _sys.path.insert(0, _scripts_dir)
from paths import (
    F_INTEGRADOR, F_FOG, F_PARES_THREADS,
    F_DIARIO, F_CADASTRO_CLIENTES, F_ROTULOS,
    F_REGISTROS_FOG, F_USUARIOS, PIPELINE_DIR, PAINEL_DIR, CONFIG_DIR,
    load_aguardando, save_aguardando, load_concluidas, save_concluidas,
    load_cartao_overrides, save_cartao_overrides,
)
import pipeline_jobs
DATA_DIR    = PIPELINE_DIR
PASTA_DADOS = PIPELINE_DIR

BASE_DADOS                        = F_INTEGRADOR
ARQUIVO_FOG                       = F_FOG
STATUS_COMPLIANCE                 = os.path.join(PIPELINE_DIR, 'status_compliance.json')
ARQUIVO_DECISOES                  = os.path.join(PIPELINE_DIR, 'decisoes_nexus.json')
ARQUIVO_REGISTROS                 = F_REGISTROS_FOG
USUARIOS_FILE                     = F_USUARIOS
ARQUIVO_PARES_THREADS_CONFIRMADOS = F_PARES_THREADS
ARQUIVO_DIARIO                    = F_DIARIO
ARQUIVO_CADASTRO_CLIENTES         = F_CADASTRO_CLIENTES
ARQUIVO_ROTULOS_EMPRESA_GESTAO    = F_ROTULOS

# --- CONFIGURAÇÕES API FOGBUGZ ---
FOG_TOKEN = os.getenv("FOGBUGZ_TOKEN")
FOG_URL_API = "https://finaud.fogbugz.com/api.asp"

# --- SISTEMA DE CACHE DO DÓLAR (AwesomeAPI) ---
CACHE_FINANCEIRO = {
    "dolar_valor": 6.10,        # Valor inicial de segurança (Fallback)
    "ultima_atualizacao": 0     # Timestamp da última consulta
}

# --- CACHE EM MEMÓRIA DO INTEGRADOR (03_integrador_dados_site.json) ---
# Invalidado automaticamente quando o arquivo muda no disco (mtime).
# Evita reler e parsear ~267 MB a cada request de /api/dados e /api/threads.
_CACHE_INTEGRADOR: dict = {
    "dados": None,
    "mtime": None,
    "caminho": None,
}

def _carregar_json_cached(caminho: str):
    """Carrega JSON com cache em memória invalidado por mtime.

    Para o integrador (~267 MB), a primeira leitura é lenta; as seguintes
    retornam o objeto Python já em memória enquanto o arquivo não mudar.
    Outros arquivos pequenos passam por aqui sem custo extra.
    """
    if not os.path.exists(caminho):
        logger.error(f"❌ CACHE: arquivo não existe: {caminho}")
        return [] if "compliance" not in caminho else {}
    try:
        mtime = os.path.getmtime(caminho)
        if (
            _CACHE_INTEGRADOR["dados"] is not None
            and _CACHE_INTEGRADOR["caminho"] == caminho
            and _CACHE_INTEGRADOR["mtime"] == mtime
        ):
            logger.debug(f"✅ CACHE HIT integrador (mtime inalterado)")
            return _CACHE_INTEGRADOR["dados"]
        logger.info(f"🔄 CACHE MISS integrador — relendo {caminho}")
        with open(caminho, "r", encoding="utf-8") as f:
            dados = json.load(f)
        _CACHE_INTEGRADOR["dados"] = dados
        _CACHE_INTEGRADOR["mtime"] = mtime
        _CACHE_INTEGRADOR["caminho"] = caminho
        logger.info(f"✅ Integrador cacheado ({type(dados).__name__})")
        return dados
    except Exception as e:
        logger.error(f"❌ ERRO _carregar_json_cached: {e}", exc_info=True)
        return []

# --- CACHE DE PAYLOAD COMPUTADO POR DATA (/api/dados) ---
# Guarda o resultado processado de montagem_api_dados_snapshot por (data, busca_ativa).
# Invalida TUDO quando qualquer arquivo de entrada muda (mtime).
_CACHE_PAYLOAD_DADOS: dict = {}   # key: (data_norm, busca_ativa) → payload dict
_CACHE_PAYLOAD_ESTADO: tuple = ()  # tupla de mtimes dos arquivos de entrada

def _estado_key_payload() -> tuple:
    """Tupla de mtimes dos arquivos que influenciam /api/dados.
    Qualquer mudança invalida todos os payloads cacheados."""
    from paths import (  # pylint: disable=import-outside-toplevel
        F_AGUARDANDO_AUTO,
        F_CONCLUIDAS_AUTO,
        F_CARTAO_OVERRIDES, F_PARES_THREADS,
    )
    arquivos = [
        BASE_DADOS,
        F_AGUARDANDO_AUTO,
        F_CONCLUIDAS_AUTO,
        F_CARTAO_OVERRIDES, F_PARES_THREADS,
    ]
    return tuple(
        os.path.getmtime(p) if os.path.exists(p) else 0.0
        for p in arquivos
    )

def _payload_cache_get(data_norm: str, busca_ativa: bool):
    """Retorna payload cacheado ou None se inválido/ausente."""
    global _CACHE_PAYLOAD_ESTADO
    try:
        estado_atual = _estado_key_payload()
        if estado_atual != _CACHE_PAYLOAD_ESTADO:
            _CACHE_PAYLOAD_DADOS.clear()
            _CACHE_PAYLOAD_ESTADO = estado_atual
            return None
        return _CACHE_PAYLOAD_DADOS.get((data_norm, busca_ativa))
    except Exception:
        return None

def _payload_cache_set(data_norm: str, busca_ativa: bool, payload: dict) -> None:
    """Armazena payload no cache (estado já verificado por _payload_cache_get)."""
    try:
        _CACHE_PAYLOAD_DADOS[(data_norm, busca_ativa)] = payload
    except Exception:
        pass


# --- PARSER RÁPIDO DE DATAS (substitui dateutil para timestamps ISO do integrador) ---
# dateutil.parser.parse é ~500× mais lento que strptime/fromisoformat para formatos
# ISO conhecidos (YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, etc.).  O profiler mostrou 97.706
# chamadas ao dateutil gastando 52 s por request.  Esta função tenta o caminho rápido
# primeiro e só recorre ao dateutil se falhar.
import re as _re_mod
_RE_ISO_DT  = _re_mod.compile(r'^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})')
_RE_ISO_D   = _re_mod.compile(r'^(\d{4})-(\d{2})-(\d{2})')
_RE_BR_DT   = _re_mod.compile(r'^(\d{2})[/\-](\d{2})[/\-](\d{4})')

def _parse_dt_rapido(val: str, dayfirst: bool = True):
    """Retorna datetime (sem tz) ou None — tenta ISO antes de dateutil."""
    if not val:
        return None
    val = val.strip()
    m = _RE_ISO_DT.match(val)
    if m:
        try:
            return datetime(int(m[1]), int(m[2]), int(m[3]),
                            int(m[4]), int(m[5]), int(m[6]))
        except ValueError:
            pass
    m = _RE_ISO_D.match(val)
    if m:
        try:
            return datetime(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            pass
    if dayfirst:
        m = _RE_BR_DT.match(val)
        if m:
            try:
                return datetime(int(m[3]), int(m[2]), int(m[1]))
            except ValueError:
                pass
    try:
        dt = parser.parse(val, dayfirst=dayfirst)
        return dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt
    except Exception:
        return None


# --- CACHE DE ARQUIVO PARA CADASTRO E RÓTULOS (evita json.load por evento) ---
# Profiler: _carregar_cadastro_empresas chamada 6.631× por request = 11 s de I/O.
_CACHE_CADASTRO: dict = {"dados": None, "mtime": None}
_CACHE_ROTULOS:  dict = {"dados": None, "mtime": None}

def _cadastro_cached() -> dict:
    """Cadastro de clientes com cache em memória invalidado por mtime."""
    if not os.path.exists(ARQUIVO_CADASTRO_CLIENTES):
        return {}
    try:
        mt = os.path.getmtime(ARQUIVO_CADASTRO_CLIENTES)
        if _CACHE_CADASTRO["dados"] is not None and _CACHE_CADASTRO["mtime"] == mt:
            return _CACHE_CADASTRO["dados"]
        with open(ARQUIVO_CADASTRO_CLIENTES, "r", encoding="utf-8") as f:
            d = json.load(f)
        d = d if isinstance(d, dict) else {}
        _CACHE_CADASTRO["dados"] = d
        _CACHE_CADASTRO["mtime"] = mt
        return d
    except Exception:
        return _CACHE_CADASTRO["dados"] or {}

def _rotulos_cached() -> dict:
    """Rótulos de empresa com cache em memória invalidado por mtime."""
    arq = getattr(_sys.modules[__name__], "ARQUIVO_ROTULOS_EMPRESA_GESTAO", None)
    if arq is None:
        return {}
    if not os.path.exists(arq):
        return {}
    try:
        mt = os.path.getmtime(arq)
        if _CACHE_ROTULOS["dados"] is not None and _CACHE_ROTULOS["mtime"] == mt:
            return _CACHE_ROTULOS["dados"]
        with open(arq, "r", encoding="utf-8") as f:
            raw = json.load(f)
        out: dict = {}
        if isinstance(raw, dict):
            for k, v in raw.items():
                if isinstance(k, str) and not k.startswith("_") and isinstance(v, str) and v.strip():
                    out[k.strip().lower()] = v.strip()
        _CACHE_ROTULOS["dados"] = out
        _CACHE_ROTULOS["mtime"] = mt
        return out
    except Exception:
        return _CACHE_ROTULOS["dados"] or {}

def obter_dolar_atual():
    """Busca cotação USD-BRL na AwesomeAPI."""
    agora = time.time()
    tempo_passado = agora - CACHE_FINANCEIRO["ultima_atualizacao"]
    
    if tempo_passado < 3600:
        return CACHE_FINANCEIRO["dolar_valor"]

    try:
        print("🔄 Atualizando cotação do Dólar via AwesomeAPI...")
        url = "https://economia.awesomeapi.com.br/last/USD-BRL"
        response = requests.get(url, timeout=5) 
        
        if response.status_code == 200:
            dados = response.json()
            novo_valor = float(dados['USDBRL']['bid'])
            CACHE_FINANCEIRO["dolar_valor"] = novo_valor
            CACHE_FINANCEIRO["ultima_atualizacao"] = agora
            return novo_valor
            
    except Exception as e:
        print(f"⚠️ Erro ao buscar Dólar: {e}")
    
    return CACHE_FINANCEIRO["dolar_valor"]

def buscar_usuarios_ativos_fog():
    try:
        params = {
            'token': FOG_TOKEN,
            'cmd': 'listPeople',
            'fIncludeVirtual': 0,
            'fIncludeDeleted': 0,
            'fIncludeActive': 1
        }
        resp = requests.get(FOG_URL_API, params=params)
        # [ALTERNATIVA] Usa xml.etree.ElementTree (built-in) em vez de xmltodict
        root = ET.fromstring(resp.text)
        pessoas = root.findall('.//person')
        ativos = []
        for pessoa in pessoas:
            f_deleted = pessoa.get('fDeleted', '0')
            f_active = pessoa.get('fActive', '0')
            if f_deleted == '0' and f_active == '1':
                nome = pessoa.get('sFullName')
                if nome:
                    ativos.append(nome)
        return ativos
    except Exception as e:
        print(f"Erro ao buscar usuários no Fog: {e}")
        return []

def extrair_usuario_real(caso):
    resp_atual = caso.get('responsavel') or caso.get('autor')
    if resp_atual and resp_atual != "CLOSED":
        return resp_atual
    
    eventos = caso.get('eventos', [])
    if isinstance(eventos, dict): eventos = [eventos]
    
    if eventos:
        for ev in reversed(eventos):
            if ev.get('sVerb') in ['Closed', 'Resolved']:
                return ev.get('sPerson')
    return "Sistema"

def carregar_usuarios():
    if not os.path.exists(USUARIOS_FILE):
        return {}
    try:
        with open(USUARIOS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Erro ao ler usuários: {e}")
        return {}

def salvar_usuarios(usuarios):
    try:
        with open(USUARIOS_FILE, 'w', encoding='utf-8') as f:
            json.dump(usuarios, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Erro ao salvar usuários: {e}")


# ---------------------------------------------------------------------------
# Helpers de gestão de usuários (tela /admin/usuarios — adicionado em
# 2026-05-07).
# ---------------------------------------------------------------------------
ROLES_VALIDOS = ('admin', 'gestor', 'diretor', 'gerencial', 'operacional')


def _gerar_uid_unico_para_email(email: str, usuarios: dict) -> str:
    """Gera um identificador interno (uid) único para um novo usuário a
    partir do e-mail. Mantém a chave do dict curta e legível, sem confundir
    o operador (que vai logar pelo e-mail mesmo)."""
    import re as _re
    base = (email or "").split("@", 1)[0].lower()
    base = _re.sub(r"[^a-z0-9._-]+", ".", base).strip(".")
    if not base:
        base = "usuario"
    candidato = base
    i = 2
    while candidato in usuarios:
        candidato = f"{base}{i}"
        i += 1
    return candidato


def _email_ja_cadastrado(email: str, usuarios: dict, ignorar_uid: str = "") -> bool:
    email_norm = (email or "").strip().lower()
    if not email_norm:
        return False
    for uid, dados in usuarios.items():
        if uid == ignorar_uid:
            continue
        if (dados.get("email") or "").strip().lower() == email_norm:
            return True
    return False


def _so_admin_acessa():
    """Retorna True se o current_user é admin. Usado nas rotas de
    /admin/usuarios para bloquear acesso de quem não é admin."""
    return getattr(current_user, "role", "") == "admin"


def _enviar_email_smtp(destino: str, assunto: str, corpo_html: str) -> tuple[bool, str]:
    """Envia um e-mail via SMTP do Gmail usando as credenciais em
    EMAIL_USER / EMAIL_PASS (mesmas variáveis usadas em /recuperar_senha).
    Retorna (sucesso, mensagem_erro_curta). Tolerante a erro: nunca lança.
    """
    remetente = os.getenv("EMAIL_USER")
    senha_smtp = os.getenv("EMAIL_PASS")
    if not remetente or not senha_smtp:
        return False, "SMTP não configurado (EMAIL_USER/EMAIL_PASS ausentes no .env)"
    if not destino:
        return False, "Destinatário vazio"
    msg = MIMEMultipart()
    msg["From"] = remetente
    msg["To"] = destino
    msg["Subject"] = assunto
    msg.attach(MIMEText(corpo_html, "html"))
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(remetente, senha_smtp)
        server.send_message(msg)
        server.quit()
        return True, ""
    except Exception as exc:
        logger.error(f"_enviar_email_smtp falhou: {exc}", exc_info=True)
        return False, str(exc)[:200]


# ----- Cores fixas do Oráculo (espelham o tema dark do painel) ------------
_EMAIL_BG_HEADER       = "#3333A8"   # Azul indigo Finaud
_EMAIL_BG_HEADER_GRAD  = "#1e1e72"   # Azul escuro Finaud
_EMAIL_TXT_HEADER      = "#ffffff"
_EMAIL_TXT_MUTED       = "#8899bb"
_EMAIL_BG_BODY         = "#f1f5f9"
_EMAIL_BG_CARD         = "#ffffff"
_EMAIL_TXT_BODY        = "#3333A8"   # Azul substitui preto
_EMAIL_TXT_SECONDARY   = "#1e1e72"
_EMAIL_BORDER_SOFT     = "#c8c8e8"
_EMAIL_VERDE           = "#8DC63F"   # Verde limao Finaud
_EMAIL_VERDE_ESC       = "#6aab1e"   # Verde escuro (legibilidade)


def _email_chrome_oraculo(
    titulo: str,
    cor_acento: str,
    nome: str,
    conteudo_html: str,
) -> str:
    """Casca visual padrão dos e-mails transacionais do Oráculo:
    cabeçalho escuro Slate (igual à sidebar do painel) + corpo claro com
    título "Olá, ${nome}" + footer fixo. Cada e-mail específico injeta o
    conteúdo principal em ``conteudo_html`` (caixa de credenciais, botão
    CTA, etc.).
    """
    return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:{_EMAIL_BG_BODY};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;">
  <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background:{_EMAIL_BG_BODY};">
    <tr><td align="center" style="padding:32px 12px;">
      <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600"
             style="max-width:600px;width:100%;background:{_EMAIL_BG_CARD};border-radius:14px;overflow:hidden;
                    box-shadow:0 4px 20px rgba(15,23,42,.08);border:1px solid {_EMAIL_BORDER_SOFT};">

        <!-- Header escuro (identidade Oráculo) -->
        <tr><td style="background:linear-gradient(135deg,{_EMAIL_BG_HEADER} 0%,{_EMAIL_BG_HEADER_GRAD} 100%);padding:28px 32px 24px 32px;">
          <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
            <tr>
              <td style="font-size:13px;font-weight:700;letter-spacing:1.5px;color:{cor_acento};text-transform:uppercase;">
                🤖 ORÁCULO 360
              </td>
            </tr>
            <tr>
              <td style="padding-top:8px;font-size:22px;font-weight:700;color:{_EMAIL_TXT_HEADER};line-height:1.3;">
                {titulo}
              </td>
            </tr>
          </table>
        </td></tr>

        <!-- Body inicial: saudação -->
        <tr><td style="padding:28px 32px 0 32px;color:{_EMAIL_TXT_BODY};font-size:14.5px;line-height:1.6;">
          <p style="margin:0 0 16px 0;">Olá, <b>{nome}</b>,</p>
        </td></tr>

        <!-- Conteúdo específico do e-mail -->
        {conteudo_html}

        <!-- Footer -->
        <tr><td style="padding:20px 32px 28px 32px;border-top:1px solid {_EMAIL_BORDER_SOFT};margin-top:12px;">
          <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
            <tr>
              <td style="font-size:11.5px;color:{_EMAIL_TXT_MUTED};line-height:1.5;">
                Este e-mail foi enviado automaticamente pelo sistema <b style="color:{_EMAIL_TXT_BODY};">Oráculo 360</b>.
                <br>Se você recebeu por engano, ignore esta mensagem.
              </td>
            </tr>
          </table>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
""".strip()


def _email_bloco_credenciais(
    intro_html: str,
    email_login: str,
    rotulo_senha: str,
    senha: str,
    cor_acento: str,
    aviso_html: str,
    rodape_extra_html: str = "",
) -> str:
    """Conteúdo: parágrafo intro + caixa de credenciais (login + senha) +
    aviso destacado + bloco extra opcional. Usado por boas-vindas e reset
    administrativo (admin define a senha)."""
    return f"""
        <tr><td style="padding:0 32px 12px 32px;color:{_EMAIL_TXT_BODY};font-size:14.5px;line-height:1.6;">
          {intro_html}
        </td></tr>
        <tr><td style="padding:8px 32px 8px 32px;">
          <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"
                 style="background:#f1f5f9;border:1px solid {_EMAIL_BORDER_SOFT};border-left:4px solid {cor_acento};border-radius:8px;">
            <tr>
              <td style="padding:14px 18px;font-size:12px;font-weight:700;color:{_EMAIL_TXT_SECONDARY};
                         text-transform:uppercase;letter-spacing:.5px;width:140px;">
                E-mail (login)
              </td>
              <td style="padding:14px 18px;font-size:14px;color:{_EMAIL_TXT_BODY};word-break:break-all;">
                {email_login}
              </td>
            </tr>
            <tr>
              <td style="padding:14px 18px;font-size:12px;font-weight:700;color:{_EMAIL_TXT_SECONDARY};
                         text-transform:uppercase;letter-spacing:.5px;border-top:1px solid {_EMAIL_BORDER_SOFT};">
                {rotulo_senha}
              </td>
              <td style="padding:14px 18px;font-size:15px;font-weight:700;color:{cor_acento};
                         font-family:'Courier New',monospace;letter-spacing:1.5px;
                         border-top:1px solid {_EMAIL_BORDER_SOFT};">
                {senha}
              </td>
            </tr>
          </table>
        </td></tr>
        <tr><td style="padding:18px 32px 8px 32px;">
          <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"
                 style="background:#f0f0ff;border:1px solid #c8c8e8;border-left:4px solid #8DC63F;border-radius:8px;">
            <tr><td style="padding:12px 16px;font-size:13px;color:{_EMAIL_TXT_SECONDARY};line-height:1.55;">
              {aviso_html}
            </td></tr>
          </table>
        </td></tr>
        {rodape_extra_html}
"""


def _email_bloco_botao_cta(
    intro_html: str,
    label_botao: str,
    url_botao: str,
    cor_acento: str,
    aviso_html: str,
    rodape_extra_html: str = "",
) -> str:
    """Conteúdo: parágrafo intro + botão CTA grande (link) + aviso de
    segurança + URL alternativa em texto (caso o botão não funcione no
    cliente de e-mail). Usado pela recuperação de senha (auto-serviço)."""
    return f"""
        <tr><td style="padding:0 32px 12px 32px;color:{_EMAIL_TXT_BODY};font-size:14.5px;line-height:1.6;">
          {intro_html}
        </td></tr>
        <tr><td align="center" style="padding:8px 32px 16px 32px;">
          <table role="presentation" cellspacing="0" cellpadding="0" border="0">
            <tr><td align="center"
                    style="background:{cor_acento};border-radius:10px;
                           box-shadow:0 4px 12px rgba(59,130,246,.25);">
              <a href="{url_botao}" target="_blank"
                 style="display:inline-block;padding:13px 28px;font-size:14.5px;font-weight:700;
                        color:#ffffff;text-decoration:none;letter-spacing:.3px;">
                {label_botao}
              </a>
            </td></tr>
          </table>
        </td></tr>
        <tr><td style="padding:0 32px 16px 32px;">
          <p style="margin:0;font-size:12.5px;color:{_EMAIL_TXT_SECONDARY};line-height:1.55;">
            Se o botão acima não funcionar, copie e cole este endereço no seu navegador:
          </p>
          <p style="margin:6px 0 0 0;font-size:12.5px;font-family:'Courier New',monospace;
                    color:{cor_acento};word-break:break-all;line-height:1.5;">
            {url_botao}
          </p>
        </td></tr>
        <tr><td style="padding:8px 32px 8px 32px;">
          <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"
                 style="background:#f0f0ff;border:1px solid #c8c8e8;border-left:4px solid #8DC63F;border-radius:8px;">
            <tr><td style="padding:12px 16px;font-size:13px;color:{_EMAIL_TXT_SECONDARY};line-height:1.55;">
              {aviso_html}
            </td></tr>
          </table>
        </td></tr>
        {rodape_extra_html}
"""


def _email_template_boas_vindas(nome: str, email_login: str, senha: str) -> str:
    """HTML do e-mail de boas-vindas."""
    cor = _EMAIL_VERDE_ESC  # verde Finaud
    conteudo = _email_bloco_credenciais(
        intro_html=(
            "<p style='margin:0 0 14px 0;'>Sua conta foi criada com sucesso. Use os dados "
            "abaixo para acessar o painel:</p>"
        ),
        email_login=email_login,
        rotulo_senha="Senha inicial",
        senha=senha,
        cor_acento=cor,
        aviso_html=(
            "🔐 Por segurança, recomendamos que você troque a senha logo no primeiro acesso, "
            "em <b>Perfil → Alterar senha</b>."
        ),
    )
    return _email_chrome_oraculo(
        titulo="Bem-vindo(a) ao Oráculo 360",
        cor_acento=cor,
        nome=nome,
        conteudo_html=conteudo,
    )


def _email_template_senha_resetada(nome: str, email_login: str, senha: str) -> str:
    """HTML do e-mail de senha resetada pelo admin."""
    cor = _EMAIL_BG_HEADER   # azul Finaud
    rodape_alerta = (
        "<tr><td style='padding:0 32px 8px 32px;'>"
        f"<div style='background:#f0f0ff;border:1px solid {_EMAIL_BORDER_SOFT};"
        f"border-left:4px solid {_EMAIL_VERDE};border-radius:8px;padding:12px 16px;"
        f"font-size:12.5px;color:{_EMAIL_TXT_SECONDARY};line-height:1.5;'>"
        "<b>Nao pediu este reset?</b> Fale com o administrador imediatamente."
        "</div></td></tr>"
    )
    conteudo = _email_bloco_credenciais(
        intro_html=(
            "<p style='margin:0 0 14px 0;'>O administrador <b>resetou a sua senha</b> de acesso "
            "ao Oráculo 360. Use os dados abaixo para entrar:</p>"
        ),
        email_login=email_login,
        rotulo_senha="Nova senha",
        senha=senha,
        cor_acento=cor,
        aviso_html=(
            "🔐 Por segurança, recomendamos que você troque esta senha logo no primeiro acesso, "
            "em <b>Perfil → Alterar senha</b>."
        ),
        rodape_extra_html=rodape_alerta,
    )
    return _email_chrome_oraculo(
        titulo="Sua senha foi resetada",
        cor_acento=cor,
        nome=nome,
        conteudo_html=conteudo,
    )


def _email_template_recuperacao_senha(nome: str, email_login: str, link_reset: str) -> str:
    """HTML do e-mail de recuperação de senha (auto-serviço — usuário pediu).

    O link ``link_reset`` deve ser construído com ``url_for(..., _external=True)``,
    o que faz o Flask gerar a URL absoluta a partir do host do request. Em
    desenvolvimento, fica ``http://127.0.0.1:5000/...``; no deploy, vira
    automaticamente o domínio público (ex.: ``https://oraculo.finaud.com.br/...``)
    sem precisar mudar este código."""
    cor = _EMAIL_BG_HEADER   # azul Finaud
    rodape_seguranca = (
        "<tr><td style='padding:0 32px 8px 32px;'>"
        f"<div style='background:#f0f0ff;border:1px solid {_EMAIL_BORDER_SOFT};"
        f"border-left:4px solid {_EMAIL_VERDE};border-radius:8px;padding:12px 16px;"
        f"font-size:12.5px;color:{_EMAIL_TXT_SECONDARY};line-height:1.5;'>"
        "<b>Nao solicitou esta recuperacao?</b> Ignore este e-mail. Sua senha "
        "atual permanece inalterada."
        "</div></td></tr>"
    )
    conteudo = _email_bloco_botao_cta(
        intro_html=(
            "<p style='margin:0 0 10px 0;'>Recebemos uma solicitação para recuperar o acesso "
            f"à conta <b>{email_login}</b> no Oráculo 360.</p>"
            "<p style='margin:0 0 14px 0;'>Clique no botão abaixo para definir uma nova senha:</p>"
        ),
        label_botao="🔑 Recuperar minha senha",
        url_botao=link_reset,
        cor_acento=cor,
        aviso_html=(
            "🔐 Por segurança, este link é válido apenas para esta solicitação. Se você não "
            "concluir agora, será necessário pedir uma nova recuperação."
        ),
        rodape_extra_html=rodape_seguranca,
    )
    return _email_chrome_oraculo(
        titulo="Recuperação de acesso",
        cor_acento=cor,
        nome=nome,
        conteudo_html=conteudo,
    )


class User(UserMixin):
    def __init__(self, id, dados):
        self.id = id
        self.role = dados.get('role', 'user')
        self.name = dados.get('name', 'Usuário')
        self.cargo = dados.get('cargo', 'N/A')
        self.depto = dados.get('depto', 'N/A')
        self.email = dados.get('email', '')
        # Padrão True quando o campo não existe (retrocompat com usuários
        # criados antes da introdução do flag de desativação).
        self.ativo = bool(dados.get('ativo', True))

@login_manager.user_loader
def load_user(user_id):
    usuarios = carregar_usuarios()
    if user_id not in usuarios:
        return None
    return User(user_id, usuarios[user_id])

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def carregar_json(caminho):
    logger.info("="*70)
    logger.info(f"🔍 CARREGAR_JSON - Tentando carregar: {caminho}")
    logger.info("="*70)
    
    if not os.path.exists(caminho):
        logger.error(f"❌ ERRO: Arquivo não existe!")
        return [] if 'compliance' not in caminho else {}
    
    logger.info(f"✅ Arquivo existe")
    
    try:
        with open(caminho, 'r', encoding='utf-8') as f:
            dados = json.load(f)
        
        logger.info(f"✅ JSON carregado com sucesso")
        logger.info(f"   Tipo: {type(dados).__name__}")
        
        # 🔧 COMPATIBILIDADE: Novo formato do integrador (dict com 'eventos' e 'threads')
        if isinstance(dados, dict):
            logger.info(f"   É um dict com campos: {list(dados.keys())}")
            
            if 'eventos' in dados:
                eventos = dados['eventos']
                logger.info(f"   ✅ Campo 'eventos' encontrado com {len(eventos)} itens")
                return dados # Retornamos o dict todo para processar threads e eventos na rota
            else:
                logger.warning(f"   ⚠️  É dict mas NÃO tem campo 'eventos'")
                return dados
        else:
            # Formato antigo (lista direta)
            logger.info(f"   É uma lista com {len(dados)} itens")
            return dados
            
    except Exception as e:
        logger.error(f"❌ ERRO ao ler JSON: {e}", exc_info=True)
        return []

# --- ROTAS DE AUTENTICAÇÃO ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email_login = request.form['username']
        password = request.form['password']
        usuarios = carregar_usuarios()
        
        user_id_encontrado = None
        for uid, dados in usuarios.items():
            if dados.get('email') == email_login:
                user_id_encontrado = uid
                break

        if user_id_encontrado and check_password_hash(usuarios[user_id_encontrado]['password'], password):
            dados_user = usuarios[user_id_encontrado]
            # Usuário desativado pelo admin não pode logar (mas mantemos o
            # registo no JSON para preservar histórico de auditoria).
            if not dados_user.get('ativo', True):
                flash("Usuário desativado. Procure o administrador.", "error")
                return render_template('login.html')
            user = User(user_id_encontrado, dados_user)
            login_user(user)
            if user.role == 'operacional':
                return redirect(url_for('page_operacional'))
            return redirect(url_for('index'))

        flash("E-mail ou senha incorretos.", "error")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/recuperar_senha', methods=['GET', 'POST'])
def recuperar_senha():
    if request.method == 'POST':
        email_destino = (request.form.get('email') or '').strip().lower()
        usuarios = carregar_usuarios()

        user_found = None
        dados_user = None
        for uid, dados in usuarios.items():
            if (dados.get('email') or '').strip().lower() == email_destino:
                user_found = uid
                dados_user = dados
                break

        if user_found and dados_user:
            # ``url_for(..., _external=True)`` usa o host do request, então
            # em produção o link vira do domínio público sem mudar código.
            link_reset = url_for(
                'resetar_senha_form',
                token="token_seguro_123",
                _external=True,
            )
            ok_email, _erro = _enviar_email_smtp(
                destino=email_destino,
                assunto="Recuperação de acesso — Oráculo 360",
                corpo_html=_email_template_recuperacao_senha(
                    nome=dados_user.get('name', email_destino),
                    email_login=email_destino,
                    link_reset=link_reset,
                ),
            )
            # Por segurança, não revelamos se o e-mail existe ou se o SMTP
            # falhou: a mensagem ao usuário é genérica em ambos os casos.
            if ok_email:
                flash("Se o e-mail existir, enviaremos as instruções.", "success")
            else:
                flash("Se o e-mail existir, enviaremos as instruções.", "success")
        else:
            # Não revela existência da conta (anti-enumeração).
            flash("Se o e-mail existir, enviaremos as instruções.", "success")
        return redirect(url_for('login'))
    return render_template('recuperar_senha.html')

@app.route('/resetar_senha_form/<token>')
def resetar_senha_form(token):
    return render_template('resetar_senha_novo.html', token=token)

@app.route('/atualizar_senha_esquecida', methods=['POST'])
def atualizar_senha_esquecida():
    nova_senha = request.form.get('nova_senha')
    usuarios = carregar_usuarios()
    if 'admin' in usuarios:
        usuarios['admin']['password'] = generate_password_hash(nova_senha)
        salvar_usuarios(usuarios)
        flash("Senha redefinida com sucesso!", "success")
    return redirect(url_for('login'))
    
@app.route('/perfil')
@login_required
def perfil():
    return render_template('perfil.html')

@app.route('/editar_dados', methods=['GET', 'POST'])
@login_required
def editar_dados():
    if request.method == 'POST':
        usuarios = carregar_usuarios()
        usuarios[current_user.id]['name'] = request.form.get('nome')
        usuarios[current_user.id]['cargo'] = request.form.get('cargo')
        usuarios[current_user.id]['depto'] = request.form.get('departamento')
        salvar_usuarios(usuarios)
        flash("Dados atualizados!", "success")
        return redirect(url_for('perfil'))
    return render_template('editar_dados.html')

@app.route('/alterar_senha', methods=['GET', 'POST'])
@login_required
def alterar_senha():
    if request.method == 'POST':
        senha_atual = request.form.get('senha_atual')
        nova_senha = request.form.get('nova_senha')
        usuarios = carregar_usuarios()
        if not check_password_hash(usuarios[current_user.id]['password'], senha_atual):
            flash("Senha atual incorreta.", "error")
            return redirect(url_for('alterar_senha'))
        usuarios[current_user.id]['password'] = generate_password_hash(nova_senha)
        salvar_usuarios(usuarios)
        flash("Senha alterada!", "success")
        return redirect(url_for('perfil'))
    return render_template('alterar_senha.html')

@app.route('/configuracoes')
@login_required
def configuracoes():
    return render_template('configuracoes.html')      

# --- ROTAS PRINCIPAIS ---
@app.route('/')
@login_required
def index():
    if current_user.role == 'operacional':
        return redirect(url_for('page_operacional'))
    return render_template('index.html')

@app.route('/operacional')
@login_required
def page_operacional():
    return render_template('email_operacional.html')

@app.route('/gerencial')
@login_required
def page_gerencial():
    if current_user.role != 'admin':
        return render_template('403.html'), 403
    return render_template('email_gerencial.html')

@app.route('/gestao/prototipo')
@login_required
def page_gestao_prototipo():
    """Protótipo da Visão Gestão para validação de layout e UX antes da implementação real."""
    return render_template('gestao_prototipo.html')

@app.route('/gerencial/mensal')
@login_required
def page_gerencial_consolidado():
    if current_user.role != 'admin':
        return render_template('403.html'), 403
    return render_template('email_gerencial_consolidado.html')


@app.route('/admin/pipeline')
@login_required
def page_admin_pipeline():
    if current_user.role != 'admin':
        return render_template('403.html'), 403
    return render_template('admin_pipeline.html')


@app.route('/admin/logs')
@login_required
def page_admin_logs():
    if current_user.role != 'admin':
        return render_template('403.html'), 403
    return render_template('admin_logs.html')


@app.route('/api/admin/logs')
@login_required
def api_admin_logs():
    if current_user.role != 'admin':
        return jsonify({'error': 'Acesso negado'}), 403
    import json as _json
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'logs', 'pipeline_runs.json')
    runs = []
    if os.path.exists(log_path):
        try:
            with open(log_path, encoding='utf-8') as f:
                runs = _json.load(f)
            if not isinstance(runs, list):
                runs = []
        except Exception:
            runs = []
    return jsonify({'runs': runs})


# ---------------------------------------------------------------------------
# Gestão de usuários (admin) — adicionado em 2026-05-07.
# Tela: templates/admin_usuarios.html.
# Endpoints:
#   GET   /admin/usuarios                       → renderiza a lista
#   POST  /admin/usuarios/criar                 → cria novo usuário
#   POST  /admin/usuarios/<uid>/editar          → edita (nome/cargo/depto/role/email)
#   POST  /admin/usuarios/<uid>/resetar_senha   → reseta senha (admin define ou
#                                                  sistema gera aleatória — UI escolhe)
#   POST  /admin/usuarios/<uid>/desativar       → toggle ativo/inativo
# ---------------------------------------------------------------------------
@app.route('/admin/usuarios')
@login_required
def page_admin_usuarios():
    if not _so_admin_acessa():
        return render_template('403.html'), 403
    usuarios = carregar_usuarios()
    # Adapta para uma lista de dicts amigável ao template (uid + campos).
    lista = []
    for uid, dados in sorted(usuarios.items(), key=lambda kv: (kv[1].get('name') or kv[0]).lower()):
        lista.append({
            'uid': uid,
            'name': dados.get('name', ''),
            'email': dados.get('email', ''),
            'cargo': dados.get('cargo', ''),
            'depto': dados.get('depto', ''),
            'role': dados.get('role', ''),
            'ativo': bool(dados.get('ativo', True)),
            'eh_voce': uid == getattr(current_user, 'id', ''),
        })
    return render_template(
        'admin_usuarios.html',
        usuarios=lista,
        roles_validos=ROLES_VALIDOS,
    )


@app.route('/admin/usuarios/criar', methods=['POST'])
@login_required
def api_admin_usuarios_criar():
    if not _so_admin_acessa():
        return jsonify({'error': 'forbidden'}), 403
    payload = request.get_json(silent=True) or {}
    nome = (payload.get('name') or '').strip()
    email = (payload.get('email') or '').strip().lower()
    cargo = (payload.get('cargo') or '').strip()
    depto = (payload.get('depto') or '').strip()
    role = (payload.get('role') or '').strip().lower()
    senha = (payload.get('senha') or '').strip()

    if not nome or not email or not role:
        return jsonify({'error': 'Nome, e-mail e perfil são obrigatórios.'}), 400
    if role not in ROLES_VALIDOS:
        return jsonify({'error': f'Perfil inválido. Use um de: {", ".join(ROLES_VALIDOS)}.'}), 400
    if '@' not in email:
        return jsonify({'error': 'E-mail inválido.'}), 400

    usuarios = carregar_usuarios()
    if _email_ja_cadastrado(email, usuarios):
        return jsonify({'error': 'Este e-mail já está cadastrado.'}), 400

    # Senha: se não informada, gera aleatória de 10 chars.
    senha_gerada = ''
    if not senha:
        import secrets, string
        alfabeto = string.ascii_letters + string.digits
        senha = ''.join(secrets.choice(alfabeto) for _ in range(10))
        senha_gerada = senha

    uid = _gerar_uid_unico_para_email(email, usuarios)
    usuarios[uid] = {
        'password': generate_password_hash(senha),
        'role': role,
        'name': nome,
        'cargo': cargo or 'N/A',
        'depto': depto or 'N/A',
        'email': email,
        'ativo': True,
    }
    salvar_usuarios(usuarios)

    # Envia e-mail de boas-vindas com login + senha. A senha em texto vai
    # no corpo do e-mail (mesmo padrão do /recuperar_senha existente);
    # depois o usuário troca em Perfil → Alterar senha.
    ok_email, erro_email = _enviar_email_smtp(
        destino=email,
        assunto="Bem-vindo(a) ao Oráculo 360 — seus dados de acesso",
        corpo_html=_email_template_boas_vindas(nome, email, senha),
    )

    return jsonify({
        'ok': True,
        'uid': uid,
        'senha_gerada': senha_gerada,  # vazio se admin definiu manualmente
        'email_enviado': ok_email,
        'email_erro': '' if ok_email else erro_email,
    })


@app.route('/admin/usuarios/<uid>/editar', methods=['POST'])
@login_required
def api_admin_usuarios_editar(uid):
    if not _so_admin_acessa():
        return jsonify({'error': 'forbidden'}), 403
    usuarios = carregar_usuarios()
    if uid not in usuarios:
        return jsonify({'error': 'Usuário não encontrado.'}), 404

    payload = request.get_json(silent=True) or {}
    nome = (payload.get('name') or '').strip()
    email = (payload.get('email') or '').strip().lower()
    cargo = (payload.get('cargo') or '').strip()
    depto = (payload.get('depto') or '').strip()
    role = (payload.get('role') or '').strip().lower()

    if not nome or not email or not role:
        return jsonify({'error': 'Nome, e-mail e perfil são obrigatórios.'}), 400
    if role not in ROLES_VALIDOS:
        return jsonify({'error': f'Perfil inválido.'}), 400
    if '@' not in email:
        return jsonify({'error': 'E-mail inválido.'}), 400
    if _email_ja_cadastrado(email, usuarios, ignorar_uid=uid):
        return jsonify({'error': 'Já existe outro usuário com este e-mail.'}), 400

    # Auto-proteção: admin não pode rebaixar/desativar a si mesmo a ponto
    # de não conseguir mais entrar. Editar só campos cosméticos é OK.
    if uid == getattr(current_user, 'id', '') and role != 'admin':
        return jsonify({'error': 'Você não pode trocar seu próprio perfil de admin (proteção).'}), 400

    usuarios[uid].update({
        'name': nome,
        'email': email,
        'cargo': cargo or 'N/A',
        'depto': depto or 'N/A',
        'role': role,
    })
    salvar_usuarios(usuarios)
    return jsonify({'ok': True})


@app.route('/admin/usuarios/<uid>/resetar_senha', methods=['POST'])
@login_required
def api_admin_usuarios_resetar_senha(uid):
    if not _so_admin_acessa():
        return jsonify({'error': 'forbidden'}), 403
    usuarios = carregar_usuarios()
    if uid not in usuarios:
        return jsonify({'error': 'Usuário não encontrado.'}), 404

    payload = request.get_json(silent=True) or {}
    senha_nova = (payload.get('senha') or '').strip()

    senha_gerada = ''
    if not senha_nova:
        import secrets, string
        alfabeto = string.ascii_letters + string.digits
        senha_nova = ''.join(secrets.choice(alfabeto) for _ in range(10))
        senha_gerada = senha_nova

    usuarios[uid]['password'] = generate_password_hash(senha_nova)
    salvar_usuarios(usuarios)

    # Notifica o usuário do reset por e-mail (mesma infra SMTP do
    # /recuperar_senha). Falha é silenciosa — devolvemos email_enviado
    # no JSON pra UI exibir feedback.
    ok_email, erro_email = _enviar_email_smtp(
        destino=usuarios[uid].get('email', ''),
        assunto="Sua senha do Oráculo 360 foi resetada",
        corpo_html=_email_template_senha_resetada(
            usuarios[uid].get('name', ''),
            usuarios[uid].get('email', ''),
            senha_nova,
        ),
    )

    return jsonify({
        'ok': True,
        'senha_gerada': senha_gerada,
        'email_enviado': ok_email,
        'email_erro': '' if ok_email else erro_email,
    })


@app.route('/admin/usuarios/<uid>/desativar', methods=['POST'])
@login_required
def api_admin_usuarios_desativar(uid):
    if not _so_admin_acessa():
        return jsonify({'error': 'forbidden'}), 403
    usuarios = carregar_usuarios()
    if uid not in usuarios:
        return jsonify({'error': 'Usuário não encontrado.'}), 404
    # Auto-proteção: não desativar a si mesmo (perderia acesso imediato).
    if uid == getattr(current_user, 'id', ''):
        return jsonify({'error': 'Você não pode desativar a si mesmo.'}), 400

    estado_atual = bool(usuarios[uid].get('ativo', True))
    usuarios[uid]['ativo'] = not estado_atual
    salvar_usuarios(usuarios)
    return jsonify({'ok': True, 'ativo': usuarios[uid]['ativo']})


@app.route('/admin/usuarios/<uid>/excluir', methods=['POST'])
@login_required
def api_admin_usuarios_excluir(uid):
    """Apaga o usuário de vez do JSON (perde histórico). Para apenas
    bloquear acesso preservando o registo, use /desativar."""
    if not _so_admin_acessa():
        return jsonify({'error': 'forbidden'}), 403
    usuarios = carregar_usuarios()
    if uid not in usuarios:
        return jsonify({'error': 'Usuário não encontrado.'}), 404

    # Auto-proteção 1: não excluir a si mesmo.
    if uid == getattr(current_user, 'id', ''):
        return jsonify({'error': 'Você não pode excluir a si mesmo.'}), 400

    # Auto-proteção 2: não deixar o sistema sem nenhum admin ativo (caso
    # contrário ninguém mais conseguiria entrar nesta tela). Conta os
    # admins restantes excluindo o que estamos prestes a apagar.
    if usuarios[uid].get('role') == 'admin':
        admins_restantes = [
            u for k, u in usuarios.items()
            if k != uid and u.get('role') == 'admin' and u.get('ativo', True)
        ]
        if not admins_restantes:
            return jsonify({
                'error': 'Não posso excluir: este é o último admin ativo do sistema.'
            }), 400

    # Confirmação forte: o cliente envia o email para conferir que sabe
    # quem está apagando (proteção contra clique/atalho acidental).
    payload = request.get_json(silent=True) or {}
    email_confirmado = (payload.get('email_confirmado') or '').strip().lower()
    email_real = (usuarios[uid].get('email') or '').strip().lower()
    if not email_confirmado or email_confirmado != email_real:
        return jsonify({
            'error': 'Confirmação não bate: digite exatamente o e-mail do usuário.'
        }), 400

    nome_apagado = usuarios[uid].get('name', '')
    del usuarios[uid]
    salvar_usuarios(usuarios)
    return jsonify({'ok': True, 'nome_apagado': nome_apagado})


@app.route('/api/admin/pipeline/run', methods=['POST'])
@login_required
def api_admin_pipeline_run():
    if current_user.role != 'admin':
        return jsonify({'error': 'Acesso negado'}), 403
    data = request.get_json(force=True, silent=True) or {}
    tipo = (data.get('tipo') or '').strip()

    if tipo == 'deletar':
        jid, err = pipeline_jobs.iniciar_deletar_carga(bool(data.get('backups')))
    elif tipo == 'periodo_unico':
        jid, err = pipeline_jobs.iniciar_periodo_unico(
            data.get('data_ini') or '',
            data.get('data_fim') or '',
        )
    elif tipo == 'lista_dias':
        modo = (data.get('modo') or 'subir').strip().lower()
        jid, err = pipeline_jobs.iniciar_lista_dias(
            data.get('datas') or '',
            modo,
            bool(data.get('incremental')),
            bool(data.get('triagem_todo_o_03')),
        )
    elif tipo == 'limpar_periodo':
        jid, err = pipeline_jobs.iniciar_limpar_periodo(
            data.get('data') or None,
            data.get('data_de') or None,
            data.get('data_ate') or None,
            bool(data.get('preservar_threads_painel')),
        )
    else:
        return jsonify({
            'error': 'tipo inválido; use «deletar», «periodo_unico», «lista_dias» ou «limpar_periodo»',
        }), 400
    if err:
        return jsonify({'error': err}), 400
    return jsonify({'job_id': jid})


@app.route('/api/admin/pipeline/job/<job_id>')
@login_required
def api_admin_pipeline_job(job_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Acesso negado'}), 403
    st = pipeline_jobs.obter_estado(job_id)
    if not st:
        return jsonify({'error': 'Trabalho não encontrado'}), 404
    return jsonify(st)


@app.route('/aprendizados')
@login_required
def page_aprendizados():
    """Página de Aprendizados (threads concluídas — Aprender e Concluir).

    Mantida só para retrocompat de bookmarks; o novo destino é o Painel
    de Gestão. Em algum momento essa rota pode ser removida.
    """
    return render_template('aprendizados.html')


# ===========================================================================
# PAINEL DE GESTÃO — visão executiva pra gestores e diretores.
# (substitui no menu a tela de "Aprendizados", que era um dashboard cru de
#  threads concluídas. Aqui os mesmos dados são agregados em 4 KPIs do topo
#  + 5 painéis de perguntas-chave da gestão.)
# ===========================================================================
@app.route('/painel/gestao')
@login_required
def page_painel_gestao():
    """Renderiza a tela. Os dados vêm via /api/painel_gestao/dados."""
    return render_template('painel_gestao.html')



@app.route('/painel/base-conhecimento-bacen')
@login_required
def page_base_conhecimento_bacen():
    """Base de Conhecimento — críticas reais do BACEN + orientações da Finaud."""
    return render_template('base_conhecimento_bacen.html')


@app.route('/api/ultima_data_carga')
@login_required
def api_ultima_data_carga():
    """Retorna a última data_iso disponível nos eventos do pipeline."""
    try:
        import json as _json
        path = os.path.join('data', 'json', 'pipeline', '03_integrador_dados_site.json')
        with open(path, encoding='utf-8') as f:
            d = _json.load(f)
        datas = sorted(
            (e.get('data_iso', '') for e in d.get('eventos', []) if e.get('data_iso', '')),
            reverse=True
        )
        ultima = datas[0] if datas else None
        return jsonify({'ultima_data': ultima, 'gerado_em': d.get('gerado_em', '')})
    except Exception as e:
        logger.error(f'api_ultima_data_carga: {e}', exc_info=True)
        return jsonify({'ultima_data': None}), 500


@app.route('/api/base_conhecimento_bacen')
@login_required
def api_base_conhecimento_bacen():
    """Retorna os grupos de críticas da base de conhecimento."""
    try:
        from scripts.base_conhecimento_bacen import carregar_base
        dados = carregar_base()
        return jsonify({'grupos': dados, 'total': len(dados)})
    except Exception as e:
        logger.error(f'api_base_conhecimento_bacen: {e}', exc_info=True)
        return jsonify({'erro': str(e)}), 500


ALERTAS_CONFIG = os.path.join('data', 'json', 'config', 'alertas.json')

def _carregar_alertas():
    with open(ALERTAS_CONFIG, encoding='utf-8') as f:
        return json.load(f)

def _salvar_alertas(dados):
    with open(ALERTAS_CONFIG, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


@app.route('/admin/alertas')
@login_required
def page_admin_alertas():
    if not _so_admin_acessa():
        return render_template('403.html'), 403
    cfg = _carregar_alertas()
    return render_template('admin_alertas.html', alertas=cfg['alertas'])


@app.route('/api/admin/alertas', methods=['GET'])
@login_required
def api_alertas_get():
    if not _so_admin_acessa():
        return jsonify({'erro': 'Acesso negado'}), 403
    return jsonify(_carregar_alertas())


@app.route('/api/admin/alertas/<alerta_id>', methods=['POST'])
@login_required
def api_alertas_salvar(alerta_id):
    if not _so_admin_acessa():
        return jsonify({'erro': 'Acesso negado'}), 403
    body = request.get_json(force=True)
    cfg = _carregar_alertas()
    for al in cfg['alertas']:
        if al['id'] == alerta_id:
            if 'ativo' in body:
                al['ativo'] = bool(body['ativo'])
            if 'destinatarios' in body:
                emails = [e.strip() for e in body['destinatarios'] if e.strip()]
                al['destinatarios'] = emails
            break
    else:
        return jsonify({'erro': 'Alerta não encontrado'}), 404
    _salvar_alertas(cfg)
    return jsonify({'ok': True})


@app.route('/api/admin/alertas/<alerta_id>/enviar', methods=['POST'])
@login_required
def api_alertas_enviar(alerta_id):
    if not _so_admin_acessa():
        return jsonify({'erro': 'Acesso negado'}), 403
    cfg = _carregar_alertas()
    alerta = next((a for a in cfg['alertas'] if a['id'] == alerta_id), None)
    if not alerta:
        return jsonify({'erro': 'Alerta não encontrado'}), 404

    destinatarios = alerta.get('destinatarios', [])
    if not destinatarios:
        return jsonify({'erro': 'Nenhum destinatário configurado para este alerta'}), 400

    import smtplib, os as _os
    from email.mime.text import MIMEText as _MIMEText
    from scripts.email_alerta_template import montar_email_alerta, SEVERIDADE

    sev_map = {'critico': SEVERIDADE.CRITICO, 'atencao': SEVERIDADE.ATENCAO, 'informativo': SEVERIDADE.INFO}
    sev = sev_map.get(alerta.get('severidade', 'atencao'), SEVERIDADE.ATENCAO)

    html = montar_email_alerta(
        severidade=sev,
        titulo=alerta['nome'],
        subtitulo=alerta['motivo'],
        corpo_html='<p style="color:#94a3b8;font-size:14px;">Este é um <strong>envio de teste</strong> disparado manualmente pelo painel.</p>',
        rodape_extra=f'Disparado por {getattr(current_user, "name", "administrador")} via painel Oráculo 360',
    )

    # Alertas com lógica própria: delegar ao script específico
    if alerta_id == 'cliente_desconhecido':
        try:
            from html import escape as _esc
            dados = _carregar_json_cached(BASE_DADOS)
            eventos = dados.get('eventos', []) if isinstance(dados, dict) else []
            casos = [
                e for e in eventos
                if (e.get('cliente') or '').strip().upper() in ('CLIENTE_DESCONHECIDO', 'DESCONHECIDO')
            ]
            if not casos:
                return jsonify({'ok': True, 'mensagem': 'Nenhum e-mail com cliente desconhecido encontrado.', 'enviados': []})
            linhas_html = ''.join(
                f"<tr><td style='padding:6px 8px;border-bottom:1px solid #e2e8f0;'>{_esc(c.get('titulo') or '(sem assunto)')}</td>"
                f"<td style='padding:6px 8px;border-bottom:1px solid #e2e8f0;color:#64748b;'>{_esc(c.get('timestamp') or c.get('data_iso') or '')}</td></tr>"
                for c in casos
            )
            corpo = (
                f"<p style='margin:0 0 12px 0;'>Encontrados <strong>{len(casos)} e-mail(s)</strong> "
                f"cujo remetente não foi identificado. Verifique cada caso e cadastre o cliente se necessário.</p>"
                f"<table style='width:100%;border-collapse:collapse;font-size:13px;'>"
                f"<thead><tr>"
                f"<th style='text-align:left;padding:6px 8px;background:#f1f5f9;'>Assunto</th>"
                f"<th style='text-align:left;padding:6px 8px;background:#f1f5f9;'>Data</th>"
                f"</tr></thead><tbody>{linhas_html}</tbody></table>"
            )
            from scripts.email_alerta_template import montar_email_alerta, SEVERIDADE as _SEV
            _html = montar_email_alerta(
                severidade=_SEV.ATENCAO,
                titulo='E-mail com Cliente Desconhecido',
                subtitulo=f'{len(casos)} caso(s) sem remetente identificado',
                corpo_html=corpo,
            )
            erros_cd, enviados_cd = [], []
            for dest in destinatarios:
                _ok, _err = _enviar_email_smtp(dest, f'[ATENÇÃO] E-mail com Cliente Desconhecido — Oráculo 360', _html)
                if _ok:
                    enviados_cd.append(dest)
                else:
                    erros_cd.append(f'{dest}: {_err}')
            if erros_cd and not enviados_cd:
                return jsonify({'erro': ' | '.join(erros_cd)}), 500
            return jsonify({'ok': True, 'enviados': enviados_cd, 'erros': erros_cd,
                            'mensagem': f'{len(casos)} caso(s) — enviado para: {", ".join(enviados_cd)}'})
        except Exception as _ex:
            return jsonify({'erro': str(_ex)[:200]}), 500

    if alerta_id == 'prazo_bacen':
        try:
            from datetime import date as _date, timedelta as _td
            from scripts.verificar_prazos_bacen import buscar_vencimentos, montar_html, enviar as _env_prazo
            _amanha = _date.today() + _td(days=1)
            _venc = buscar_vencimentos(_amanha)
            if not _venc:
                return jsonify({'ok': True, 'mensagem': f'Nenhum prazo vencendo amanhã ({_amanha.strftime("%d/%m/%Y")})', 'enviados': []})
            _html_prazo = montar_html(_venc, _amanha)
            _ok, _err = _env_prazo(_html_prazo, destinatarios, len(_venc), _amanha.strftime('%d/%m/%Y'))
            if _ok:
                return jsonify({'ok': True, 'enviados': destinatarios,
                                'mensagem': f'{len(_venc)} prazo(s) — enviado para: {", ".join(destinatarios)}'})
            return jsonify({'erro': _err}), 500
        except Exception as _ex:
            return jsonify({'erro': str(_ex)[:200]}), 500

    remetente = _os.getenv('EMAIL_USER')
    senha     = _os.getenv('EMAIL_PASS')
    if not remetente or not senha:
        return jsonify({'erro': 'EMAIL_USER / EMAIL_PASS não configurados no servidor'}), 500

    erros = []
    enviados = []
    for dest in destinatarios:
        try:
            msg = MIMEMultipart()
            msg['From']    = remetente
            msg['To']      = dest
            msg['Subject'] = f'[TESTE] {alerta["nome"]} — Oráculo 360'
            msg.attach(_MIMEText(html, 'html'))
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(remetente, senha)
            server.send_message(msg)
            server.quit()
            enviados.append(dest)
        except Exception as exc:
            erros.append(f'{dest}: {str(exc)[:120]}')

    if erros and not enviados:
        return jsonify({'erro': ' | '.join(erros)}), 500
    return jsonify({
        'ok': True,
        'enviados': enviados,
        'erros': erros,
        'mensagem': f'Enviado para: {", ".join(enviados)}' + (f' | Erros: {", ".join(erros)}' if erros else ''),
    })



def _periodo_dias(periodo: str) -> tuple[date, date, date, date]:
    """Resolve um identificador de período em (inicio, fim) e o
    período anterior comparável (inicio_ant, fim_ant) para cálculos
    de delta. Aceita: '7d', '30d', '90d', 'mes_corrente', 'YYYY-MM-DD..YYYY-MM-DD'.
    """
    hoje = datetime.now().date()
    if periodo and ".." in periodo:
        try:
            ini_s, fim_s = periodo.split("..", 1)
            ini = datetime.strptime(ini_s.strip(), "%Y-%m-%d").date()
            fim = datetime.strptime(fim_s.strip(), "%Y-%m-%d").date()
        except Exception:
            ini, fim = hoje - timedelta(days=29), hoje
    elif periodo == "mes_corrente":
        ini = hoje.replace(day=1)
        fim = hoje
    elif periodo == "7d":
        ini, fim = hoje - timedelta(days=6), hoje
    elif periodo == "90d":
        ini, fim = hoje - timedelta(days=89), hoje
    else:  # default 30d
        ini, fim = hoje - timedelta(days=29), hoje
    delta = (fim - ini).days + 1
    fim_ant = ini - timedelta(days=1)
    ini_ant = fim_ant - timedelta(days=delta - 1)
    return ini, fim, ini_ant, fim_ant


def _dt_iso(s: str):
    """Tenta parsear ``data_conclusao`` / ``data_iso`` em formato variado."""
    if not s:
        return None
    s = str(s).strip()[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _filtra_concluidas_por_periodo(concluidas: list, ini, fim) -> list:
    out = []
    for r in concluidas or []:
        if not isinstance(r, dict):
            continue
        d = _dt_iso(r.get('data_conclusao', ''))
        if d and ini <= d <= fim:
            out.append(r)
    return out


def _calcula_kpis_topo(concluidas_periodo: list, concluidas_anterior: list,
                       eventos_03: list, threads_03: list, fora_prazo: list) -> dict:
    """Os 4 KPIs do topo (Painel de Gestão — visão GERAL, todos os cadocs):
    total resolvidos, tempo médio real (calculado de timestamps), fora do
    prazo, e categoria com mais volume.
    """
    total_atual = len(concluidas_periodo)
    total_ant = len(concluidas_anterior)

    def _delta_pct(atual, anterior):
        if not anterior:
            return None
        return round(((atual - anterior) / anterior) * 100, 1)

    # Tempo médio REAL: data_conclusao - primeira mensagem do fio (em horas)
    horas_total = []
    for r in concluidas_periodo:
        h = _calcular_horas_resolucao(
            eventos_03, threads_03,
            str(r.get('threadId') or ''),
            r.get('data_conclusao', ''),
        )
        if h is not None:
            horas_total.append(h)
    tempo_medio_dias = (
        round(sum(horas_total) / len(horas_total) / 24.0) if horas_total else None
    )

    # Categoria com mais volume — usa catálogo oficial (config/categorias.py)
    from collections import Counter
    por_cadoc: Counter = Counter()
    for r in concluidas_periodo:
        alvo = (r.get('alvo_triagem_auto') or '').strip()
        cadoc_raw = (r.get('cadoc') or '').strip()
        display, visivel = categoria_display(alvo, cadoc_raw)
        if visivel and display:
            por_cadoc[display] += 1
    cadoc_top = por_cadoc.most_common(1)[0] if por_cadoc else (None, 0)

    return {
        'total_resolvidos': total_atual,
        'total_resolvidos_delta_pct': _delta_pct(total_atual, total_ant),
        'tempo_medio_dias': tempo_medio_dias,
        'tempo_medio_baseado_em': len(horas_total),  # quantos casos entraram na média
        'fora_do_prazo_qtd': len(fora_prazo),
        'fora_do_prazo_pct': round(len(fora_prazo) / total_atual * 100, 1) if total_atual else 0,
        'cadoc_top_codigo': cadoc_top[0],
        'cadoc_top_qtd': cadoc_top[1],
    }


def _ranking_criticas_bacen(cache_resumos: dict, concluidas_periodo: list) -> list:
    """Painel 1: críticas Bacen com recorrência, clientes, solução típica, tempo médio."""
    from collections import defaultdict
    grupos = defaultdict(lambda: {'qtd': 0, 'clientes': set(), 'solucoes': [], 'documentos': set()})
    for v in (cache_resumos or {}).values():
        if not isinstance(v, dict):
            continue
        resumo = v.get('resumo') or {}
        prob = resumo.get('problema') or {}
        sol = resumo.get('solucao') or {}
        critica = (prob.get('critica') or '').strip()
        if not critica:
            continue
        g = grupos[critica]
        g['qtd'] += 1
        if prob.get('cnpj'):
            g['clientes'].add(prob.get('cnpj'))
        if prob.get('documento'):
            g['documentos'].add(str(prob.get('documento')))
        if sol.get('descricao'):
            g['solucoes'].append(sol.get('descricao')[:160])
    saida = []
    for critica, g in sorted(grupos.items(), key=lambda kv: -kv[1]['qtd']):
        # Solução "típica": pega a mais frequente OU a primeira
        solucao_tipica = ''
        if g['solucoes']:
            from collections import Counter
            mc = Counter(g['solucoes']).most_common(1)
            solucao_tipica = mc[0][0] if mc else g['solucoes'][0]
        saida.append({
            'critica': critica,
            'qtd': g['qtd'],
            'documentos': sorted(g['documentos']),
            'qtd_clientes': len(g['clientes']),
            'solucao_tipica': solucao_tipica,
        })
    return saida[:10]  # Top 10


def _casos_fora_do_prazo(concluidas_periodo: list, eventos_03: list) -> list:
    """Painel 2: thread concluída APÓS o prazo vigente na data de conclusão.

    Para threads com múltiplos prazos (entregas mensais), usa o prazo mais
    recente que já havia vencido quando a thread foi concluída — evita
    atrasos fantasmas de centenas de dias causados pelo uso do prazo mais antigo.
    """
    # Mapa thread -> lista de todos os prazos (do JSON 03)
    prazos_por_tid: dict = {}
    for ev in eventos_03 or []:
        if not isinstance(ev, dict):
            continue
        tid = str(ev.get('threadId') or '')
        lp = ev.get('lista_prazos') or []
        for p in lp:
            if not isinstance(p, dict):
                continue
            raw = (p.get('prazo_limite') or '').strip()
            if not raw:
                continue
            try:
                parts = raw.split("/")
                if len(parts) == 3:
                    d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                    if y < 100:
                        y += 2000
                    prazos_por_tid.setdefault(tid, []).append(date(y, m, d))
            except Exception:
                continue
    out = []
    for r in concluidas_periodo:
        tid = str(r.get('threadId') or '')
        todos_prazos = prazos_por_tid.get(tid)
        d_conc = _dt_iso(r.get('data_conclusao', ''))
        if not todos_prazos or not d_conc:
            continue
        # Prazo vigente = o mais recente que já havia vencido na data de conclusão
        prazos_vencidos = [p for p in todos_prazos if p <= d_conc]
        if not prazos_vencidos:
            continue  # concluída antes de qualquer prazo → não está atrasada
        prazo_vigente = max(prazos_vencidos)
        if d_conc > prazo_vigente:
            atraso = (d_conc - prazo_vigente).days
            ai = r.get('aprendizado_ia') or {}
            out.append({
                'threadId': tid,
                'cliente': ai.get('cliente_identificado', '') or (r.get('empresa') or '').strip(),
                'cadoc': ai.get('cadoc_real', '') or r.get('alvo_triagem_auto', ''),
                'prazo': prazo_vigente.isoformat(),
                'data_conclusao': d_conc.isoformat(),
                'atraso_dias': atraso,
            })
    out.sort(key=lambda x: -x['atraso_dias'])
    return out


def _casos_perto_de_vencer(eventos_03: list, threads_aguardando: list, concluidas_ids: set) -> list:
    """Painel 3: prazos nos próximos 3 dias úteis, ainda não concluídos."""
    from datetime import datetime as _dt
    hoje = _dt.now().date()
    janela_dias = 5  # corridos
    out = []
    aguardando_ids = {str(r.get('threadId')) for r in (threads_aguardando or []) if isinstance(r, dict)}
    for ev in eventos_03 or []:
        if not isinstance(ev, dict):
            continue
        tid = str(ev.get('threadId') or '')
        if tid in concluidas_ids:
            continue
        for p in ev.get('lista_prazos') or []:
            if not isinstance(p, dict):
                continue
            raw = (p.get('prazo_limite') or '').strip()
            if not raw:
                continue
            try:
                parts = raw.split("/")
                if len(parts) == 3:
                    d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                    if y < 100:
                        y += 2000
                    prazo_d = date(y, m, d)
                    dias_ate = (prazo_d - hoje).days
                    if 0 <= dias_ate <= janela_dias:  # vence hoje ou nos próximos 5 dias
                        out.append({
                            'threadId': tid,
                            'cliente': (ev.get('cliente') or '').strip(),
                            'cadoc': (ev.get('cadoc') or '').strip(),
                            'titulo': (ev.get('titulo') or '')[:120],
                            'prazo': prazo_d.isoformat(),
                            'dias_restantes': dias_ate,
                            'em_aguardando': tid in aguardando_ids,
                        })
            except Exception:
                continue
    # Dedup por threadId (mantém o de menor dias_restantes)
    dedup: dict = {}
    for c in out:
        k = c['threadId']
        if k not in dedup or c['dias_restantes'] < dedup[k]['dias_restantes']:
            dedup[k] = c
    out = sorted(dedup.values(), key=lambda x: x['dias_restantes'])
    return out[:10]


def _mapa_usuarios_por_email() -> dict:
    """E-mail (minúsculo) → nome de exibição de cada usuário cadastrado em
    ``usuarios.json``. O cadastro de usuários é a fonte oficial de quem
    aparece nos rankings do Painel de Gestão (decisão de 01/07/2026)."""
    mapa = {}
    for dados in carregar_usuarios().values():
        if not isinstance(dados, dict):
            continue
        email = (dados.get('email') or '').strip().lower()
        if email:
            mapa[email] = (dados.get('name') or '').strip() or email
    return mapa


def _email_quem_respondeu(thread_03, nome_responsavel: str = '') -> str:
    """Descobre, nas mensagens do fio, o e-mail (minúsculo) de quem atuou
    pela Finaud. Se ``nome_responsavel`` vier preenchido, prioriza o contato
    (origem ou destino) com esse nome; senão usa a última mensagem ENVIADA
    pelo lado FINAUD. Devolve '' se não encontrar."""
    if not isinstance(thread_03, dict):
        return ''

    def _norm(s):
        s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode('ascii')
        return ' '.join(s.lower().split())

    alvo = _norm(nome_responsavel)
    ultimo_email, ultimo_ts = '', None
    for m in thread_03.get('mensagens') or []:
        if not isinstance(m, dict):
            continue
        for papel in ('contato_origem', 'contato_destino'):
            c = m.get(papel) or {}
            if not isinstance(c, dict) or (c.get('lado') or '').upper() != 'FINAUD':
                continue
            email = (c.get('email') or '').strip().lower()
            if not email:
                continue
            if alvo and _norm(c.get('nome')) == alvo:
                return email
            if papel == 'contato_origem':
                ts = m.get('timestamp_epoch') or m.get('timestamp')
                if isinstance(ts, (int, float)) and (ultimo_ts is None or ts > ultimo_ts):
                    ultimo_ts, ultimo_email = ts, email
    return ultimo_email


def _ranking_colaboradores(eventos_03: list, threads_03: list,
                            concluidas_periodo: list) -> dict:
    """Painel 4: ranking ÚNICO dos analistas da Finaud — TODOS os cadastrados
    aparecem, inclusive quem não teve caso no período (0 casos). Clientes,
    "Suporte", "Riskdriver" e conta genérica ficam de fora."""
    from collections import defaultdict

    def _norm(s):
        s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode('ascii')
        return ' '.join(s.lower().split())

    mapa_email = _mapa_usuarios_por_email()
    mapa_nome: dict = {}
    todos_analistas: set = set()
    for dados in carregar_usuarios().values():
        if not isinstance(dados, dict):
            continue
        nome = (dados.get('name') or '').strip()
        email = (dados.get('email') or '').strip().lower()
        role = (dados.get('role') or '').strip()
        if not nome or not email:
            continue
        # Só analistas operacionais com e-mail @finaud.com.br
        # (exclui admin, consultores externos e conta genérica)
        if role != 'operacional':
            continue
        if not email.endswith('@finaud.com.br'):
            continue
        mapa_nome[_norm(nome)] = nome
        todos_analistas.add(nome)

    resp_por_tid: dict = {}
    for ev in eventos_03 or []:
        if not isinstance(ev, dict):
            continue
        tid = str(ev.get('threadId') or '')
        if (ev.get('lado_responsavel') or '').upper() == 'FINAUD' and ev.get('responsavel'):
            resp = (ev.get('responsavel') or '').strip()
            cliente = (ev.get('cliente') or '').strip()
            if resp and resp.lower() != cliente.lower():
                resp_por_tid[tid] = resp

    th_por_tid = {str(t.get('threadId') or ''): t
                  for t in threads_03 or [] if isinstance(t, dict)}

    def _analista_cadastrado(tid, resp_nome):
        email = _email_quem_respondeu(th_por_tid.get(tid), resp_nome)
        if email and email in mapa_email:
            return mapa_email[email]
        rn = _norm(resp_nome)
        if rn in mapa_nome:
            return mapa_nome[rn]
        pn = set(rn.split())
        for nn, oficial in mapa_nome.items():
            pc = set(nn.split())
            if pn and (pn <= pc or pc <= pn):
                return oficial
        return None  # não cadastrado → fora do ranking

    stats = defaultdict(lambda: {'casos': 0, 'tempos_horas': []})
    # Inicializa todos os cadastrados para garantir que apareçam mesmo com 0 casos
    for nome in todos_analistas:
        _ = stats[nome]
    for r in concluidas_periodo:
        tid = str(r.get('threadId') or '')
        resp = resp_por_tid.get(tid)
        if not resp:
            continue
        analista = _analista_cadastrado(tid, resp)
        if not analista or analista not in todos_analistas:
            continue
        stats[analista]['casos'] += 1
        h = _calcular_horas_resolucao(
            eventos_03, threads_03, tid, r.get('data_conclusao', ''),
        )
        if h is not None:
            stats[analista]['tempos_horas'].append(h)

    ranking = []
    for nome, s in stats.items():
        media_h = round(sum(s['tempos_horas']) / len(s['tempos_horas']), 1) if s['tempos_horas'] else None
        ranking.append({
            'colaborador': nome,
            'casos': s['casos'],
            'tempo_medio_horas': media_h,
        })
    com_tempo = sorted([r for r in ranking if r['tempo_medio_horas'] is not None],
                       key=lambda x: x['tempo_medio_horas'])
    sem_tempo = sorted([r for r in ranking if r['tempo_medio_horas'] is None],
                       key=lambda x: -x['casos'])
    return {
        'ranking': com_tempo + sem_tempo,  # único: do mais ágil ao mais lento
        'volume_total': sorted(ranking, key=lambda x: -x['casos']),
        'total_colaboradores': len(todos_analistas),
    }


def _assuntos_lentos(concluidas_periodo: list, eventos_03: list, threads_03: list) -> list:
    """Painel 5: tipos de demanda (cadoc) que mais demoraram (tempo real)."""
    from collections import defaultdict
    grupos = defaultdict(lambda: {'casos': 0, 'tempos_horas': []})

    for r in concluidas_periodo:
        alvo = (r.get('alvo_triagem_auto') or '').strip()
        cadoc_raw = (r.get('cadoc') or '').strip()
        display, visivel = categoria_display(alvo, cadoc_raw)
        if not visivel:
            continue
        cadoc = display
        grupos[cadoc]['casos'] += 1
        h = _calcular_horas_resolucao(
            eventos_03, threads_03,
            str(r.get('threadId') or ''),
            r.get('data_conclusao', ''),
        )
        if h is not None:
            grupos[cadoc]['tempos_horas'].append(h)

    saida = []
    for cadoc, g in grupos.items():
        media_h = round(sum(g['tempos_horas']) / len(g['tempos_horas']), 1) if g['tempos_horas'] else None
        saida.append({
            'cadoc': cadoc,
            'casos': g['casos'],
            'tempo_medio_horas': media_h,
        })
    com_tempo = [s for s in saida if s['tempo_medio_horas'] is not None]
    com_tempo.sort(key=lambda x: -x['tempo_medio_horas'])
    return com_tempo[:5]


def _primeira_msg_thread(eventos_03: list, tid: str):
    """Devolve a date da PRIMEIRA mensagem do fio (thread completa).

    Usa o ``timestamp_epoch`` mais antigo do evento que carrega esse tid.
    Retorna ``None`` se não conseguir encontrar nada utilizável.
    """
    if not tid:
        return None
    candidatos_epoch = []
    for ev in eventos_03 or []:
        if not isinstance(ev, dict):
            continue
        if str(ev.get('threadId') or '') != str(tid):
            continue
        # Timestamp do próprio evento
        ts = ev.get('timestamp_epoch')
        if ts:
            try:
                candidatos_epoch.append(int(ts))
            except Exception:
                pass
        # Timestamps das mensagens (varre o JSON 03 procurando o thread)
    # Olha também o objeto ``threads`` do JSON 03 (se carregado)
    return min(candidatos_epoch) if candidatos_epoch else None


def _calcular_horas_resolucao(eventos_03: list, threads_03: list, tid: str,
                              data_conclusao_str: str):
    """Tempo de resolução em HORAS = data_conclusao - data da primeira mensagem do fio.

    Usa data_iso de cada mensagem no integrador (campo confiável gerado pelo script 09).
    Quando timestamp_epoch > 0 está disponível, usa a data extraída dele; caso contrário
    cai para data_iso (YYYY-MM-DD). Devolve None se não conseguir calcular.
    """
    if not tid or not data_conclusao_str:
        return None
    d_conc = _dt_iso(data_conclusao_str)
    if not d_conc:
        return None

    primeira_data = None
    for th in threads_03 or []:
        if not isinstance(th, dict):
            continue
        if str(th.get('threadId') or '') != str(tid):
            continue
        msgs = th.get('mensagens') or []
        datas = []
        for m in msgs:
            if not isinstance(m, dict):
                continue
            # Preferência: timestamp_epoch numérico e positivo
            ts = m.get('timestamp_epoch')
            if isinstance(ts, (int, float)) and ts > 0:
                try:
                    datas.append(datetime.fromtimestamp(int(ts)).date())
                    continue
                except Exception:
                    pass
            # Fallback: data_iso (YYYY-MM-DD) — sempre preenchido pelo script 09
            d_iso = (m.get('data_iso') or '').strip()
            if d_iso:
                d = _dt_iso(d_iso)
                if d:
                    datas.append(d)
        if datas:
            primeira_data = min(datas)
        break  # thread encontrada — para a busca

    if primeira_data is None:
        return None

    delta_dias = (d_conc - primeira_data).days
    if delta_dias <= 0:
        return None
    return round(delta_dias * 24.0, 1)


def _resolver_prazo_bacen(prazo_bacen_llm, data_referencia):
    """Resolve a data limite do BACEN para um caso de Retorno Bacen.

    1. Se o LLM extraiu ``prazo_bacen`` do texto da mensagem (no formato
       ``DD/MM/YYYY``), usa ele.
    2. Caso contrário, soma ``+3 dias úteis`` à ``data_referencia`` (a
       data da mensagem do BACEN).
    """
    if prazo_bacen_llm:
        try:
            s = str(prazo_bacen_llm).strip()
            # Formatos aceitos: DD/MM/YYYY ou YYYY-MM-DD
            if "/" in s:
                p = s.split("/")
                if len(p) == 3:
                    d, m, y = int(p[0]), int(p[1]), int(p[2])
                    if y < 100:
                        y += 2000
                    return date(y, m, d)
            elif "-" in s:
                return _dt_iso(s)
        except Exception:
            pass
    # Fallback: +3 dias úteis a partir da data de referência
    if not data_referencia:
        return None
    try:
        regras = _carregar_regras_prazo() or {}
        feriados = regras.get("feriados") or set()
        return _adicionar_dias_uteis(data_referencia, 3, feriados)
    except Exception:
        return None


@app.route('/api/painel_gestao/dados')
@login_required
def api_painel_gestao_dados():
    """Endpoint que alimenta o Painel de Gestão. Resposta agregada,
    custo computacional baixo (não chama LLM)."""
    periodo = (request.args.get('periodo') or '30d').strip()
    ini, fim, ini_ant, fim_ant = _periodo_dias(periodo)

    # Carrega fontes (com fallback elegante se faltar arquivo)
    def _carrega_json(fp, default):
        try:
            if not os.path.exists(fp):
                return default
            with open(fp, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f'painel_gestao: erro lendo {fp}: {e}')
            return default

    base = os.path.join(BASE_DIR, 'data', 'json', 'pipeline')
    concluidas = _carrega_json(os.path.join(base, 'threads_concluidas_auto.json'), [])

    aguardando = _carrega_json(os.path.join(base, 'threads_aguardando_auto.json'), [])
    cache_resumos = _carrega_json(os.path.join(base, 'cache_resumos_llm.json'), {})
    integ_03 = _carrega_json(os.path.join(base, '03_integrador_dados_site.json'), {})
    eventos_03 = (integ_03.get('eventos') if isinstance(integ_03, dict) else []) or []

    concluidas_periodo = _filtra_concluidas_por_periodo(concluidas, ini, fim)
    concluidas_anterior = _filtra_concluidas_por_periodo(concluidas, ini_ant, fim_ant)

    threads_03 = (integ_03.get('threads') if isinstance(integ_03, dict) else []) or []
    fora_prazo = _casos_fora_do_prazo(concluidas_periodo, eventos_03)
    kpis = _calcula_kpis_topo(concluidas_periodo, concluidas_anterior,
                              eventos_03, threads_03, fora_prazo)
    concluidas_ids = {str(r.get('threadId')) for r in concluidas if isinstance(r, dict)}
    perto_vencer = _casos_perto_de_vencer(eventos_03, aguardando, concluidas_ids)
    colaboradores = _ranking_colaboradores(eventos_03, threads_03, concluidas_periodo)
    assuntos = _assuntos_lentos(concluidas_periodo, eventos_03, threads_03)

    return jsonify({
        'periodo': {
            'codigo': periodo,
            'inicio': ini.isoformat(),
            'fim': fim.isoformat(),
            'inicio_anterior': ini_ant.isoformat(),
            'fim_anterior': fim_ant.isoformat(),
        },
        'kpis': kpis,
        'fora_do_prazo': fora_prazo,
        'perto_de_vencer': perto_vencer,
        'colaboradores': colaboradores,
        'assuntos_lentos': assuntos,
    })


# --- Visão Gestão & Direção (protótipo com dados dos JSON do pipeline) ---
PAPEIS_VISAO_GESTAO_DIRECAO = frozenset({"admin", "gestor", "diretor", "gerencial"})


def _usuario_pode_visao_gestao_direcao():
    return getattr(current_user, "role", None) in PAPEIS_VISAO_GESTAO_DIRECAO


@app.route("/gestao/direcao")
@login_required
def page_gestao_direcao():
    """Dashboard consolidado categoria / prazo / tempo / resoluções (protótipo)."""
    if not _usuario_pode_visao_gestao_direcao():
        return render_template("403.html"), 403
    return render_template("gestao_direcao.html")


@app.route("/api/gestao_direcao")
@login_required
def api_gestao_direcao():
    if not _usuario_pode_visao_gestao_direcao():
        return jsonify({"error": "Acesso negado"}), 403
    try:
        periodo = request.args.get("periodo", "dia")
        ref_q = request.args.get("ref")
        return jsonify(coletar_stats_gestao_direcao(periodo=periodo, ref_iso=ref_q))
    except Exception as exc:
        logger.exception("gestao_direcao")
        return jsonify({"error": str(exc)}), 500


def _parse_data_ref(data_raw):
    """Converte parâmetro data (YYYY-MM-DD ou DD/MM/YYYY) em date. Retorna None se inválido."""
    if not data_raw or not isinstance(data_raw, str):
        return None
    s = data_raw.strip()[:10]
    if not s:
        return None
    try:
        if '-' in s and len(s) >= 10:
            return datetime.strptime(s[:10], '%Y-%m-%d').date()
        if '/' in s:
            parts = s.split('/')
            if len(parts) >= 3:
                d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                if y < 100:
                    y += 2000
                return date(y, m, d)
    except (ValueError, TypeError):
        pass
    try:
        return parser.parse(s, dayfirst=True).date()
    except Exception:
        return None


def _data_civil_em_registro(valor):
    """Extrai ``date`` de ``data_conclusao`` / ``data_marcacao`` (YYYY-MM-DD ou prefixo ISO)."""
    if not valor:
        return None
    s = str(valor).strip()
    if not s:
        return None
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    return _parse_data_ref(s[:10] if len(s) >= 10 else s)


def _evento_concluido_operacional(e):
    """
    True se o caso deve ser tratado como encerrado na API/UI (Fog CLOSED, CONCLUÍDO do integrador, etc.).
    Evita listar ticket Fog fechado em Pendentes só porque status != 'concluido'.
    """
    if not isinstance(e, dict):
        return False
    st = (e.get('status') or '').strip().lower()
    if st in ('concluido', 'closed', 'resolved', 'fechado'):
        return True
    sp = (e.get('status_processo') or '').strip().upper().replace('Í', 'I')
    if sp in ('CONCLUIDO', 'CLOSED', 'RESOLVED', 'FECHADO'):
        return True
    return False


def _extrair_data_msg(msg):
    """Extrai data (date) de uma mensagem a partir de data_iso, timestamp ou data_email."""
    for campo in ('data_iso', 'timestamp', 'data_email'):
        val = (msg.get(campo) or '').strip()
        if not val:
            continue
        dt = _parse_dt_rapido(val, dayfirst=True)
        if dt is not None:
            return dt.date()
    return None


def _ordenar_mensagens_operacional_para_acao(mensagens):
    """Ordem cronológica das mensagens (mesma ideia do 04 / modal) para achar a última do fio."""

    def _sort_key(m):
        if not isinstance(m, dict):
            return datetime.min
        for campo in ("data_email", "data_iso", "timestamp"):
            val = (m.get(campo) or "").strip()
            if not val:
                continue
            dt = _parse_dt_rapido(val, dayfirst=True)
            if dt is not None:
                return dt
        return datetime.min

    if not mensagens:
        return []
    return sorted(mensagens, key=_sort_key)


def _str_strip_seguro(val):
    """Evita AttributeError quando o JSON traz nome/e-mail/responsável como número ou outro tipo."""
    if val is None:
        return ""
    try:
        return str(val).strip()
    except Exception:
        return ""


def _nome_contato_dict_seguro(d):
    if not isinstance(d, dict):
        return ""
    n = _str_strip_seguro(d.get("nome"))
    if n:
        return n
    em = _str_strip_seguro(d.get("email"))
    if em and "@" in em:
        return em.split("@")[0]
    return ""


def _excecao_obrigada_pelo_envio_ultima(ultima):
    """Finaud agradece recebimento → bola permanece na Finaud (remetente), alinhado ao 04."""
    if not isinstance(ultima, dict):
        return False
    co = ultima.get("contato_origem") or {}
    if _str_strip_seguro(co.get("lado")).upper() != "FINAUD":
        return False
    blob = ultima.get("corpo_limpo") or ultima.get("corpo") or ultima.get("corpo_texto")
    corpo = _str_strip_seguro(blob).lower()
    return (
        "obrigada pelo envio" in corpo
        or "obrigado pelo envio" in corpo
    )


def _responsavel_pela_acao_from_mensagens(mensagens, fallback_responsavel=""):
    """
    Quem deve agir agora, a partir do último fio (lados origem→destino).
    C→F → destinatário Finaud; F→F → destinatário Finaud; F→C → contato cliente.
    Exceção: «obrigada/obrigado pelo envio» com origem Finaud → remetente Finaud.
    O campo legado ``responsavel`` (contraparte / 02) permanece; este valor alimenta o card.
    """
    fb = _str_strip_seguro(fallback_responsavel)
    if not mensagens or not isinstance(mensagens, list):
        return fb
    ordenados = _ordenar_mensagens_operacional_para_acao(
        [m for m in mensagens if isinstance(m, dict)]
    )
    if not ordenados:
        return fb
    ultima = ordenados[-1]
    co = ultima.get("contato_origem") or {}
    cd = ultima.get("contato_destino") or {}
    o_lado = _str_strip_seguro(co.get("lado")).upper()
    d_lado = _str_strip_seguro(cd.get("lado")).upper()

    if _excecao_obrigada_pelo_envio_ultima(ultima):
        nome = _nome_contato_dict_seguro(co)
        return nome or fb

    if o_lado == "CLIENTE":
        nome = _nome_contato_dict_seguro(cd)
        return nome or fb

    if o_lado == "FINAUD" and d_lado == "FINAUD":
        nome = _nome_contato_dict_seguro(cd)
        return nome or fb

    if o_lado == "FINAUD" and d_lado == "CLIENTE":
        nome = _nome_contato_dict_seguro(cd)
        if nome:
            return nome
        raw_rv = ultima.get("responsavel")
        if raw_rv in (None, ""):
            raw_rv = ultima.get("responsavel_nome")
        msg_fb = _str_strip_seguro(raw_rv)
        return msg_fb or fb

    return fb


def _filtrar_evento_por_data(evento, dt_limite):
    """
    Retorna cópia do evento com mensagens filtradas: só as com data <= dt_limite.
    Igual ao Gmail: no dia 23 mostra 1 msg, no dia 24 mostra 2 msgs (23+24).
    """
    ev = dict(evento)
    msgs = ev.get('mensagens') or []
    if not msgs:
        return ev
    # Mensagens sem data parseável: incluir (conservador)
    filtradas = [m for m in msgs if (_extrair_data_msg(m) or datetime.min.date()) <= dt_limite]
    ev['mensagens'] = filtradas
    ev['qtd_mensagens'] = len(filtradas)
    return ev


def _fingerprint_lista_prazos_operacional(lista):
    """
    Identidade dos prazos do card: cadoc + data_base + prazo_limite (strings como no JSON).
    Mesma regra validada manualmente para os pares Fair 4111 e Trustee DDR_2011.
    """
    if not lista or not isinstance(lista, list):
        return None
    tuplas = []
    for x in lista:
        if not isinstance(x, dict):
            continue
        c = (x.get('cadoc') or '').strip()
        db = (x.get('data_base') or '').strip()
        pl = (x.get('prazo_limite') or '').strip()
        if not c:
            continue
        tuplas.append((c, db, pl))
    if not tuplas:
        return None
    return frozenset(tuplas)


def _empresa_chave_par_operacional(empresa):
    """Chave alinhada ao campo empresa do card (API); ignora desconhecido/vazio."""
    s = (empresa or '').strip().lower()
    if len(s) < 2:
        return None
    if s in ('desconhecido', 'cliente_desconhecido', 'sem empresa identificada', 'n/a', '—'):
        return None
    return s


def _buckets_empresa_prazos_operacional(eventos_visao):
    """
    Agrupa threadId pelo evento mais recente por fio: chave (empresa API normalizada, fingerprint lista_prazos).
    Usado em pares sugeridos (buckets de 2) e clusters multi-thread (3+).
    """
    por_tid = {}
    for e in eventos_visao:
        if not isinstance(e, dict):
            continue
        tid = e.get('threadId')
        if not tid:
            continue
        ts = e.get('timestamp_epoch')
        if ts is None:
            ts = 0
        ts2 = e.get('timestamp') or ''
        prev = por_tid.get(tid)
        if prev is None or (ts, ts2) > (prev.get('timestamp_epoch') or 0, prev.get('timestamp') or ''):
            por_tid[tid] = e

    buckets = {}
    for tid, ev in por_tid.items():
        emp_k = _empresa_chave_par_operacional(ev.get('empresa'))
        fp = _fingerprint_lista_prazos_operacional(ev.get('lista_prazos'))
        if not emp_k or fp is None:
            continue
        key = (emp_k, fp)
        buckets.setdefault(key, []).append((tid, ev))
    return buckets


def _computar_pares_sugeridos_operacional(eventos_visao):
    """
    Sugere pares de threads distintos: mesma empresa (API) + mesma lista_prazos (fingerprint).
    Só buckets com exatamente 2 threads (evita ambiguidade). Não usa cliente cru quando empresa inválida.
    """
    buckets = _buckets_empresa_prazos_operacional(eventos_visao)

    out = {}
    for _key, lst in buckets.items():
        if len(lst) != 2:
            continue
        (tid_a, ev_a), (tid_b, ev_b) = lst
        if tid_a == tid_b:
            continue

        def _entrada(ev, outro_tid):
            tit = (ev.get('titulo') or ev.get('assunto') or '')[:220]
            return {
                'threadId': outro_tid,
                'id': str(ev.get('id') or ''),
                'titulo': tit,
            }

        out.setdefault(tid_a, []).append(_entrada(ev_b, tid_b))
        out.setdefault(tid_b, []).append(_entrada(ev_a, tid_a))
    return out


def _computar_clusters_multi_thread_operacional(eventos_visao):
    """
    Buckets com 3 ou mais threadId distintos (mesma empresa API + mesmo fingerprint lista_prazos).
    Fase 1 de automação: exposto na API / UI para revisão — não funde threads sozinho.
    """
    buckets = _buckets_empresa_prazos_operacional(eventos_visao)
    clusters = []
    for (emp_k, fp), lst in buckets.items():
        if len(lst) < 3:
            continue
        prazos_serial = [
            {'cadoc': a, 'data_base': b, 'prazo_limite': c}
            for a, b, c in sorted(fp, key=lambda t: (t[0], t[1], t[2]))
        ]
        lst_ord = sorted(lst, key=lambda x: x[0])
        threads_payload = []
        for tid, ev in lst_ord:
            tit = (ev.get('titulo') or ev.get('assunto') or '')[:220]
            threads_payload.append({
                'threadId': tid,
                'id': str(ev.get('id') or ''),
                'titulo': tit,
            })
        clusters.append({
            'empresa_chave': emp_k,
            'lista_prazos': prazos_serial,
            'thread_ids': [t[0] for t in lst_ord],
            'threads': threads_payload,
            'n_threads': len(lst_ord),
        })
    return clusters


def _normalizar_par_thread_ids(ta, tb):
    a, b = str(ta or ''), str(tb or '')
    if a > b:
        a, b = b, a
    return a, b


def _carregar_pares_confirmados_list():
    if not os.path.exists(ARQUIVO_PARES_THREADS_CONFIRMADOS):
        return []
    try:
        with open(ARQUIVO_PARES_THREADS_CONFIRMADOS, 'r', encoding='utf-8') as f:
            dados = json.load(f)
        return dados if isinstance(dados, list) else []
    except Exception as e:
        logger.error(f'Erro ao carregar pares confirmados: {e}')
        return []


def _salvar_pares_confirmados_list(lista):
    os.makedirs(os.path.dirname(ARQUIVO_PARES_THREADS_CONFIRMADOS), exist_ok=True)
    with open(ARQUIVO_PARES_THREADS_CONFIRMADOS, 'w', encoding='utf-8') as f:
        json.dump(lista, f, indent=2, ensure_ascii=False)


def _mapa_pares_confirmados_para_api(lista_pares):
    """threadId -> outroThreadId (bidirecional)."""
    m = {}
    for r in lista_pares:
        if not isinstance(r, dict):
            continue
        ta, tb = r.get('thread_a'), r.get('thread_b')
        if not ta or not tb or ta == tb:
            continue
        m[ta] = tb
        m[tb] = ta
    return m


def _contar_tids_dedup_par_confirmado(tids, mapa_par):
    """
    Cada par confirmado presente em tids (ambos os lados) conta como um só.
    Usado no KPI threads_em_monitoramento quando as duas threads do par têm monitorar_resposta.
    """
    if not tids:
        return 0
    s = set(tids)
    consumed = set()
    n = 0
    for tid in s:
        if tid in consumed:
            continue
        ot = (mapa_par or {}).get(tid)
        if ot and ot in s:
            consumed.add(tid)
            consumed.add(ot)
            n += 1
        else:
            consumed.add(tid)
            n += 1
    return n


def _remover_par_confirmado(lista_pares, ta, tb):
    na, nb = _normalizar_par_thread_ids(ta, tb)
    return [
        r for r in lista_pares
        if not isinstance(r, dict)
        or _normalizar_par_thread_ids(r.get('thread_a'), r.get('thread_b')) != (na, nb)
    ]


def _representativo_thread_para_par(thread_id, dados_json, aguardando_lista):
    """Último evento da thread com enriquecimento igual à API (empresa no card)."""
    eventos = dados_json.get('eventos', []) if isinstance(dados_json, dict) else []
    threads_lista = dados_json.get('threads', []) if isinstance(dados_json, dict) else []
    mapa_threads = {t.get('threadId'): t.get('mensagens', []) for t in threads_lista if t.get('threadId')}
    mapa_thread_responsavel = {
        t.get('threadId'): t.get('responsavel')
        for t in threads_lista
        if t.get('threadId') and (t.get('responsavel') or '').strip()
    }
    best = None
    for e in eventos:
        if not isinstance(e, dict) or e.get('threadId') != thread_id:
            continue
        if e.get('cadoc') in ('IGNORADO',):
            continue
        if e.get('relatorio_interno_risk_driver'):
            continue
        assunto = (e.get('titulo') or e.get('assunto') or '').lower()
        if 'relatório do serviço' in assunto or 'atualização de comunicados' in assunto:
            continue
        ts = e.get('timestamp_epoch')
        if ts is None:
            ts = 0
        ts2 = e.get('timestamp') or ''
        if best is None or (ts, ts2) > (best.get('timestamp_epoch') or 0, best.get('timestamp') or ''):
            best = dict(e)
    if not best:
        return None
    tid = best.get('threadId')
    if tid in mapa_threads:
        best['mensagens'] = mapa_threads[tid]
    if tid in mapa_thread_responsavel:
        best['responsavel'] = mapa_thread_responsavel[tid]
    reg_ag = next((r for r in aguardando_lista if isinstance(r, dict) and r.get('threadId') == tid), None)
    if reg_ag and not best.get('empresa'):
        emp_reg = (reg_ag.get('empresa') or '').strip()
        if not emp_reg:
            motivo = (reg_ag.get('motivo') or '')
            m = re.search(
                r'(?:da|de)\s+([A-Za-zÀ-ÿ\s]+?)(?:\s+sobre|\s+ref\.|\.|$)', motivo, re.I
            )
            if m:
                emp_reg = m.group(1).strip()
        if emp_reg:
            best['empresa'] = emp_reg
    _aplicar_fallback_cliente_encaminhamento_interno_api(best)
    if best.pop("_painel_preservar_empresa_responsavel_fallback", False):
        best["empresa"] = _rotulo_empresa_gestao_para_api((best.get("empresa") or "Finaud").strip())
    else:
        best["empresa"] = _rotulo_empresa_gestao_para_api(_empresa_gestao_final(best))
    return best


def _threads_elegiveis_para_confirmar_par(ta, tb):
    if not ta or not tb or ta == tb:
        return False, 'threadId e outroThreadId obrigatórios e devem ser diferentes.'
    dados = carregar_json(BASE_DADOS)
    ag_lista = _carregar_threads_aguardando()
    ea = _representativo_thread_para_par(ta, dados, ag_lista)
    eb = _representativo_thread_para_par(tb, dados, ag_lista)
    if not ea or not eb:
        return False, 'Thread sem evento elegível no integrador.'
    ka = _empresa_chave_par_operacional(ea.get('empresa'))
    kb = _empresa_chave_par_operacional(eb.get('empresa'))
    if not ka or ka != kb:
        return False, 'Empresa do card difere entre as threads — não é possível confirmar o par.'
    fa = _fingerprint_lista_prazos_operacional(ea.get('lista_prazos'))
    fb = _fingerprint_lista_prazos_operacional(eb.get('lista_prazos'))
    if fa is None or fb is None or fa != fb:
        return False, 'Lista de prazos (categoria/datas) difere — não é possível confirmar o par.'
    return True, ''


def _qtd_mensagens_thread_integrador(thread_id):
    dados = carregar_json(BASE_DADOS)
    for t in dados.get('threads') or []:
        if isinstance(t, dict) and t.get('threadId') == thread_id:
            return len(t.get('mensagens') or [])
    return 0


def _carregar_eventos_fog():
    """Carrega casos Fog do script 05 (massa_bruta_fog.json). Fallback: eventos com origem FogBugz no BASE_DADOS."""
    if os.path.exists(ARQUIVO_FOG):
        try:
            with open(ARQUIVO_FOG, 'r', encoding='utf-8') as f:
                lista = json.load(f)
            if isinstance(lista, list) and lista:
                return lista
        except Exception:
            pass
    dados_brutos = carregar_json(BASE_DADOS)
    eventos = dados_brutos.get('eventos', []) if isinstance(dados_brutos, dict) else dados_brutos or []
    return [e for e in eventos if e.get('origem') == 'FogBugz']


def _resumo_fog_ativos_criticos(eventos):
    """Conta casos do FOG ativos (não fechados) e críticos (15+ dias sem novidade).
    Usada por /fog/gerencial e /api/fog_resumo_dia — mesma regra nas duas telas."""
    total_ativos = 0
    total_critico = 0
    hoje = datetime.now()
    for e in eventos:
        try:
            data_raw = e.get('data_iso') or e.get('data') or ''
            dt = datetime.strptime(data_raw[:10], '%Y-%m-%d') if 'T' in data_raw else datetime.strptime(data_raw[:10], '%d/%m/%Y')
            idade = (hoje - dt).days
        except Exception:
            idade = 0
        is_ativo = "fechado" not in str(e.get('conteudo') or e.get('status', '')).lower()
        if is_ativo:
            total_ativos += 1
            if idade >= 15:
                total_critico += 1
    return total_ativos, total_critico


def _chat_por_fog() -> dict:
    """Retorna dict {fog_id: [mensagens ordenadas cronologicamente]} lendo massa_bruta_chat.json.
    Detecta menções via 'FOG NNNNN' ou URL fogbugz.com/f/cases/NNNNN."""
    import re as _re
    chat_path = os.path.join(os.path.dirname(ARQUIVO_FOG), 'massa_bruta_chat.json')
    if not os.path.exists(chat_path):
        return {}
    try:
        with open(chat_path, encoding='utf-8') as f:
            msgs = json.load(f)
    except Exception:
        return {}
    pad_fog = _re.compile(r'\bFOG\s+(\d{4,6})\b', _re.I)
    pad_url = _re.compile(r'fogbugz\.com/f/cases/(\d{4,6})', _re.I)
    por_fog: dict = {}
    for m in msgs:
        texto = m.get('texto') or ''
        ids_encontrados = set(pad_fog.findall(texto)) | set(pad_url.findall(texto))
        data_raw = m.get('data') or ''
        # Formatar para DD/MM/YYYY HH:MM
        try:
            from datetime import datetime as _dt, timezone as _tz
            dt = _dt.fromisoformat(data_raw.replace('Z', '+00:00'))
            dt_br = dt.astimezone(_tz(timedelta(hours=-3)))
            data_fmt = dt_br.strftime('%d/%m/%Y %H:%M')
            data_sort = dt_br.strftime('%Y%m%d%H%M')
        except Exception:
            data_fmt = data_raw[:16]
            data_sort = data_raw[:16]
        for fid in ids_encontrados:
            por_fog.setdefault(fid, []).append({
                'autor':      m.get('autor') or '?',
                'data':       data_fmt,
                'data_sort':  data_sort,
                'texto':      texto,
            })
    # Ordenar cada lista cronologicamente
    for fid in por_fog:
        por_fog[fid].sort(key=lambda x: x['data_sort'])
    return por_fog


@app.route('/api/fog_resumo_dia')
@login_required
def api_fog_resumo_dia():
    """Resumo do FOG para a tela inicial: casos ativos e críticos (mesma regra de /fog/gerencial)."""
    try:
        eventos = _carregar_eventos_fog()
        ativos, criticos = _resumo_fog_ativos_criticos(eventos)
        return jsonify({"ativos": ativos, "criticos": criticos})
    except Exception as e:
        logger.error(f"api_fog_resumo_dia: {e}", exc_info=True)
        return jsonify({"ativos": None, "criticos": None}), 500


@app.route('/fog/operacional')
@login_required
def fog_operacional_page():
    eventos = _carregar_eventos_fog()
    ativos_fog = buscar_usuarios_ativos_fog()
    tarefas_tecnicas = []
    hoje = datetime.now()
    for e in eventos:
        responsavel_real = extrair_usuario_real(e)
        try:
            data_raw = e.get('data_iso') or e.get('data') or ''
            dt = datetime.strptime(data_raw[:10], '%Y-%m-%d') if 'T' in data_raw else datetime.strptime(data_raw[:10], '%d/%m/%Y')
            e['idade_dias'] = (hoje - dt).days
        except Exception:
            e['idade_dias'] = 0
        e['responsavel_exibicao'] = responsavel_real
        tarefas_tecnicas.append(e)
    tarefas_tecnicas.sort(key=lambda x: x.get('idade_dias', 0), reverse=True)
    chat_por_fog = _chat_por_fog()
    return render_template('fog_operacional.html', tarefas=tarefas_tecnicas, ativos_fog=ativos_fog, chat_por_fog=chat_por_fog)
    
@app.route('/fog/gerencial')
@login_required 
def fog_gerencial_page():
    if current_user.role != 'admin':
        return render_template('403.html'), 403
    eventos = _carregar_eventos_fog()
    ativos_fog = buscar_usuarios_ativos_fog()
    ranking_responsaveis = {}
    total_ativos, total_critico = _resumo_fog_ativos_criticos(eventos)
    total_atencao = total_recentes = total_concluidos = 0
    hoje = datetime.now()
    for e in eventos:
        resp = extrair_usuario_real(e)
        try:
            data_raw = e.get('data_iso') or e.get('data') or ''
            dt = datetime.strptime(data_raw[:10], '%Y-%m-%d') if 'T' in data_raw else datetime.strptime(data_raw[:10], '%d/%m/%Y')
            idade = (hoje - dt).days
        except Exception:
            idade = 0
        is_ativo = "fechado" not in str(e.get('conteudo') or e.get('status', '')).lower()
        if is_ativo:
            if idade < 15:
                if idade >= 8: total_atencao += 1
                else: total_recentes += 1
            if resp not in ranking_responsaveis:
                ranking_responsaveis[resp] = {"dias_acumulados": 0, "tickets": 0, "criticos": 0}
            ranking_responsaveis[resp]["dias_acumulados"] += idade
            ranking_responsaveis[resp]["tickets"] += 1
            if idade >= 8: ranking_responsaveis[resp]["criticos"] += 1
        else:
            total_concluidos += 1
    total_ativos_denom = total_ativos or 1
    stats = {
        "total_ativos": total_ativos,
        "total_concluidos": total_concluidos,
        "ranking": ranking_responsaveis,
        "recentes": {"qtd": total_recentes, "perc": round((total_recentes / total_ativos_denom) * 100, 1)},
        "atencao": {"qtd": total_atencao, "perc": round((total_atencao / total_ativos_denom) * 100, 1)},
        "critico": {"qtd": total_critico, "perc": round((total_critico / total_ativos_denom) * 100, 1)},
    }
    return render_template('fog_gerencial.html', stats=stats)


def _patch_cadoc_desde_cartao_overrides(eventos_lista, threads_lista, overrides: dict) -> None:
    """Aplica cadoc manual antes do filtro FILTRADO_POR_DATA (para o fio voltar à lista)."""
    if not overrides:
        return
    for e in eventos_lista:
        if not isinstance(e, dict):
            continue
        tid = e.get("threadId")
        if not tid:
            continue
        ov = overrides.get(tid)
        if not isinstance(ov, dict):
            continue
        c = (ov.get("cadoc") or "").strip()
        if c:
            e["cadoc"] = c
            e["secao_operacional"] = c
    for t in threads_lista:
        if not isinstance(t, dict):
            continue
        tid = t.get("threadId")
        if not tid:
            continue
        ov = overrides.get(tid)
        if not isinstance(ov, dict):
            continue
        c = (ov.get("cadoc") or "").strip()
        if c:
            t["cadoc"] = c
            t["secao_operacional"] = c


def _aplicar_cartao_overrides_nos_sets(
    overrides: dict,
    concluidos_set: set,
    aguardando_set: set,
    concluida_qtd_msg: dict,
    mapa_threads: dict,
) -> None:
    """Ajusta sets de concluído/aguardando conforme override manual (painel_estado)."""
    if not overrides:
        return
    for tid, ov in overrides.items():
        if not tid or not isinstance(ov, dict):
            continue
        st = (ov.get("status") or "").strip().lower()
        if not st:
            continue
        nmsg = len((mapa_threads or {}).get(tid) or [])
        if st == "concluido":
            concluidos_set.add(tid)
            aguardando_set.discard(tid)
            concluida_qtd_msg[tid] = nmsg
        elif st == "aguardando":
            aguardando_set.add(tid)
            concluidos_set.discard(tid)
        elif st in ("aberto", "pendente", "aberta"):
            concluidos_set.discard(tid)
            aguardando_set.discard(tid)
            concluida_qtd_msg.pop(tid, None)


def _bucket_prazo_cumprido_aprendizado(txt):
    """Agrupa respostas livres do campo prazo_cumprido (aprendizado)."""
    t = (txt or "").strip().lower()
    if not t:
        return "sem_informação"
    if "não se aplica" in t or "nao se aplica" in t or "nao aplic" in t:
        return "não_se_aplica"
    # "também" contém substring " não " — só depois dos casos especiais acima:
    if t.startswith("não") or t.startswith("nao"):
        return "não_cumprido"
    if t.startswith("sim") or ("cumprido" in t and "não" not in t and "nao" not in t):
        return "cumprido"
    return "outros"


def _parse_ref_gestao_direcao(ref_iso: str | None) -> date:
    if not ref_iso or not str(ref_iso).strip():
        return date.today()
    try:
        return datetime.strptime(str(ref_iso).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return date.today()


def _intervalo_gestao_direcao(ref: date, periodo: str | None) -> tuple[date, date]:
    """Devolve (início, fim) inclusivos para o filtro de período do painel Direção."""
    p = (periodo or "dia").strip().lower()
    if p in ("d", "dia", "diario", "day", "daily"):
        return ref, ref
    if p in ("s", "semana", "sem", "weekly"):
        return ref - timedelta(days=6), ref
    if p in ("m", "mes", "mensal", "month", "monthly"):
        ld = calendar.monthrange(ref.year, ref.month)[1]
        return date(ref.year, ref.month, 1), date(ref.year, ref.month, ld)
    return ref, ref


def _max_data_mensagens(msgs) -> date | None:
    mx = None
    for m in msgs or []:
        if not isinstance(m, dict):
            continue
        d = _extrair_data_msg(m)
        if d and (mx is None or d > mx):
            mx = d
    return mx


def _mensagens_thread_integrador(tid: str, map_msgs: dict, por_tid_ev: dict) -> list:
    ms = map_msgs.get(tid) or []
    if ms:
        return ms
    ev = por_tid_ev.get(tid)
    return (ev.get("mensagens") or []) if isinstance(ev, dict) else []


def _cadoc_rotulo_como_chip_operacional(cadoc: str | None, *, retorno_bacen: bool = False) -> str:
    """Espelho de ``mapCadocInternoParaCategoriaExibicao`` / chips do operacional."""
    if retorno_bacen or (cadoc or "").strip().upper() == "RETORNO_BACEN":
        return "RETORNO BACEN"
    c = (cadoc or "").strip()
    if not c:
        return "—"
    u = c.upper()
    curto = {
        "DDR_2011": "DDR",
        "DRM_2060": "DRM",
        "DLO_2061": "DLO",
        "DLI_2062": "DLI",
        "DRL_2160": "DRL",
        "4111": "4111",
        "RETORNO_BACEN": "RETORNO BACEN",
        "SUPORTE": "SUPORTE",
        "SUPORTE_GERAL": "SUPORTE",
        "S5": "S5",
        "DRSAC": "DRSAC",
        "FORCAPITAL": "FORCAPITAL",
        "RISK_DRIVER_ALERTA": "RD Alertas",
        "RISK_DRIVER_RELATORIO": "RD Relatório",
        "RISK_DRIVER_RESP_AUTO": "RD Resp. Auto",
        "FOGBUGZ": "FogBugz",
        "LEIAUTES_BACEN": "Leiautes BACEN",
    }
    return curto.get(u, c)


def _ascii_fold_lower(s: str) -> str:
    """Minusculizado sem acentos — compara nome do card ao ``name`` dos utilizadores."""
    t = unicodedata.normalize("NFD", (s or "").strip())
    return "".join(ch for ch in t if unicodedata.category(ch) != "Mn").lower()


def _nomes_equipe_finaud_from_usuarios() -> frozenset[str]:
    out: list[str] = []
    if os.path.isfile(F_USUARIOS):
        try:
            with open(F_USUARIOS, encoding="utf-8") as fh:
                udict = json.load(fh)
            if isinstance(udict, dict):
                for _uid, ud in udict.items():
                    if isinstance(ud, dict):
                        n = (ud.get("name") or "").strip()
                        if n:
                            out.append(n.lower())
        except (OSError, json.JSONDecodeError):
            pass
    return frozenset(out)


def _lista_nomes_exibicao_usuarios_finaud() -> list[str]:
    """Nomes como em ``usuarios.json`` — para igualdade e prefixo (nome completo do Gmail)."""
    out: list[str] = []
    if os.path.isfile(F_USUARIOS):
        try:
            with open(F_USUARIOS, encoding="utf-8") as fh:
                udict = json.load(fh)
            if isinstance(udict, dict):
                for _uid, ud in udict.items():
                    if isinstance(ud, dict):
                        n = (ud.get("name") or "").strip()
                        if n:
                            out.append(n)
        except (OSError, json.JSONDecodeError):
            pass
    return out


def _nome_gestacao_corresponde_a_utilizadores(nome_dec: str, refs: list[str]) -> bool:
    """Igual direto, igual sem acento, ou prefixo («Andrea» nas definições vs «Andrea Maria …» na API)."""
    nome_l = nome_dec.strip().lower()
    nome_f = _ascii_fold_lower(nome_dec)
    for ref in refs:
        rl = (ref or "").strip().lower()
        if not rl:
            continue
        rf = _ascii_fold_lower(ref)
        if nome_l == rl or nome_f == rf:
            return True
        if len(rl) >= 4 and nome_l.startswith(rl + " "):
            return True
        if len(rf) >= 4 and nome_f.startswith(rf + " "):
            return True
        # referência longa («Nome Sobrenome») quando o campo veio apenas com o primeiro token
        if len(rl) >= 8 and rl.startswith(nome_l + " "):
            return True
        if len(rf) >= 8 and rf.startswith(nome_f + " "):
            return True
    return False


def _dominio_correio_institucional_finaud(email: str | None) -> bool:
    """Apenas e-mail institucional Finaud (domínio finaud.com / finaud.com.br), não cliente nem genéricos."""
    if not email or "@" not in str(email):
        return False
    dom = str(email).strip().lower().rsplit("@", 1)[-1]
    if _dominio_eh_generico(dom):
        return False
    if dom == "finaud.com.br" or dom.endswith(".finaud.com.br"):
        return True
    if dom == "finaud.com" or dom.endswith(".finaud.com"):
        return True
    return False


def _email_contato_finaud_para_responsavel(nome_resp: str | None, mensagens: list | None) -> str:
    """Últimas mensagens primeiro: contacto lado FINAUD cujo nome casa com ``responsável pela ação``."""
    nome_dec = _nome_responsavel_gestacao_decodificado(nome_resp).strip()
    if not nome_dec:
        return ""
    ordenados = _ordenar_mensagens_operacional_para_acao([m for m in (mensagens or []) if isinstance(m, dict)])
    for msg in reversed(ordenados):
        if not isinstance(msg, dict):
            continue
        for ck in ("contato_origem", "contato_destino"):
            ct = msg.get(ck)
            if not isinstance(ct, dict):
                continue
            if _str_strip_seguro(ct.get("lado")).upper() != "FINAUD":
                continue
            nome_c = _str_strip_seguro(ct.get("nome"))
            if not nome_c:
                continue
            if not _nome_gestacao_corresponde_a_utilizadores(nome_dec, [nome_c]):
                continue
            em = _str_strip_seguro(ct.get("email"))
            if em and "@" in em:
                return em.strip().lower()
    return ""


def _colab_secao_equipe_gestacao_direcao(nome_resp: str | None, mensagens: list | None) -> bool:
    """
    Inclui o cartão na secção «Equipe Finaud» como o operacional (`responsável pela ação`), com:
    última mensagem que não deixa só a bola com o cliente (F→C); e comprovado e-mail institucional Finaud
    para esse responsável nos contactos FINAUD do fio.
    """
    nome = _nome_responsavel_gestacao_decodificado(nome_resp).strip()
    nome_l = nome.lower()
    if not nome_l or nome_l in ("não atribuído", "nao atribuído", "—"):
        return False

    ordenados = _ordenar_mensagens_operacional_para_acao([m for m in (mensagens or []) if isinstance(m, dict)])
    if not ordenados:
        return False

    ult = ordenados[-1]
    if not _excecao_obrigada_pelo_envio_ultima(ult):
        co = _str_strip_seguro((ult.get("contato_origem") or {}).get("lado")).upper()
        cd = _str_strip_seguro((ult.get("contato_destino") or {}).get("lado")).upper()
        if co == "FINAUD" and cd == "CLIENTE":
            return False

    em = _email_contato_finaud_para_responsavel(nome_resp, mensagens)
    return bool(em) and _dominio_correio_institucional_finaud(em)


def _nome_responsavel_gestacao_decodificado(nome_resp: str | None) -> str:
    """Remove cabeçalhos MIME (=?UTF-8?Q?...?=) que por vezes vêm no próximo contacto."""
    s = (nome_resp or "").strip()
    if not s or "=?" not in s:
        return s
    try:
        chunks: list[str] = []
        for part, enc in email_decode_header(s):  # type: ignore[arg-type]
            if isinstance(part, bytes):
                chunks.append(part.decode(enc or "utf-8", errors="replace"))
            else:
                chunks.append(str(part))
        return " ".join(chunks).strip()
    except Exception:
        return s


def _peer_reciproco_sugeridos_dashboard(tid: str, par_sugeridos: dict | None) -> str | None:
    tid = str(tid or "").strip()
    if not tid or not isinstance(par_sugeridos, dict):
        return None
    sugs = par_sugeridos.get(tid)
    if not isinstance(sugs, list) or len(sugs) != 1:
        return None
    r0 = sugs[0]
    ot = str((r0 or {}).get("threadId") or "").strip()
    if not ot:
        return None
    back = par_sugeridos.get(ot)
    if not isinstance(back, list) or len(back) != 1:
        return None
    if str((back[0] or {}).get("threadId") or "").strip() != tid:
        return None
    return ot


def _peer_para_dedup_gestacao_dashboard(tid: str, par_sugeridos: dict | None, mapa_confirmados: dict | None) -> str | None:
    p = _peer_reciproco_sugeridos_dashboard(tid, par_sugeridos)
    if p:
        return p
    mc = mapa_confirmados if isinstance(mapa_confirmados, dict) else {}
    ot = mc.get(str(tid).strip())
    if ot and str(mc.get(str(ot).strip()) or "").strip() == str(tid).strip():
        return str(ot).strip()
    return None


def _canonical_tid_par_dashboard(tida: str, tidb: str, ev_a: dict, ev_b: dict) -> str:
    """Mesma regra do operacional para card fundido: título mais longo; empate → lexicográfico."""

    def _tit_len(ev: dict) -> int:
        return len((ev.get("titulo") or ev.get("assunto") or "")[:500])

    la, lb = _tit_len(ev_a), _tit_len(ev_b)
    if lb != la:
        return tidb if lb > la else tida
    return tida if tida < tidb else tidb


def _iter_casos_operacional_dedup_gestacao(
    ev_por_tid: dict,
    par_sugeridos: dict | None,
    mapa_confirmados: dict | None,
):
    """Alinha contagens ao KPI do operacional (``latestPorCasoOperacionalDedupPar``)."""
    todos = {str(k).strip() for k in ev_por_tid.keys() if k}
    consumido: set[str] = set()
    for tid in list(ev_por_tid.keys()):
        tid = str(tid).strip()
        if not tid or tid in consumido:
            continue
        peer = _peer_para_dedup_gestacao_dashboard(tid, par_sugeridos, mapa_confirmados)
        if peer and peer in todos:
            consumido.add(tid)
            consumido.add(peer)
            ev_a = ev_por_tid.get(tid) or {}
            ev_b = ev_por_tid.get(peer) or {}
            can = _canonical_tid_par_dashboard(tid, peer, ev_a, ev_b)
            yield can, ev_por_tid.get(can) or ev_a, peer
        else:
            consumido.add(tid)
            yield tid, ev_por_tid[tid], None


def coletar_stats_gestao_direcao(periodo: str | None = None, ref_iso: str | None = None):
    """
    Agrega integrador + concluídas + aguardando para painel Gestão/Direção.
    Cada card = um fio (e-mail/conversa). Estados: pendente, aguardando, concluído.
    Filtro temporal: dia (data ref), semana (7 dias até ref), mês civil de ref.
    """
    ref = _parse_ref_gestao_direcao(ref_iso)
    d_ini, d_fim = _intervalo_gestao_direcao(ref, periodo)

    meta: dict = {
        "ref": ref.isoformat(),
        "periodo": (periodo or "dia").strip().lower(),
        "intervalo_ini": d_ini.isoformat(),
        "intervalo_fim": d_fim.isoformat(),
    }
    erro = None
    integ: dict = {}
    if os.path.isfile(F_INTEGRADOR):
        try:
            with open(F_INTEGRADOR, encoding="utf-8") as fh:
                integ = json.load(fh)
        except Exception as ex:
            erro = str(ex)
            integ = {}
    else:
        erro = "Integrador não encontrado"

    meta["integrador_gerado_em"] = integ.get("gerado_em") if isinstance(integ, dict) else None
    eventos = integ.get("eventos") if isinstance(integ, dict) else []
    if not isinstance(eventos, list):
        eventos = []
    threads_lista = integ.get("threads") if isinstance(integ, dict) else []
    if not isinstance(threads_lista, list):
        threads_lista = []

    cartao_overrides = load_cartao_overrides() or {}
    _patch_cadoc_desde_cartao_overrides(eventos, threads_lista, cartao_overrides)

    # Último evento por threadId (mesma regra que pares / visual operacional)
    por_tid_ev: dict = {}
    for ev in eventos:
        if not isinstance(ev, dict):
            continue
        tid = str(ev.get("threadId") or "").strip()
        if not tid:
            continue
        ts = ev.get("timestamp_epoch")
        if ts is None:
            ts = 0
        ts2 = ev.get("timestamp") or ""
        prev = por_tid_ev.get(tid)
        if prev is None or (ts, ts2) > (prev.get("timestamp_epoch") or 0, prev.get("timestamp") or ""):
            por_tid_ev[tid] = ev

    map_thread_obj = {str(t.get("threadId") or "").strip(): t for t in threads_lista if isinstance(t, dict) and t.get("threadId")}
    map_msgs: dict = {}
    for tid, t in map_thread_obj.items():
        map_msgs[tid] = t.get("mensagens") or []

    # Datas de aguardando e conclusão por fio
    ag_list = load_aguardando() or []
    data_marcacao_ag: dict = {}
    for r in ag_list:
        if not isinstance(r, dict):
            continue
        tid = str(r.get("threadId") or "").strip()
        if not tid:
            continue
        dm = _data_civil_em_registro(r.get("data_marcacao"))
        if dm:
            prev = data_marcacao_ag.get(tid)
            data_marcacao_ag[tid] = max(dm, prev) if prev else dm

    conc_list = load_concluidas() or []
    dedupe: dict = {}
    for r in conc_list:
        if not isinstance(r, dict):
            continue
        tid = str(r.get("threadId") or "").strip()
        if not tid:
            continue
        dc = _data_civil_em_registro(r.get("data_conclusao"))
        dedupe.setdefault(tid, []).append((dc, r))

    data_conclusao_tid: dict = {}
    tempo_ms_por_tid: dict = {}
    concluida_qtd_msg: dict = {}
    for tid, registos in dedupe.items():
        registos.sort(key=lambda x: (x[0] or date.min), reverse=True)
        r = registos[0][1]
        dc = registos[0][0]
        if dc:
            data_conclusao_tid[tid] = dc
        tms = r.get("tempo_total_ms")
        if tms is not None:
            try:
                tempo_ms_por_tid[tid] = int(tms)
            except (TypeError, ValueError):
                pass
        try:
            concluida_qtd_msg[tid] = int(r.get("qtd_mensagens_no_fechamento") or 0)
        except (TypeError, ValueError):
            concluida_qtd_msg[tid] = 0

    concluidos_set = set(dedupe.keys())
    aguardando_set = {str(x.get("threadId") or "").strip() for x in ag_list if isinstance(x, dict) and x.get("threadId")}

    _aplicar_cartao_overrides_nos_sets(
        cartao_overrides,
        concluidos_set,
        aguardando_set,
        concluida_qtd_msg,
        map_msgs,
    )

    def _classificar_status(tid: str) -> str:
        if tid in concluidos_set:
            return "concluido"
        ev = por_tid_ev.get(tid)
        if ev and _evento_concluido_operacional(ev):
            return "concluido"
        if tid in aguardando_set:
            return "aguardando"
        return "pendente"

    def _ultima_msg_dt(tid: str) -> date | None:
        msgs = _mensagens_thread_integrador(tid, map_msgs, por_tid_ev)
        return _max_data_mensagens(msgs)

    def _thread_no_periodo(tid: str) -> bool:
        u = _ultima_msg_dt(tid)
        if u and d_ini <= u <= d_fim:
            return True
        dc = data_conclusao_tid.get(tid)
        if dc and d_ini <= dc <= d_fim:
            return True
        da = data_marcacao_ag.get(tid)
        if da and d_ini <= da <= d_fim:
            return True
        return False

    periodo_norm = (periodo or "dia").strip().lower()
    usa_visao_identica_operacional = periodo_norm in ("d", "dia", "diario", "day", "daily")

    union_tids = set(por_tid_ev.keys()) | set(map_msgs.keys())
    scoped_tids = {tid for tid in union_tids if _thread_no_periodo(tid)}

    contagem_status = {"pendente": 0, "aguardando": 0, "concluido": 0}
    contagem_cad: dict = {}
    por_colab: dict = {}
    ev_por_tid: dict = {}

    if usa_visao_identica_operacional:
        from painel_operacional_snapshot import (  # noqa: WPS433 pylint: disable=import-outside-toplevel
            estado_cartao_de_evento_enriquecido,
            montagem_api_dados_snapshot,
        )

        meta["alinhado_operacional_visao_diaria"] = True
        snap = montagem_api_dados_snapshot(
            copy.deepcopy(integ),
            ref.isoformat(),
            busca_ativa=False,
            modo_leitura_gestacao=True,
        )
        if snap.get("error"):
            erro = erro or snap.get("error") or ""
            pl_snap = {}
        elif snap.get("early_flat"):
            pl_snap = {}
        else:
            pl_snap = snap.get("payload") or {}

        hoje_snap = list(pl_snap.get("hoje") or [])
        acum_snap = list(pl_snap.get("acumulado") or [])
        nr_snap = list(pl_snap.get("nao_resolvidos_eventos") or [])
        for lst_snap in (hoje_snap, acum_snap, nr_snap):
            for raw_ev in lst_snap:
                if not isinstance(raw_ev, dict):
                    continue
                tid_sv = raw_ev.get("threadId")
                if not tid_sv:
                    continue
                if raw_ev.get("canal") == "Fog" or raw_ev.get("origem") == "FogBugz":
                    continue
                ev_por_tid[str(tid_sv).strip()] = raw_ev

        par_sg = pl_snap.get("pares_sugeridos") if isinstance(pl_snap, dict) else None
        par_cf = pl_snap.get("pares_confirmados") if isinstance(pl_snap, dict) else None

        for caso_tid, raw_ev, outro_tid in _iter_casos_operacional_dedup_gestacao(ev_por_tid, par_sg, par_cf):
            if not isinstance(raw_ev, dict):
                continue
            st = estado_cartao_de_evento_enriquecido(raw_ev)
            if st in contagem_status:
                contagem_status[st] += 1
            rb = bool(raw_ev.get("retorno_bacen"))
            cad_lab = _cadoc_rotulo_como_chip_operacional(str(raw_ev.get("cadoc") or "").strip(), retorno_bacen=rb)
            contagem_cad[cad_lab] = contagem_cad.get(cad_lab, 0) + 1
            nk_raw = (raw_ev.get("responsavel_pela_acao") or "").strip() or "Não atribuído"
            nk = _nome_responsavel_gestacao_decodificado(nk_raw) or nk_raw
            msgs_sv = raw_ev.get("mensagens") or []
            if _colab_secao_equipe_gestacao_direcao(nk_raw, msgs_sv if isinstance(msgs_sv, list) else []):
                entrada = por_colab.setdefault(nk[:120], {"pendente": 0, "aguardando": 0, "concluido": 0, "tempos_min": []})
                entrada[st] = entrada.get(st, 0) + 1
                if st == "concluido":
                    tms = tempo_ms_por_tid.get(caso_tid)
                    if tms is None and outro_tid:
                        tms = tempo_ms_por_tid.get(outro_tid)
                    if tms is not None:
                        entrada["tempos_min"].append(tms / 60000.0)
    else:
        for tid in scoped_tids:
            st = _classificar_status(tid)
            if st in contagem_status:
                contagem_status[st] += 1
            ev = por_tid_ev.get(tid)
            tobj = map_thread_obj.get(tid)
            fb = ""
            if isinstance(tobj, dict):
                fb = _str_strip_seguro(tobj.get("responsavel"))
            msgs = _mensagens_thread_integrador(tid, map_msgs, por_tid_ev)
            resp = _responsavel_pela_acao_from_mensagens(msgs, fb) or ""
            nk = _str_strip_seguro(resp) or "Não atribuído"

            cad_raw = ""
            if isinstance(ev, dict):
                cad_raw = (ev.get("cadoc") or ev.get("secao_operacional") or "").strip()
            if not cad_raw and isinstance(tobj, dict):
                cad_raw = (tobj.get("cadoc") or "").strip()
            rb = bool(ev.get("retorno_bacen")) if isinstance(ev, dict) else False
            cad_lab = _cadoc_rotulo_como_chip_operacional((cad_raw or "—")[:120], retorno_bacen=rb)

            contagem_cad[cad_lab] = contagem_cad.get(cad_lab, 0) + 1

            nk_disp = _nome_responsavel_gestacao_decodificado(nk) or nk
            if _colab_secao_equipe_gestacao_direcao(nk, msgs):
                entrada = por_colab.setdefault((nk_disp or nk)[:120], {"pendente": 0, "aguardando": 0, "concluido": 0, "tempos_min": []})
                entrada[st] = entrada.get(st, 0) + 1
                if st == "concluido" and tid in tempo_ms_por_tid:
                    entrada["tempos_min"].append(tempo_ms_por_tid[tid] / 60000.0)

    if usa_visao_identica_operacional:
        scoped_tids = set(ev_por_tid.keys())

    n_scope = sum(contagem_status.values()) or 0
    demanda_cards = sorted(
        (
            {
                "categoria": k,
                "cards": v,
                "percent_do_total": round(100.0 * v / n_scope, 1) if n_scope else 0.0,
            }
            for k, v in contagem_cad.items()
        ),
        key=lambda x: -x["cards"],
    )[:28]

    colaboradores_linhas = []
    for nome in sorted(
        por_colab.keys(),
        key=lambda n: -(por_colab[n].get("pendente", 0) + por_colab[n].get("aguardando", 0) + por_colab[n].get("concluido", 0)),
    ):
        e = por_colab[nome]
        tlist = e.get("tempos_min") or []
        media = round(sum(tlist) / len(tlist), 1) if tlist else None
        if media is not None and not math.isfinite(float(media)):
            media = None
        pe = int(e.get("pendente", 0) or 0)
        agc = int(e.get("aguardando", 0) or 0)
        conc = int(e.get("concluido", 0) or 0)
        colaboradores_linhas.append(
            {
                "colaborador": nome[:72],
                "pendente": pe,
                "aguardando": agc,
                "concluido": conc,
                "total_cartoes_periodo": pe + agc + conc,
                "tempo_medio_min_concluidos": media,
                "casos_medidos_tempo": len(tlist),
            }
        )

    # --- Legacy / detalhes (concluídas globais dedupe por fio para prazos) ---
    prazo_buckets = {
        "cumprido": 0,
        "não_cumprido": 0,
        "não_se_aplica": 0,
        "sem_informação": 0,
        "outros": 0,
    }
    tempo_acc = []
    tempo_por_cat: dict = {}
    concluids_unicos_global = len(dedupe)
    for tid, registos in dedupe.items():
        registos.sort(key=lambda x: (x[0] or date.min), reverse=True)
        r = registos[0][1]
        ai = r.get("aprendizado_ia") if isinstance(r.get("aprendizado_ia"), dict) else {}
        cad = (ai.get("cadoc_real") or ai.get("tipo_demanda") or "—").strip() or "—"
        b = _bucket_prazo_cumprido_aprendizado(ai.get("prazo_cumprido"))
        if b not in prazo_buckets:
            b = "outros"
        prazo_buckets[b] += 1
        tms = r.get("tempo_total_ms")
        if tms is not None:
            try:
                ms = int(tms)
                tempo_acc.append(ms)
                tempo_por_cat.setdefault(cad, []).append(ms)
            except (TypeError, ValueError):
                pass

    def _media_ms(lista):
        if not lista:
            return None
        return int(sum(lista) / len(lista))

    tempo_global_min = None
    if tempo_acc:
        tempo_global_min = round(sum(tempo_acc) / len(tempo_acc) / 60000.0, 1)
        if not math.isfinite(float(tempo_global_min)):
            tempo_global_min = None

    tempo_cat_rows = []
    for cat, lista in sorted(tempo_por_cat.items(), key=lambda x: -len(x[1]))[:16]:
        m = _media_ms(lista)
        mm = round(m / 60000.0, 1) if m is not None else None
        if mm is not None and not math.isfinite(float(mm)):
            mm = None
        tempo_cat_rows.append(
            {
                "categoria": cat[:48] + ("…" if len(cat) > 48 else ""),
                "amostras": len(lista),
                "media_minutos": mm,
            }
        )

    res_samples = []

    def _snippet_ai(ai):
        if not isinstance(ai, dict):
            return ""
        for campo in ("resolucao_final", "resumo_desfecho", "resumo_interacoes"):
            s = ai.get(campo)
            if isinstance(s, str) and s.strip():
                x = " ".join(s.strip().split())[:280]
                return x + ("…" if len(s.strip()) > 280 else "")
        return ""

    todas_linhas = []
    for tid, registos in dedupe.items():
        _, rmax = registos[0]
        todas_linhas.append((registos[0][0] or date.min, tid, rmax))
    todas_linhas.sort(key=lambda x: x[0], reverse=True)

    for _d, tid, r in todas_linhas[:25]:
        ai = r.get("aprendizado_ia") if isinstance(r.get("aprendizado_ia"), dict) else {}
        sn = _snippet_ai(ai)
        if not sn:
            continue
        cad = (ai.get("cadoc_real") or "—").strip() or "—"
        res_samples.append(
            {
                "threadId": tid[:40],
                "categoria": cad[:40],
                "data_conclusao": (str(r.get("data_conclusao") or "")[:19]),
                "resolucao_snippet": sn,
            }
        )

    threads_ev = {str(ev.get("threadId") or "").strip() for ev in eventos if isinstance(ev, dict) and ev.get("threadId")}

    payload = {
        "meta": {
            **meta,
            "erro_leitura": erro,
            "eventos_total": len(eventos),
            "threads_distintas_eventos": len(threads_ev),
            "fios_concluidos_unicos": concluids_unicos_global,
            "cards_no_periodo": n_scope,
        },
        "painel_cards": {
            "total_cards_periodo": n_scope,
            "pendente": contagem_status["pendente"],
            "aguardando": contagem_status["aguardando"],
            "concluido": contagem_status["concluido"],
            "categorias_percent_total": demanda_cards,
            "colaboradores": colaboradores_linhas[:40],
        },
        "kpis": {
            "casos_na_base_integrador_eventos": len(eventos),
            "threads_aparecem_no_integrador": len(threads_ev),
            "em_aguardando_marcacao": sum(1 for x in ag_list if isinstance(x, dict) and x.get("threadId")),
            "fios_em_concluidas": concluids_unicos_global,
        },
        "demanda_por_categoria": demanda_cards,
        "concluidos_por_categoria": sorted(
            ({"categoria": k, "fios": v} for k, v in contagem_cad.items()),
            key=lambda x: -x["fios"],
        )[:24],
        "prazo_declarado_fechamento": prazo_buckets,
        "tempo": {
            "media_total_minutos_fechamento": tempo_global_min,
            "por_categoria": tempo_cat_rows,
        },
        "resolucoes_amostra": res_samples[:18],
        "avisos": [
            "Cada cartão na base corresponde a uma conversa de e-mail. O período filtra fios com última mensagem, conclusão ou marcação «aguardando» nessa janela.",
            "Indicadores de prazo na conclusão vêm do registo operacional ao fechar o caso.",
        ],
    }
    return payload


@app.route('/api/dados')
@login_required  
def api_dados():
    logger.info("🔍 API_DADOS - Requisição recebida")
    data_filtro_raw = request.args.get('data')
    busca_ativa = request.args.get('busca') == '1'  # Quando busca ativa, incluir FILTRADO_POR_DATA e retornar tudo

    try:
        # Normaliza a chave de cache (None → "" para tratar igual)
        data_norm = (data_filtro_raw or "").strip()

        payload_cached = _payload_cache_get(data_norm, busca_ativa)
        if payload_cached is not None:
            logger.info(f"✅ CACHE HIT payload /api/dados data={data_norm!r} busca={busca_ativa}")
            return jsonify(payload_cached)

        dados_json = _carregar_json_cached(BASE_DADOS)
        from painel_operacional_snapshot import montagem_api_dados_snapshot  # noqa: WPS433 pylint: disable=import-outside-toplevel

        snap = montagem_api_dados_snapshot(
            dados_json,
            data_filtro_raw,
            busca_ativa=busca_ativa,
            modo_leitura_gestacao=False,
        )
        err = snap.get("error")
        if err:
            sc = int(snap.get("status_code") or 400)
            return jsonify({
                "error": err,
                "hoje": [],
                "acumulado": [],
                "pares_confirmados": {},
                "clusters_multi_thread": [],
            }), sc
        payload = snap.get("payload") or {}
        _payload_cache_set(data_norm, busca_ativa, payload)
        return jsonify(payload)

    except Exception as e:
        logger.error(f"❌ ERRO API_DADOS: {e}", exc_info=True)
        return jsonify({
            "error": str(e),
            "hoje": [],
            "acumulado": [],
            "clusters_multi_thread": [],
        }), 500

@app.route('/api/threads_concluidos')
@login_required
def api_threads_concluidos():
    """Retorna lista de threadIds já concluídos (Aprender e Concluir) para o front desabilitar o botão."""
    try:
        lista = _carregar_threads_concluidas()
        ids = [r.get('threadId') for r in lista if isinstance(r, dict) and r.get('threadId')]
        return jsonify({"threadIds": ids})
    except Exception as e:
        return jsonify({"threadIds": []}), 500

@app.route('/api/aprendizados')
@login_required
def api_aprendizados():
    """Retorna dados agregados de threads concluídas para a tela de Aprendizados (dias, tipo_demanda)."""
    try:
        dias = int(request.args.get('dias', 30))
        tipo_demanda = (request.args.get('tipo_demanda') or '').strip()
        lista = _carregar_threads_concluidas()
        hoje = datetime.now().date()
        dt_limite = hoje - timedelta(days=dias)

        filtrados = []
        for r in lista:
            if not isinstance(r, dict) or not r.get('threadId'):
                continue
            data_str = (r.get('data_conclusao') or '')[:10]
            if not data_str:
                continue
            try:
                dt = datetime.strptime(data_str, '%Y-%m-%d').date()
            except Exception:
                continue
            if dt < dt_limite:
                continue
            ai = r.get('aprendizado_ia') or {}
            if tipo_demanda:
                td = (ai.get('tipo_demanda') or '').strip()
                if td != tipo_demanda:
                    continue
            filtrados.append(r)

        # Agregações
        prazo_geral = {"sim": 0, "não": 0, "nao": 0, "parcial": 0, "não se aplica": 0}
        por_tipo = {}
        por_cliente = {}
        resolucoes_por_tipo = {}
        gerou_fog_total = 0
        ultimos_flat = []

        for r in filtrados:
            ai = r.get('aprendizado_ia') or {}
            prazo = (ai.get('prazo_cumprido') or '').strip().lower()
            if prazo:
                prazo_geral[prazo] = prazo_geral.get(prazo, 0) + 1
            else:
                prazo_geral["não se aplica"] = prazo_geral.get("não se aplica", 0) + 1

            td = (ai.get('tipo_demanda') or 'OUTROS').strip()
            por_tipo[td] = por_tipo.get(td, {"total": 0})
            por_tipo[td]["total"] += 1

            cliente = (ai.get('cliente_identificado') or 'Não identificado').strip()
            por_cliente[cliente] = por_cliente.get(cliente, 0) + 1

            if ai.get('gerou_fog') in (True, 'true', 1, '1'):
                gerou_fog_total += 1

            res = (ai.get('resolucao_final') or '').strip()
            if res:
                if td not in resolucoes_por_tipo:
                    resolucoes_por_tipo[td] = []
                resolucoes_por_tipo[td].append(res)

            ultimos_flat.append({
                "threadId": r.get('threadId'),
                "data_conclusao": r.get('data_conclusao', ''),
                "cliente_identificado": cliente,
                "tipo_demanda": td,
                "prazo_cumprido": (ai.get('prazo_cumprido') or 'n/a').strip(),
                "gerou_fog": ai.get('gerou_fog') in (True, 'true', 1, '1'),
                "resolucao_final": res,
                "resumo_desfecho": (ai.get('resumo_desfecho') or '').strip(),
                "cadoc_real": (ai.get('cadoc_real') or '').strip(),
            })

        # Ordenar últimos por data (mais recente primeiro)
        ultimos_flat.sort(key=lambda x: (x.get('data_conclusao') or ''), reverse=True)
        ultimos_flat = ultimos_flat[:100]

        # Normalizar prazo_geral: "nao" -> "não"
        prazo_norm = {
            "sim": prazo_geral.get("sim", 0),
            "não": prazo_geral.get("não", 0) + prazo_geral.get("nao", 0),
            "parcial": prazo_geral.get("parcial", 0),
            "não se aplica": prazo_geral.get("não se aplica", 0),
        }

        return jsonify({
            "total_threads": len(filtrados),
            "prazo_cumprido_geral": prazo_norm,
            "gerou_fog_total": gerou_fog_total,
            "por_cliente": por_cliente,
            "por_tipo_demanda": por_tipo,
            "ultimos_aprendizados": ultimos_flat,
            "resolucoes_por_tipo": resolucoes_por_tipo,
        })
    except Exception as e:
        logger.error(f"api_aprendizados: {e}", exc_info=True)
        return jsonify({"error": str(e), "total_threads": 0, "ultimos_aprendizados": []}), 500

@app.route('/api/aprendizado/editar', methods=['POST'])
@login_required
def api_aprendizado_editar():
    """Atualiza campos do aprendizado_ia de uma thread concluída (threadId)."""
    dados = request.get_json() or {}
    thread_id = dados.get('threadId')
    if not thread_id:
        return jsonify({"status": "error", "message": "threadId é obrigatório"}), 400

    campos_editaveis = {
        'resumo_desfecho', 'resolucao_final', 'cliente_identificado',
        'prazo_cumprido', 'tipo_demanda', 'gerou_fog', 'cadoc_real', 'maior_tempo_espera'
    }
    updates = {k: v for k, v in dados.items() if k in campos_editaveis and k != 'threadId'}

    if not updates:
        return jsonify({"status": "error", "message": "Nenhum campo editável enviado"}), 400

    lista = _carregar_threads_concluidas()
    encontrado = False
    for r in lista:
        if isinstance(r, dict) and str(r.get('threadId')) == str(thread_id):
            ai = r.setdefault('aprendizado_ia', {})
            for k, v in updates.items():
                if k == 'gerou_fog':
                    ai[k] = v in (True, 'true', 1, '1', 'sim')
                else:
                    ai[k] = v if v is not None else ''
            encontrado = True
            break

    if not encontrado:
        return jsonify({"status": "error", "message": "Thread não encontrada em concluídas"}), 404

    try:
        _salvar_threads_concluidas(lista)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/threads')
@login_required
def api_threads():
    try:
        if not os.path.exists(BASE_DADOS): return jsonify({"threads": []})
        dados = _carregar_json_cached(BASE_DADOS)
        threads = dados.get('threads', []) if isinstance(dados, dict) else []
        resumos = dados.get('resumos_estruturados') or {} if isinstance(dados, dict) else {}
        return jsonify({"threads": threads, "resumos_estruturados": resumos})
    except Exception as e:
        return jsonify({"error": str(e), "threads": []}), 500

@app.route('/api/crd_indicio_qualidade')
@login_required
def api_crd_indicio_qualidade():
    """JSON exportado a partir de indício-qualidade.xlsx (aba Indício) — coluna Mensagem e metadados por protocolo."""
    try:
        from paths import F_CRD
        path = F_CRD
        if not os.path.isfile(path):
            path = os.path.join(PASTA_DADOS, 'crd_indicio_qualidade.json')
        if os.path.isfile(path):
            with open(path, 'r', encoding='utf-8') as f:
                return jsonify(json.load(f))
        return jsonify({"fonte": "", "aba": "Indício", "linhas": []})
    except Exception as e:
        return jsonify({"error": str(e), "linhas": []}), 500

@app.route('/api/concluir_item', methods=['POST'])
@login_required
def concluir_item():
    dados_input = request.get_json()
    item_id = dados_input.get('id')
    justificativa_analista = dados_input.get('justificativa')
    
    dados_brutos = carregar_json(BASE_DADOS)
    # Se for dict (formato novo), pegamos a lista de eventos para atualizar
    is_dict_format = isinstance(dados_brutos, dict)
    eventos = dados_brutos.get('eventos', []) if is_dict_format else dados_brutos
    
    item_concluido = None
    for e in eventos:
        if str(e.get('id')) == str(item_id):
            e['status_processo'] = 'CONCLUÍDO'
            e['justificativa_conclusao'] = justificativa_analista
            e['data_conclusao'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            item_concluido = e
            break
            
    if item_concluido:
        try:
            # Preserva a estrutura original (se era dict ou list) ao salvar
            dados_para_salvar = dados_brutos
            if is_dict_format: dados_para_salvar['eventos'] = eventos
            else: dados_para_salvar = eventos

            with open(BASE_DADOS, 'w', encoding='utf-8') as f:
                json.dump(dados_para_salvar, f, indent=4, ensure_ascii=False)
            
            return jsonify({"status": "success"})
        except Exception as err:
            return jsonify({"status": "error", "message": str(err)}), 500
            
    return jsonify({"status": "error", "message": "Item não encontrado"}), 404

def _carregar_threads_concluidas():
    """Lista de fios concluídos."""
    try:
        return load_concluidas()
    except Exception as e:
        logger.error(f"Erro ao carregar threads concluídas: {e}")
        return []

def _salvar_threads_concluidas(lista):
    """Grava fios concluídos no arquivo único."""
    try:
        save_concluidas(lista)
    except Exception as e:
        logger.error(f"Erro ao salvar threads concluídas: {e}")
        raise

def _carregar_threads_aguardando():
    """Lista de fios em aguardando."""
    try:
        return load_aguardando()
    except Exception as e:
        logger.error(f"Erro ao carregar threads aguardando: {e}")
        return []

def _salvar_threads_aguardando(lista):
    """Grava fios aguardando no arquivo único."""
    try:
        save_aguardando(lista)
    except Exception as e:
        logger.error(f"Erro ao salvar threads aguardando: {e}")
        raise


def _tids_aguardando_com_nova_mensagem(mapa_threads, aguardando_lista):
    """Threads em aguardando cujo fio tem mais mensagens que ao marcar o aguardo."""
    out = set()
    for r in aguardando_lista:
        if not isinstance(r, dict):
            continue
        tid = r.get('threadId')
        if not tid:
            continue
        msgs = mapa_threads.get(tid) or []
        try:
            stored = int(r.get('qtd_mensagens_no_fechamento') or 0)
        except (TypeError, ValueError):
            stored = 0
        if len(msgs) > stored:
            out.add(tid)
    return out


def _persistir_saida_aguardando_por_nova_mensagem(tids_afetados):
    """
    Nova mensagem após Aguardando: remove o registro em threads_aguardando.json e
    grava status_processo PENDENTE no integrador. Remove o registro = zera o marcador de dias
    em Aguardando; um novo "Marcar aguardando" grava data_marcacao de novo (ex.: DATA REF do calendário).
    """
    if not tids_afetados:
        return
    lista_ag = _carregar_threads_aguardando()
    nova_ag = [r for r in lista_ag if not isinstance(r, dict) or r.get('threadId') not in tids_afetados]
    if len(nova_ag) < len(lista_ag):
        try:
            _salvar_threads_aguardando(nova_ag)
        except Exception as e:
            logger.error(f"Erro ao remover aguardando após nova mensagem: {e}", exc_info=True)
            return
    try:
        dados = carregar_json(BASE_DADOS)
    except Exception as e:
        logger.error(f"Erro ao carregar integrador para saída de aguardando: {e}", exc_info=True)
        return
    if not isinstance(dados, dict):
        return
    changed = False
    for ev in dados.get('eventos') or []:
        if not isinstance(ev, dict):
            continue
        if ev.get('threadId') not in tids_afetados:
            continue
        if _evento_concluido_operacional(ev):
            continue
        sp = (ev.get('status_processo') or '').strip().upper().replace('Í', 'I')
        if sp != 'PENDENTE':
            ev['status_processo'] = 'PENDENTE'
            changed = True
    for th in dados.get('threads') or []:
        if not isinstance(th, dict):
            continue
        if th.get('threadId') not in tids_afetados:
            continue
        st = (th.get('status') or '').strip().lower()
        if st in ('concluido', 'closed', 'resolved', 'fechado'):
            continue
        sp = (th.get('status_processo') or '').strip().upper().replace('Í', 'I')
        if sp in ('CONCLUIDO', 'CLOSED', 'RESOLVED', 'FECHADO'):
            continue
        if sp != 'PENDENTE':
            th['status_processo'] = 'PENDENTE'
            changed = True
    if changed:
        try:
            with open(BASE_DADOS, 'w', encoding='utf-8') as f:
                json.dump(dados, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erro ao salvar integrador após saída de aguardando: {e}", exc_info=True)


def _carregar_cadastro_empresas():
    """Carrega cadastro_clientes_cadoc — usa cache em memória (ver _cadastro_cached)."""
    return _cadastro_cached()

# Domínios de e-mail pessoal — não usar como nome de empresa na distribuição por clientes
_DOMINIOS_EMAIL_GENERICOS = frozenset({
    "gmail.com", "googlemail.com", "hotmail.com", "outlook.com", "live.com", "msn.com",
    "yahoo.com", "yahoo.com.br", "yahoo.co.uk", "icloud.com", "me.com", "mac.com",
    "bol.com.br", "uol.com.br", "terra.com.br", "ig.com.br", "protonmail.com", "proton.me",
    "hey.com", "pm.me",
})


def _dominio_eh_generico(dominio: str) -> bool:
    if not dominio or not isinstance(dominio, str):
        return True
    d = dominio.strip().lower().lstrip("@")
    if d in _DOMINIOS_EMAIL_GENERICOS:
        return True
    for g in _DOMINIOS_EMAIL_GENERICOS:
        if d == g or d.endswith("." + g):
            return True
    return False


def _empresa_fallback_dominio_corporativo(e) -> str:
    """
    Quando cadastro e assunto não resolvem empresa: usa o domínio do e-mail do lado CLIENTE.
    Evita tratar nome de pessoa (campo cliente) como empresa na Visão Gestão.
    """
    for contato in (e.get("contato_origem"), e.get("contato_destino")):
        if not isinstance(contato, dict):
            continue
        if (contato.get("lado") or "").upper() != "CLIENTE":
            continue
        email = (contato.get("email") or "").strip().lower()
        if not email or "@" not in email:
            continue
        dom = email.rsplit("@", 1)[-1].strip()
        if not dom or _dominio_eh_generico(dom):
            continue
        if "finaud" in dom:
            continue
        return dom
    return ""


def _empresa_do_email(email):
    """Resolve empresa pelo cadastro: 1) lista emails_exatos (ex.: Gmail → Açoriana); 2) domínios."""
    if not email or not isinstance(email, str):
        return ""
    email_norm = email.strip().lower()
    if "@" not in email_norm:
        return ""
    cadastro = _carregar_cadastro_empresas()
    for empresa, info in cadastro.items():
        if not isinstance(info, dict):
            continue
        for ex in info.get("emails_exatos") or ():
            if isinstance(ex, str) and ex.strip().lower() == email_norm:
                return empresa
    dominio = email_norm.split("@", 1)[1]
    for empresa, info in cadastro.items():
        if not isinstance(info, dict):
            continue
        dominios = info.get("dominios", []) if isinstance(info, dict) else []
        for d in dominios:
            if d and (dominio == d or dominio.endswith("." + d) or d in dominio):
                return empresa
    return ""

def _empresa_do_assunto(assunto):
    """Fallback: resolve empresa quando o nome aparece no assunto (ex.: 'Remitly CC - 4010')."""
    if not assunto or not isinstance(assunto, str):
        return ""
    assunto_lower = assunto.strip().lower()
    cadastro = _carregar_cadastro_empresas()
    # Ordena por tamanho decrescente para priorizar "Western Union" sobre "Western"
    empresas_ordenadas = sorted([e for e in cadastro.keys() if e and len(e) >= 3], key=len, reverse=True)
    for empresa in empresas_ordenadas:
        if empresa.lower() in assunto_lower:
            return empresa
    return ""


def _emails_lado_cliente_do_evento(e):
    """E-mails lado CLIENTE no evento e em todas as mensagens da thread (último evento pode não ter o remetente cliente)."""
    out = []
    seen = set()

    def take(ct):
        if not isinstance(ct, dict) or (ct.get("lado") or "").upper() != "CLIENTE":
            return
        em = (ct.get("email") or "").strip().lower()
        if em and "@" in em and em not in seen:
            seen.add(em)
            out.append(em)

    take(e.get("contato_origem"))
    take(e.get("contato_destino"))
    for msg in (e.get("mensagens") or []):
        if isinstance(msg, dict):
            take(msg.get("contato_origem"))
            take(msg.get("contato_destino"))
    return out


def _parece_nome_pessoa_longo(s):
    """Evita usar como 'empresa' strings tipo nome completo de colaborador."""
    s = (s or "").strip()
    if len(s) < 12:
        return False
    tokens = [t for t in re.split(r"[\s\-|]+", s) if t]
    tokens = [re.sub(r"^#+", "", t) for t in tokens]
    tokens = [t for t in tokens if t]
    if len(tokens) >= 4:
        return True
    if len(tokens) >= 3 and len(s) > 22:
        return True
    return False


def _eh_cliente_placeholder_nao_identificado(cand: str) -> bool:
    """Integrador usa DESCONHECIDO / CLIENTE_DESCONHECIDO quando não há contato — não exibir como empresa."""
    u = re.sub(r"\s+", " ", (cand or "").strip()).upper()
    if not u:
        return True
    return u in (
        "DESCONHECIDO",
        "CLIENTE_DESCONHECIDO",
        "NÃO IDENTIFICADO",
        "NAO IDENTIFICADO",
        "UNKNOWN",
        "—",
        "-",
    )


def _eh_rotulo_encaminhamento_interno_finaud(cand: str) -> bool:
    """Mesmo texto que o 04 usa para Finaud→Finaud sem cliente no envelope — pode ir em cliente e empresa."""
    return re.sub(r"\s+", " ", (cand or "").strip()).lower() == "encaminhamento interno finaud"


def _api_email_externo_valido_fwd(em: str, ignorar_sub: tuple) -> bool:
    em = (em or "").strip().lower()
    if not em or "@" not in em:
        return False
    dom = em.rsplit("@", 1)[-1]
    if "finaud" in em or "finaud" in dom:
        return False
    if any(x in dom for x in ignorar_sub):
        return False
    return True


def _api_fwd_primeiro_email_externo_apos_marcador(texto: str) -> str:
    """
    Após marcador de encaminhamento: primeiro e-mail externo em De:/From:.
    Suporta texto plano (`De: Nome <a@b.c>`) e HTML Gmail/Outlook (`mailto:`, texto do link `>a@b.c</a>`).
    """
    if not texto or not str(texto).strip():
        return ""
    low = texto.lower()
    marcadores = (
        "---------- forwarded message ---------",
        "-----forwarded message-----",
        "-----original message-----",
        "begin forwarded message",
        "original message -----",
    )
    idx = -1
    for m in marcadores:
        j = low.find(m)
        if j >= 0:
            idx = j if idx < 0 else min(idx, j)
    if idx < 0:
        return ""
    trecho = texto[idx : idx + 14000]
    ignorar_sub = ("noreply", "no-reply", "donotreply", "mailer-daemon", "maildaemon", "newsletter")
    padroes = (
        r"(?i)\bDe:\s*.+?<([^\s<>]+@[^\s<>]+)>",
        r"(?i)\bFrom:\s*.+?<([^\s<>]+@[^\s<>]+)>",
        r"(?i)\bDe:\s*[\"']?[^\"'<\n]*[\"']?\s*<([^\s<>]+@[^\s<>]+)>",
    )
    for pat in padroes:
        for m in re.finditer(pat, trecho):
            em = (m.group(1) or "").strip().lower()
            if _api_email_externo_valido_fwd(em, ignorar_sub):
                return em
    # Gmail/Outlook HTML: mailto: ou texto visível entre <a>...</a>
    for m in re.finditer(r"mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", trecho, re.I):
        em = (m.group(1) or "").strip().lower()
        if _api_email_externo_valido_fwd(em, ignorar_sub):
            return em
    for m in re.finditer(r">([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})</a>", trecho, re.I):
        em = (m.group(1) or "").strip().lower()
        if _api_email_externo_valido_fwd(em, ignorar_sub):
            return em
    return ""


def _api_contato_origem_finaud_para_fallback(e: dict) -> dict:
    """Evento da lista `eventos` ou objeto `threads[]` (sem contato no topo — só nas mensagens)."""
    co = e.get("contato_origem") or {}
    if (co.get("lado") or "").upper() == "FINAUD":
        return co
    for msg in e.get("mensagens") or []:
        if not isinstance(msg, dict):
            continue
        co = msg.get("contato_origem") or {}
        if (co.get("lado") or "").upper() == "FINAUD":
            return co
    return {}


def _api_contato_destino_finaud_para_fallback(e: dict) -> dict:
    """Destino FINAUD no evento ou na primeira mensagem (04 já corrigiu o JSON)."""
    cd = e.get("contato_destino") or {}
    if (cd.get("lado") or "").upper() == "FINAUD":
        return cd
    for msg in e.get("mensagens") or []:
        if not isinstance(msg, dict):
            continue
        cd = msg.get("contato_destino") or {}
        if (cd.get("lado") or "").upper() == "FINAUD":
            return cd
    return {}


def _api_tem_marcador_encaminhamento_em_texto(texto: str) -> bool:
    low = (texto or "").lower()
    return any(
        m in low
        for m in (
            "---------- forwarded message ---------",
            "-----forwarded message-----",
            "-----original message-----",
            "begin forwarded message",
            "original message -----",
        )
    )


_VOCATIVO_PROIBIDO = frozenset(
    {"prezado", "prezada", "ola", "olá", "oi", "bom", "boa", "caro", "cara", "caros", "caras"}
)


def _api_primeiro_nome_operacional(nome_completo: str) -> str:
    partes = (nome_completo or "").strip().split()
    return partes[0] if partes else ""


def _api_vocativo_na_primeira_linha(s: str) -> str:
    """Ex.: «Rodrigo, boa tarde» ou «Prezada Thaiana, …»."""
    linha = (s or "").strip().split("\n")[0].strip()
    m = re.match(
        r"^\s*(?:Prezado|Prezada|Caro|Cara)\s+"
        r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-]+(?:\s+[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-]+)?)\s*,",
        linha,
        re.I,
    )
    if m:
        return m.group(1).strip()
    m = re.match(
        r"^\s*([A-ZÀ-Ü][a-zà-ú]+(?:\s+[A-ZÀ-Ü][a-zà-ú]+)?)\s*,",
        linha,
    )
    if m:
        cand = m.group(1).strip()
        tok = cand.split()[0].lower()
        if tok not in _VOCATIVO_PROIBIDO:
            return cand
    return ""


def _api_extrair_vocativo_destinatario_interno(e: dict) -> str:
    for msg in (e.get("mensagens") or [])[:1]:
        if not isinstance(msg, dict):
            continue
        for k in ("corpo_limpo", "corpo"):
            s = msg.get(k)
            if isinstance(s, str) and s.strip():
                r = _api_vocativo_na_primeira_linha(s)
                if r:
                    return r
    for k in ("corpo_limpo", "corpo"):
        s = e.get(k)
        if isinstance(s, str) and s.strip():
            r = _api_vocativo_na_primeira_linha(s)
            if r:
                return r
    return ""


def _api_aplicar_cliente_empresa_responsavel_interno_finaud(e: dict, co: dict, cd: dict) -> None:
    """Pedido Finaud→Finaud com contexto no forward: pills alinhadas ao ato operacional (não ao banco citado)."""
    nome_orig = (co.get("nome") or "").strip()
    e["cliente"] = _api_primeiro_nome_operacional(nome_orig) or nome_orig or "Finaud"
    e["empresa"] = "Finaud"
    e["_painel_preservar_empresa_responsavel_fallback"] = True
    dest = ""
    if isinstance(cd, dict) and (cd.get("lado") or "").upper() == "FINAUD":
        dest = (cd.get("nome") or "").strip()
    if not dest:
        dest = _api_extrair_vocativo_destinatario_interno(e)
    if dest:
        e["responsavel"] = _api_primeiro_nome_operacional(dest) or dest


def _api_corpo_limpo_topo_sem_email_externo(e: dict) -> bool:
    """
    Texto do topo que o operacional mostra (corpo_limpo da 1ª mensagem, senão do evento):
    sem «@» ou só e-mails @finaud — típico pedido interno Andrea→Rodrigo com forward só na cauda.
    """
    bloco = ""
    msgs = e.get("mensagens") or []
    if msgs and isinstance(msgs[0], dict):
        m0 = msgs[0]
        for k in ("corpo_limpo", "corpo"):
            v = m0.get(k)
            if isinstance(v, str) and v.strip():
                bloco = v
                break
    if not bloco.strip():
        for k in ("corpo_limpo", "corpo"):
            v = e.get(k)
            if isinstance(v, str) and v.strip():
                bloco = v
                break
    bloco = (bloco or "").strip()
    if not bloco:
        return False
    emails = re.findall(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", bloco, re.I
    )
    if not emails:
        return True
    return all("finaud" in em.lower() for em in emails)


def _api_texto_corpo_para_fallback_fwd(e: dict) -> str:
    partes = []
    for k in ("corpo", "corpo_html", "corpo_limpo"):
        v = e.get(k)
        if isinstance(v, str) and v.strip():
            partes.append(v)
    for msg in (e.get("mensagens") or [])[:5]:
        if not isinstance(msg, dict):
            continue
        for k in ("corpo", "corpo_html", "corpo_limpo"):
            v = msg.get(k)
            if isinstance(v, str) and v.strip():
                partes.append(v)
    return "\n".join(partes)


def _aplicar_fallback_cliente_encaminhamento_interno_api(e: dict) -> None:
    """
    JSON gerado antes do 04/08: Finaud→Finaud (ou CLIENTE vazio) + Fwd no corpo — cliente só no citado.
    Preenche `cliente` na resposta para `_empresa_gestao_final` refletir na pill Empresa sem reprocessar pipeline.
    Também usado em `/api/threads` (modal): mesmos dados que o card em `/api/dados`.

    Prioridade operacional: se o pedido **visível no topo** é interno (sem e-mail de cliente no corpo_limpo)
    ou o destino já é **FINAUD**, pills = remetente (1º nome), empresa **Finaud**, responsável = colega (vocativo ou destino FINAUD)
    — não extrair o banco só do citado (ex.: Andrea → Rodrigo; BCP só no forward).
    """
    if not _eh_cliente_placeholder_nao_identificado(e.get("cliente")):
        return
    co = _api_contato_origem_finaud_para_fallback(e)
    if (co.get("lado") or "").upper() != "FINAUD":
        return
    if _emails_lado_cliente_do_evento(e):
        return
    texto = _api_texto_corpo_para_fallback_fwd(e)
    if not _api_tem_marcador_encaminhamento_em_texto(texto):
        return
    cd = _api_contato_destino_finaud_para_fallback(e)
    if (cd.get("lado") or "").upper() == "FINAUD":
        _api_aplicar_cliente_empresa_responsavel_interno_finaud(e, co, cd)
        return
    if _api_corpo_limpo_topo_sem_email_externo(e):
        _api_aplicar_cliente_empresa_responsavel_interno_finaud(e, co, cd)
        return
    em_ext = _api_fwd_primeiro_email_externo_apos_marcador(texto)
    if not em_ext:
        return
    nome = _empresa_do_email(em_ext)
    if not nome:
        nome = _titulo_heuristico_de_dominio(em_ext.split("@", 1)[-1])
    if not nome or _eh_cliente_placeholder_nao_identificado(nome):
        return
    e["cliente"] = nome


def _empresa_gestao_final(e):
    """
    Rótulo de empresa para API (Gestão / filtros): cadastro e domínio a partir de qualquer e-mail CLIENTE na thread;
    não propaga nome de pessoa do campo cliente.
    """
    emails = _emails_lado_cliente_do_evento(e)
    for em in emails:
        nome = _empresa_do_email(em)
        if nome:
            return nome
    r = _empresa_do_assunto(e.get("titulo") or e.get("assunto") or "")
    if r:
        return r
    for em in emails:
        dom = em.rsplit("@", 1)[-1]
        if dom and not _dominio_eh_generico(dom) and "finaud" not in dom:
            return dom
    for cand in ((e.get("empresa") or "").strip(), (e.get("cliente") or "").strip()):
        if not cand or _eh_cliente_placeholder_nao_identificado(cand):
            continue
        if _eh_rotulo_encaminhamento_interno_finaud(cand):
            return cand
        if not _parece_nome_pessoa_longo(cand):
            return cand
    return ""


def _nome_empresa_por_dominio_no_cadastro(dom_lc: str) -> str:
    """Se a string é um domínio igual a um cadastro `dominios`, retorna o nome da empresa (chave)."""
    dom_lc = (dom_lc or "").strip().lower()
    if not dom_lc or "." not in dom_lc:
        return ""
    cadastro = _carregar_cadastro_empresas()
    for nome_emp, info in cadastro.items():
        if not isinstance(info, dict):
            continue
        for d in info.get("dominios") or []:
            if d and str(d).strip().lower() == dom_lc:
                return nome_emp
    return ""


def _titulo_heuristico_de_dominio(dom_lc: str) -> str:
    """Último recurso: remove TLD comum e capitaliza partes (evita mostrar .com/.br na Gestão)."""
    s = (dom_lc or "").strip().lower()
    if not s:
        return ""
    sufixos = (
        ".com.br", ".net.br", ".org.br", ".co.uk", ".com", ".net", ".org", ".br",
        ".ai", ".vc", ".global", ".digital", ".uk", ".us",
    )
    for suf in sufixos:
        if s.endswith(suf):
            s = s[: -len(suf)]
            break
    s = s.replace("-", " ").replace(".", " ")
    partes = [p for p in re.split(r"\s+", s) if p]
    if not partes:
        return dom_lc.strip()
    return " ".join(w.capitalize() for w in partes)


def _carregar_rotulos_empresa_gestao() -> dict:
    """Rótulos de empresa — usa cache em memória (ver _rotulos_cached)."""
    return _rotulos_cached()


def _rotulo_empresa_gestao_para_api(raw: str) -> str:
    """
    Nome exibido na Visão Gestão: sem domínio cru (.com / .com.br); prioriza cadastro e rotulos_empresa_gestao.json.
    """
    s = (raw or "").strip()
    if not s or _eh_cliente_placeholder_nao_identificado(s):
        return ""
    lk = s.lower()
    rotulos = _carregar_rotulos_empresa_gestao()
    if lk in rotulos:
        return rotulos[lk]
    nome_dom = _nome_empresa_por_dominio_no_cadastro(lk)
    if nome_dom:
        return nome_dom
    if "." in lk and " " not in lk and "@" not in lk:
        return _titulo_heuristico_de_dominio(lk)
    return s


def _enriquecer_threads_com_empresa(threads):
    """Adiciona campo 'empresa' em cada thread: 1) domínio do e-mail do cliente, 2) fallback: nome no assunto, 3) Fwd interno (HTML/JSON antigo) como em /api/dados."""
    for t in (threads or []):
        if not isinstance(t, dict):
            continue
        empresa = t.get("empresa", "").strip()
        # Se empresa é placeholder F→F, tenta inferir do assunto antes de desistir
        if empresa and _eh_rotulo_encaminhamento_interno_finaud(empresa):
            assunto = t.get("assunto") or t.get("titulo") or ""
            empresa_assunto = _empresa_do_assunto(assunto)
            if empresa_assunto:
                t["empresa"] = empresa_assunto
            continue
        if empresa:
            continue
        for msg in (t.get("mensagens") or []):
            if not isinstance(msg, dict):
                continue
            for contato in (msg.get("contato_origem"), msg.get("contato_destino")):
                if not isinstance(contato, dict):
                    continue
                if (contato.get("lado") or "").upper() == "CLIENTE":
                    email = contato.get("email") or ""
                    if email:
                        empresa = _empresa_do_email(email)
                        if empresa:
                            t["empresa"] = empresa
                            break
            if empresa:
                break
        if not empresa:
            assunto = t.get("assunto") or t.get("titulo") or ""
            empresa = _empresa_do_assunto(assunto)
            if empresa:
                t["empresa"] = empresa
        _aplicar_fallback_cliente_encaminhamento_interno_api(t)
        if t.pop("_painel_preservar_empresa_responsavel_fallback", False):
            t["empresa"] = _rotulo_empresa_gestao_para_api((t.get("empresa") or "Finaud").strip())
        else:
            emp_f = (t.get("empresa") or "").strip()
            if not emp_f or _eh_cliente_placeholder_nao_identificado(emp_f):
                nova = _rotulo_empresa_gestao_para_api(_empresa_gestao_final(t))
                if nova:
                    t["empresa"] = nova
        t["responsavel_pela_acao"] = _responsavel_pela_acao_from_mensagens(
            t.get("mensagens") or [], (t.get("responsavel") or "").strip()
        )

def _threads_nova_interacao(data_ref=None):
    """Threads removidas de Aguardando (AGUARDO_RESOLVIDO) para badge 'Nova resposta'.

    Com ``data_ref`` (dia fechado passado): só inclui registos cujo campo ``data`` do diário
    coincide **exatamente** com ``data_ref`` — o pipeline daquele dia resolveu o Aguardando,
    então o badge aparece apenas na vista desse dia, não contaminando dias anteriores já
    classificados quando se sobe um dia novo.
    Sem ``data_ref`` (hoje): comportamento original — hoje ou ontem da máquina.
    """
    if not os.path.exists(ARQUIVO_DIARIO):
        return []
    try:
        with open(ARQUIVO_DIARIO, 'r', encoding='utf-8') as f:
            diario = json.load(f)
    except Exception:
        return []
    if not isinstance(diario, list):
        return []
    hoje = datetime.now().date()
    # Com data_ref explícita: badge só no dia correspondente (não contamina dias anteriores).
    # Sem data_ref: hoje ou ontem (comportamento original para a vista "ao vivo").
    if data_ref is not None and data_ref < hoje:
        datas_validas = {data_ref}
    else:
        ontem = hoje - timedelta(days=1)
        datas_validas = {hoje, ontem}
    ids = []
    for e in diario:
        if (e.get('tipo') or '') != 'AGUARDO_RESOLVIDO':
            continue
        tid = e.get('thread') or e.get('threadId')
        if not tid:
            continue
        data_str = str(e.get('data') or '').strip()
        if not data_str:
            continue
        try:
            dt = None
            if '-' in data_str[:10]:
                dt = datetime.strptime(data_str[:10], '%Y-%m-%d').date()
            elif '/' in data_str:
                parts = data_str.split()[0].split('/')
                if len(parts) >= 3:
                    d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                    if y < 100:
                        y += 2000
                    dt = date(y, m, d)
            if dt and dt in datas_validas:
                ids.append(tid)
        except (ValueError, TypeError, IndexError):
            pass
    return ids

def _extrair_texto_thread(conteudo):
    """Monta um único texto a partir do conteúdo da thread (mensagens) para enviar à IA."""
    mensagens = conteudo if isinstance(conteudo, list) else (conteudo.get("mensagens") or [])
    partes = []
    for i, msg in enumerate(mensagens):
        if isinstance(msg, dict):
            assunto = msg.get("assunto") or msg.get("subject") or ""
            corpo = msg.get("corpo") or msg.get("body") or msg.get("conteudo") or msg.get("texto") or ""
            partes.append(f"[Mensagem {i+1}] Assunto: {assunto}\nCorpo: {corpo}")
        else:
            partes.append(str(msg))
    return "\n\n---\n\n".join(partes) if partes else str(conteudo)

def analisar_fluxo_conclusao(corpo_email, cadoc_hint=None):
    """
    Analisa o corpo/conversa de e-mail via GPT-4o e retorna JSON com:
    resumo_desfecho, cadoc_real e maior_tempo_espera.
    cadoc_hint: CADOC já classificado na thread (ex: DDR_2011) para usar como fallback quando a IA retornar OUTROS.
    """
    hint = ""
    if cadoc_hint and str(cadoc_hint).strip().upper() not in ("", "OUTROS"):
        hint = f"\nDica: esta thread já foi classificada no sistema como CADOC = {cadoc_hint}. Prefira esse valor em cadoc_real se fizer sentido com o conteúdo.\n\n"
    prompt = """Atue como um especialista regulatório. Analise a conversa de e-mail abaixo e retorne UM ÚNICO JSON com exatamente estas chaves (nada mais):
- "resumo_desfecho": resumo curto do desfecho (1 a 2 frases).
- "cadoc_real": código do documento/CADOC tratado. Use um destes quando identificável: DDR_2011, DLO_2061, DRL_2160, 4010, Critica, SUPORTE, DRSAC, FORCAPITAL, S5, RETORNO_BACEN (comunicação do BC: indício, crítica, erro, reiteração) ou outro que apareça. Use "OUTROS" SOMENTE se não houver referência a documento, norma ou tipo de entrega.
- "maior_tempo_espera": "Finaud" ou "Cliente" (quem demorou mais a responder). Se não der para inferir, use "Indeterminado".
- "tipo_demanda": mesmo que cadoc_real quando for documento (DDR_2011, DLO_2061, SUPORTE, S5, RETORNO_BACEN, etc.).
- "cliente_identificado": nome da empresa ou instituição que aparece na conversa. Use "Não identificado" se não houver.
- "prazo_cumprido": "sim", "não", "parcial" ou "não se aplica" conforme o desfecho da entrega/prazo regulatório.
- "resolucao_final": 1 frase descrevendo como a demanda foi resolvida (ex.: "Arquivos enviados e aceitos pelo BACEN").
- "gerou_fog": true ou false — true apenas se a conversa mencionar abertura de caso no FogBugz ou ticket de suporte.

Regras para cadoc_real: DDR_2011 para "cadastro de ações", "opções", "DDR", "Demonstrativo Diário de Risco", "câmbio", "extrato de compromissada". Críticas regulatórias costumam ser DLO_2061.
"""
    prompt += hint
    prompt += """Conversa de e-mail:
---
"""
    texto = (corpo_email or "")[:14000]
    prompt += f"{texto}\n---"

    texto_resposta = ""
    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        texto_resposta = (resp.choices[0].message.content or "").strip()
        if texto_resposta.startswith("```"):
            texto_resposta = re.sub(r"^```(?:json)?\s*", "", texto_resposta)
            texto_resposta = re.sub(r"\s*```\s*$", "", texto_resposta)
        return json.loads(texto_resposta)
    except json.JSONDecodeError as e:
        logger.warning(f"analisar_fluxo_conclusao: resposta não-JSON: {e}")
        return {
            "resumo_desfecho": texto_resposta[:400] if texto_resposta else "Não foi possível extrair.",
            "cadoc": "OUTROS",
            "maior_tempo_espera": "Indeterminado",
        }
    except Exception as e:
        logger.error(f"analisar_fluxo_conclusao: {e}", exc_info=True)
        return {
            "resumo_desfecho": "Erro na análise.",
            "cadoc": "OUTROS",
            "maior_tempo_espera": "Indeterminado",
        }

def _aprendizado_de_resumo_ia(resumo_ia, conteudo, cadoc_hint):
    """Constrói aprendizado_ia a partir do resumo já gerado (evita chamada IA duplicada)."""
    resumo = resumo_ia or {}
    cliente = (conteudo.get("cliente") or "") if isinstance(conteudo, dict) else ""
    cadoc = (cadoc_hint or "").strip()
    if not cadoc or cadoc.upper() == "OUTROS":
        cadoc = "OUTROS"
    return {
        "resumo_desfecho": (resumo.get("motivo_aprendizado") or resumo.get("explicacao_caso") or resumo.get("motivo_em_blocos") or "").strip(),
        "cadoc_real": cadoc,
        "maior_tempo_espera": resumo.get("responsabilidade_semantica") or "Indeterminado",
        "tipo_demanda": cadoc if cadoc != "OUTROS" else "OUTROS",
        "cliente_identificado": cliente or "Não identificado",
        "prazo_cumprido": "não se aplica",
        "resolucao_final": (resumo.get("explicacao_caso") or resumo.get("motivo_em_blocos") or "").strip(),
        "gerou_fog": False,
        "resumo_interacoes": resumo.get("resumo_interacoes"),
    }


def _aprendizado_heurístico(conteudo, cadoc_hint):
    """Constrói aprendizado mínimo sem IA (fallback quando não há resumo pré-gerado)."""
    cliente = (conteudo.get("cliente") or "") if isinstance(conteudo, dict) else ""
    cadoc = (cadoc_hint or "").strip()
    if not cadoc or cadoc.upper() == "OUTROS":
        cadoc = "OUTROS"
    latest = {}
    if isinstance(conteudo, dict):
        msgs = conteudo.get("mensagens") or []
        latest = msgs[-1] if msgs else {}
    motivo = _construir_motivo_contextual(
        conteudo, latest, cadoc, cliente,
        conteudo.get("responsavel") or conteudo.get("responsavel_nome") if isinstance(conteudo, dict) else "",
        conteudo.get("lista_prazos") or [] if isinstance(conteudo, dict) else []
    )
    return {
        "resumo_desfecho": motivo or "Concluído pelo analista.",
        "cadoc_real": cadoc,
        "maior_tempo_espera": "Indeterminado",
        "tipo_demanda": cadoc if cadoc != "OUTROS" else "OUTROS",
        "cliente_identificado": cliente or "Não identificado",
        "prazo_cumprido": "não se aplica",
        "resolucao_final": motivo or "",
        "gerou_fog": False,
    }


@app.route('/api/par_threads/confirmar', methods=['POST'])
@login_required
def api_par_threads_confirmar():
    """Confirma par entre duas threads (mesma empresa + mesmos prazos); depois Aprender e Concluir em uma fecha a outra."""
    body = request.get_json() or {}
    ta = (body.get('threadId') or '').strip()
    tb = (body.get('outroThreadId') or '').strip()
    ok, msg = _threads_elegiveis_para_confirmar_par(ta, tb)
    if not ok:
        return jsonify({'status': 'error', 'message': msg}), 400
    na, nb = _normalizar_par_thread_ids(ta, tb)
    lista = _carregar_pares_confirmados_list()
    for r in lista:
        if not isinstance(r, dict):
            continue
        if _normalizar_par_thread_ids(r.get('thread_a'), r.get('thread_b')) == (na, nb):
            return jsonify({'status': 'error', 'message': 'Este par já estava confirmado.'}), 400
    lista.append({
        'thread_a': na,
        'thread_b': nb,
        'confirmado_em': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    })
    try:
        _salvar_pares_confirmados_list(lista)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    return jsonify({
        'status': 'success',
        'pares_confirmados': _mapa_pares_confirmados_para_api(lista),
    })


@app.route('/api/concluir_thread', methods=['POST'])
@login_required
def concluir_thread():
    """Recebe threadId e conteúdo; usa resumo_ia se fornecido (sem IA); senão heurísticas. Persiste em threads_concluidas.json."""
    dados = request.get_json() or {}
    thread_id = dados.get("threadId")
    conteudo = dados.get("conteudo")
    resumo_ia = dados.get("resumo_ia")

    if not thread_id:
        return jsonify({"status": "error", "message": "threadId é obrigatório"}), 400

    mensagens = conteudo if isinstance(conteudo, list) else (conteudo.get("mensagens") if isinstance(conteudo, dict) else [])
    qtd_mensagens = len(mensagens) if mensagens else 0

    cadoc_hint = None
    if isinstance(conteudo, dict):
        lista_prazos = conteudo.get("lista_prazos") or []
        cadoc_hint = conteudo.get("cadoc") or (lista_prazos[0].get("cadoc") if lista_prazos else None)

    if resumo_ia and isinstance(resumo_ia, dict):
        resultado_fluxo = _aprendizado_de_resumo_ia(resumo_ia, conteudo or {}, cadoc_hint)
    else:
        resultado_fluxo = _aprendizado_heurístico(conteudo or {}, cadoc_hint)

    cadoc_ia = (
        resultado_fluxo.get("cadoc_real") or resultado_fluxo.get("cadoc")
        or resultado_fluxo.get("documento") or ""
    ).strip()
    if not cadoc_ia or cadoc_ia.upper() == "OUTROS":
        if cadoc_hint and str(cadoc_hint).strip().upper() not in ("", "OUTROS"):
            cadoc_ia = str(cadoc_hint).strip()
        else:
            cadoc_ia = "OUTROS"

    tipo_demanda = (
        resultado_fluxo.get("tipo_demanda")
        or resultado_fluxo.get("cadoc_real")
        or cadoc_ia
        or "OUTROS"
    )
    cliente_identificado = (
        resultado_fluxo.get("cliente_identificado") or "Não identificado"
    )
    prazo_cumprido = (
        resultado_fluxo.get("prazo_cumprido") or "não se aplica"
    )
    resolucao_final = (
        resultado_fluxo.get("resolucao_final")
        or resultado_fluxo.get("resumo_desfecho")
        or resultado_fluxo.get("resumo")
        or ""
    )
    gerou_fog = resultado_fluxo.get("gerou_fog") in (True, "true", 1, "1")

    aprendizado_ia = {
        "resumo_desfecho": (
            resultado_fluxo.get("resumo_desfecho") or resultado_fluxo.get("resumo") or ""
        ),
        "cadoc_real": cadoc_ia,
        "maior_tempo_espera": (
            resultado_fluxo.get("maior_tempo_espera")
            or resultado_fluxo.get("quem_causou_maior_espera")
            or resultado_fluxo.get("responsavel_espera") or "Indeterminado"
        ),
        "tipo_demanda": tipo_demanda,
        "cliente_identificado": cliente_identificado,
        "prazo_cumprido": prazo_cumprido,
        "prazo_tipo": resultado_fluxo.get("prazo_tipo"),
        "resolucao_final": resolucao_final,
        "gerou_fog": gerou_fog,
    }
    if resultado_fluxo.get("resumo_interacoes"):
        aprendizado_ia["resumo_interacoes"] = resultado_fluxo["resumo_interacoes"]

    # Sobrescrever maior_tempo_espera com dados reais quando disponíveis
    tf = dados.get("tempo_finaud_ms")
    tc = dados.get("tempo_cliente_ms")
    if tf is not None and tc is not None:
        if int(tf) > int(tc):
            aprendizado_ia["maior_tempo_espera"] = "Finaud"
        elif int(tc) > int(tf):
            aprendizado_ia["maior_tempo_espera"] = "Cliente"
        else:
            aprendizado_ia["maior_tempo_espera"] = "Empate"

    data_conclusao = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    registro = {
        "threadId": thread_id,
        "qtd_mensagens_no_fechamento": qtd_mensagens,
        "data_conclusao": data_conclusao,
        "aprendizado_ia": aprendizado_ia,
    }
    # Tempo por agente (Finaud/Cliente/Total) para contabilização
    for k in ("tempo_finaud_ms", "tempo_cliente_ms", "tempo_total_ms"):
        v = dados.get(k)
        if v is not None:
            registro[k] = int(v)

    lista = _carregar_threads_concluidas()
    concluidos_antes = {r.get('threadId') for r in lista if isinstance(r, dict) and r.get('threadId')}
    pares_lista = _carregar_pares_confirmados_list()
    mapa_par = _mapa_pares_confirmados_para_api(pares_lista)
    outro_tid = mapa_par.get(thread_id)

    ag_lista_pre = _carregar_threads_aguardando()
    reg_ant = next((x for x in ag_lista_pre if isinstance(x, dict) and x.get("threadId") == thread_id), None)
    reg_ant_outro = (
        next((x for x in ag_lista_pre if isinstance(x, dict) and x.get("threadId") == outro_tid), None)
        if outro_tid
        else None
    )
    if isinstance(reg_ant, dict):
        mar_ag = (reg_ant.get("data_marcacao") or reg_ant.get("data_ref_operacional") or "").strip()
        if mar_ag:
            registro["marcacao_aguardante_pre_conclusao"] = mar_ag
            registro["origem_aguardante_triagem_auto"] = bool(
                reg_ant.get("alvo_triagem_auto") or reg_ant.get("origem_triagem_auto")
            )

    lista.append(registro)
    par_gemea_concluido = None

    if outro_tid:
        if outro_tid not in concluidos_antes:
            reg_gem = {
                "threadId": outro_tid,
                "qtd_mensagens_no_fechamento": _qtd_mensagens_thread_integrador(outro_tid),
                "data_conclusao": data_conclusao,
                "aprendizado_ia": copy.deepcopy(aprendizado_ia),
                "concluido_em_conjunto_com": thread_id,
            }
            for k in ("tempo_finaud_ms", "tempo_cliente_ms", "tempo_total_ms"):
                if k in registro:
                    reg_gem[k] = registro[k]
            res_fin = (reg_gem["aprendizado_ia"].get("resolucao_final") or "").strip()
            suf = f" [Concluído automaticamente em conjunto com a thread {thread_id} (Aprender e Concluir).]"
            reg_gem["aprendizado_ia"]["resolucao_final"] = (res_fin + suf).strip()
            if isinstance(reg_ant_outro, dict):
                mar_o = (reg_ant_outro.get("data_marcacao") or reg_ant_outro.get("data_ref_operacional") or "").strip()
                if mar_o:
                    reg_gem["marcacao_aguardante_pre_conclusao"] = mar_o
                    reg_gem["origem_aguardante_triagem_auto"] = bool(
                        reg_ant_outro.get("alvo_triagem_auto") or reg_ant_outro.get("origem_triagem_auto")
                    )
            lista.append(reg_gem)
            par_gemea_concluido = outro_tid
        pares_lista = _remover_par_confirmado(pares_lista, thread_id, outro_tid)
        try:
            _salvar_pares_confirmados_list(pares_lista)
        except Exception as e_par:
            logger.error(f"Erro ao atualizar pares confirmados após conclusão: {e_par}")

    ag_lista = ag_lista_pre
    tids_limpar_ag = {thread_id}
    if outro_tid:
        tids_limpar_ag.add(outro_tid)
    ag_novo = [x for x in ag_lista if not isinstance(x, dict) or x.get('threadId') not in tids_limpar_ag]
    if len(ag_novo) != len(ag_lista):
        try:
            _salvar_threads_aguardando(ag_novo)
        except Exception as e_ag:
            logger.error(f"Erro ao remover Aguardando do par: {e_ag}")

    try:
        _salvar_threads_concluidas(lista)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    resp = {"status": "success", "registro": registro}
    if par_gemea_concluido:
        resp["par_gemea_concluido"] = par_gemea_concluido
    return jsonify(resp)

# --- APIs de Aguardando ---
# valor = chave única no select; tipo = valor interno salvo em threads_aguardando
OPCOES_TIPO_AGUARDO = [
    {"valor": "finaud_enviar", "tipo": "ACAO_INTERNA", "label": "Finaud enviar relatórios por categoria"},
    {"valor": "cliente_enviar", "tipo": "ENTREGA_CLIENTE", "label": "Cliente enviar extratos/arquivos"},
    {"valor": "finaud_responder", "tipo": "ACAO_INTERNA", "label": "Finaud responder dúvida"},
    {"valor": "cliente_responder", "tipo": "RESPOSTA_CLIENTE", "label": "Cliente responder dúvida"},
    {"valor": "cliente_encaminhar_bacen", "tipo": "RESPOSTA_CLIENTE", "label": "Cliente encaminhar ao Bacen e aguardar retorno"},
    {"valor": "resposta_outro_email", "tipo": "RESPOSTA_EM_OUTRO_EMAIL", "label": "Resposta em outro e-mail"},
]

# ---------------------------------------------------------------------------
# Passo 14 do refactor: tradução motivo técnico (§refs) → plain language.
# As strings técnicas vivem no código de triagem para auditoria/baselines;
# a tradução abaixo é só para o tooltip do painel (operadores).
# ---------------------------------------------------------------------------
_MOTIVO_AMIGAVEL_MAP_EXATO = {
    # Concluir
    "§3.1 transmitido no BACEN":
        "Caso fechado: a conversa contém a confirmação de transmissão ao BACEN.",
    "§5 remessa Finaud → cliente":
        "Caso fechado: Finaud enviou o material/anexo ao cliente.",
    "§5b RES Finaud → cliente":
        "Caso fechado: Finaud respondeu ao cliente (mensagem RES).",
    "§5c texto conclusivo Finaud → cliente":
        "Caso fechado: Finaud confirmou a resolução ao cliente.",
    "§4d cliente agradece após remessa Finaud → cliente":
        "Caso fechado: cliente agradeceu após receber a resposta da Finaud.",
    "§4f-rb cliente confirma protocolo aceito pelo BACEN":
        "Caso fechado: cliente confirmou que o BACEN aceitou o protocolo.",
    # Aguardando
    "§3-inv pedido Finaud":
        "Aguarda cliente: Finaud solicitou insumos ao cliente.",
    "§3.5 reconhecimento sem remessa":
        "Aguarda Finaud: Finaud confirmou o recebimento, mas ainda não enviou a remessa.",
    "§3 última mensagem CLIENTE":
        "Aguarda Finaud: a última mensagem foi do cliente — sem resposta ainda.",
    "última mensagem Finaud→Finaud":
        "Aguarda Finaud: a última mensagem é interna (entre membros da Finaud).",
}


def _motivo_amigavel(motivo_raw: str) -> str:
    """Traduz motivo técnico de triagem em descrição plain language para o
    tooltip do painel. Lida com prefixos duplicados e linhas de log que
    vinheram embutidas no campo motivo_triagem_auto.

    Mantém a referência §N entre parênteses no fim, para auditoria.
    """
    if not motivo_raw:
        return ""
    import re as _re
    s = str(motivo_raw).strip()

    # 1) Remove prefixo "Triagem automática:" (potencialmente repetido).
    while True:
        m = _re.match(r"^Triagem autom[áa]tica\s*(?:\([^)]*\))?\s*:\s*", s)
        if not m:
            break
        s = s[m.end():].strip()

    # 2) Remove prefixo de log: "GMTHRID_xxx → Concluído (...)" /
    #    "GMTHRID_xxx → Aguardando Finaud (...)" /
    #    "GMTHRID_xxx → Aguardando cliente (...)".
    m = _re.match(
        r"^GMTHRID_\S+\s*→\s*(?:Conclu[íi]do|Aguardando(?:\s+\w+)?)\s*\((.+)\)\s*$",
        s,
    )
    if m:
        s = m.group(1).strip()

    # 3) Mapeamento exato para casos comuns. A referência §N original fica
    #    em ``motivo_tecnico`` (também devolvido pela API) para auditoria,
    #    mas não polui o tooltip do usuário operacional.
    for tech, friendly in _MOTIVO_AMIGAVEL_MAP_EXATO.items():
        if tech in s:
            return friendly

    # 4) Padrões parametrizados (cluster, §3.5+, alvos específicos, etc.)
    if "espelho cluster" in s or "espelho núcleo-assunto" in s:
        return "Caso fechado: outro fio do mesmo grupo (mesma empresa/assunto) já foi concluído — fechamento por espelho."
    if "§3.5 — agradecimento sem remessa" in s or "Finaud só agradece" in s:
        return "Aguarda Finaud: Finaud agradeceu, mas ainda não enviou o material esperado."
    if "Finaud reconheceu recebimento" in s:
        return "Aguarda Finaud: Finaud confirmou o recebimento, mas ainda não enviou a remessa."
    if "Finaud solicitou insumos" in s:
        return "Aguarda cliente: Finaud pediu insumos ao cliente."
    if ("respondeu ao cliente" in s and "aguarda retorno" in s) or "última F→C fora §5" in s:
        return "Aguarda cliente: Finaud respondeu — esperando retorno do cliente."
    if "análise em andamento" in s or "última F→C em análise" in s:
        return "Aguarda Finaud: análise do retorno do BACEN em andamento."
    if "última mensagem interna Finaud" in s:
        return "Aguarda Finaud: a última mensagem é interna (entre Finaud)."
    if "insumo do cliente — aguarda processamento" in s:
        return "Aguarda Finaud: cliente respondeu — aguardando processamento."
    if "§4e" in s and "agradecimento sem novo pedido" in s:
        return "Caso fechado: cliente agradeceu sem fazer novo pedido."

    # 5) Fallback: texto bruto (já sem prefixo duplicado nem GMTHRID).
    return s


@app.route('/api/triagem_motivos')
@login_required
def api_triagem_motivos():
    """Passo 14 do refactor: devolve motivos de Aguardando + Concluído por
    threadId num único payload, para o tooltip do badge de status no painel.

    Resposta: ``{"aguardando": {tid: {motivo, motivo_tecnico, isAuto, alvo}},
                  "concluidos": {tid: ...}}``.

    ``motivo`` é texto amigável (plain language) usado no tooltip.
    ``motivo_tecnico`` é o original com refs §N para auditoria.
    Tolerante a erro: se uma das listas falhar, devolve a outra normalmente.
    """
    try:
        ag_lista = _carregar_threads_aguardando() or []
    except Exception as e:
        logger.error(f"api_triagem_motivos aguardando: {e}", exc_info=True)
        ag_lista = []
    try:
        co_lista = _carregar_threads_concluidas() or []
    except Exception as e:
        logger.error(f"api_triagem_motivos concluidos: {e}", exc_info=True)
        co_lista = []

    def _extrair(rec):
        if not isinstance(rec, dict):
            return None
        tid = str(rec.get("threadId") or "").strip()
        if not tid:
            return None
        motivo_tecnico = (
            str(rec.get("motivo_triagem_auto") or "").strip()
            or str(rec.get("motivo") or "").strip()
            or str((rec.get("aprendizado_ia") or {}).get("resumo_desfecho") or "").strip()
        )
        if not motivo_tecnico:
            return None
        is_auto = bool(rec.get("origem_triagem_auto"))
        if is_auto:
            motivo_amigavel = _motivo_amigavel(motivo_tecnico)
        else:
            # Manual: o operador digitou texto livre — usar como está, só
            # remove prefixo "Triagem automática" caso tenha sido colado.
            motivo_amigavel = motivo_tecnico
            import re as _re
            motivo_amigavel = _re.sub(
                r"^Triagem autom[áa]tica\s*(?:\([^)]*\))?\s*:\s*", "",
                motivo_amigavel,
            ).strip()
        return tid, {
            "motivo": motivo_amigavel[:900],
            "motivo_tecnico": motivo_tecnico[:900],
            "isAuto": is_auto,
            "alvo": str(rec.get("alvo_triagem_auto") or "").strip(),
            "regra": str(rec.get("regra") or "").strip(),
        }

    ag = {}
    for r in ag_lista:
        item = _extrair(r)
        if item:
            ag[item[0]] = item[1]
    co = {}
    for r in co_lista:
        item = _extrair(r)
        if item:
            co[item[0]] = item[1]
    return jsonify({"aguardando": ag, "concluidos": co})


@app.route('/api/threads_aguardando')
@login_required
def api_threads_aguardando():
    """Retorna lista de threads em aguardo, com flag vencido para cada uma."""
    try:
        lista = _carregar_threads_aguardando()
        hoje = datetime.now().date()
        for r in lista:
            if isinstance(r, dict):
                prazo_str = r.get("prazo") or ""
                try:
                    prazo_dt = datetime.strptime(prazo_str[:10], "%Y-%m-%d").date() if prazo_str else None
                    r["vencido"] = prazo_dt is not None and prazo_dt < hoje
                except (ValueError, TypeError):
                    r["vencido"] = False
        return jsonify(lista)
    except Exception as e:
        logger.error(f"api_threads_aguardando: {e}", exc_info=True)
        return jsonify([]), 500

@app.route('/api/prefill_aguardo', methods=['POST'])
@login_required
def api_prefill_aguardo():
    """Retorna opções de tipo e valores sugeridos a partir dos dados da thread."""
    dados = request.get_json() or {}
    thread_id = dados.get("threadId")
    conteudo = dados.get("conteudo") or {}
    if not thread_id:
        return jsonify({"opcoes_tipo": OPCOES_TIPO_AGUARDO, "sugestao": {}, "ja_aguardando": False}), 200

    # Verificar se já está em aguardando
    lista_ag = _carregar_threads_aguardando()
    reg_ag = next((r for r in lista_ag if isinstance(r, dict) and r.get("threadId") == thread_id), None)
    ja_aguardando = reg_ag is not None

    # Extrair dados da thread (conteudo pode ser thread ou {mensagens: [...]})
    mensagens = conteudo.get("mensagens") if isinstance(conteudo, dict) else (conteudo if isinstance(conteudo, list) else [])
    latest = mensagens[-1] if (isinstance(mensagens, list) and mensagens) else {}
    # Preferir dados no nível da thread (conteudo) quando disponíveis
    cadoc = conteudo.get("cadoc") or latest.get("cadoc") or ""
    if not cadoc and (conteudo.get("lista_prazos") or latest.get("lista_prazos")):
        lp = (conteudo.get("lista_prazos") or latest.get("lista_prazos") or [{}])
        cadoc = lp[0].get("cadoc", "") or ""
    # Override manual de cadoc tem prioridade sobre o detectado pelo classificador.
    # Sem isto, ao mudar DDR→SUPORTE pelo chip, o prefill ainda devolveria o prazo D+3
    # (DDR) em vez do D+5 (SUPORTE) — confundindo o operador no modal de marcação.
    overrides_all = load_cartao_overrides() or {}
    ov = overrides_all.get(thread_id) if isinstance(overrides_all, dict) else None
    cadoc_override = ""
    if isinstance(ov, dict):
        cadoc_override = (ov.get("cadoc") or "").strip()
    cadoc_efetivo = cadoc_override or cadoc
    empresa = conteudo.get("cliente") or latest.get("cliente", "") or ""
    responsavel = conteudo.get("responsavel") or conteudo.get("responsavel_nome") or latest.get("responsavel") or latest.get("responsavel_nome", "") or ""
    assunto = conteudo.get("assunto") or conteudo.get("titulo") or latest.get("titulo") or latest.get("assunto", "") or ""

    lp = conteudo.get("lista_prazos") or latest.get("lista_prazos")
    prazo_sugerido = ""
    if lp:
        p = lp[0]
        # Só aproveita o prazo já calculado se o cadoc do prazo bater com o cadoc efetivo
        # (sem override) — caso contrário recalcula abaixo com a regra do cadoc efetivo.
        cadoc_lp = (p.get("cadoc") or "").strip()
        if cadoc_lp and cadoc_efetivo and cadoc_lp == cadoc_efetivo:
            raw = (p.get("prazo_limite") or "").strip()
            prazo_sugerido = _parse_prazo_to_iso(raw)
        elif not cadoc_override:
            raw = (p.get("prazo_limite") or "").strip()
            prazo_sugerido = _parse_prazo_to_iso(raw)

    # Fallback / recálculo: se não há prazo aproveitável e temos cadoc efetivo, calcular
    # pela regra (D+N_UTIL etc.) a partir da data da última mensagem (fallback hoje civil).
    if not prazo_sugerido and cadoc_efetivo:
        dt_base = None
        for campo in ("data_iso", "timestamp", "data_email"):
            val = (latest.get(campo) or "").strip() if isinstance(latest, dict) else ""
            if not val:
                continue
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
                try:
                    dt_base = datetime.strptime(val[:19] if "T" in val or " " in val else val[:10], fmt)
                    break
                except (ValueError, TypeError):
                    continue
            if dt_base is not None:
                break
        if dt_base is None:
            dt_base = datetime.now()
        prazo_sugerido = _calcular_prazo_iso_por_cadoc(dt_base, cadoc_efetivo) or ""

    tipo_sug = _inferir_tipo_aguardo(conteudo, latest, assunto)
    lp = conteudo.get("lista_prazos") or latest.get("lista_prazos") or []
    motivo_sug = _sugerir_motivo_aguardo(cadoc_efetivo, empresa, tipo_sug, assunto, lp, conteudo=conteudo, latest=latest, responsavel=responsavel)

    sugestao = {
        "cadoc": cadoc_efetivo,
        "empresa": empresa,
        "responsavel": responsavel,
        "assunto": assunto,
        "prazo": prazo_sugerido,
        "motivo": motivo_sug,
    }
    resp = {"opcoes_tipo": OPCOES_TIPO_AGUARDO, "sugestao": sugestao, "tipo_sugerido": tipo_sug, "ja_aguardando": ja_aguardando}
    if reg_ag:
        resp["registro_aguardando"] = reg_ag
    return jsonify(resp)


def _inferir_tipo_aguardo(conteudo, latest, assunto):
    """Infere tipo de espera a partir do assunto e conteúdo (ex.: TVM/Dep a Vista → RESPOSTA_EM_OUTRO_EMAIL)."""
    ass = (assunto or "").lower()
    if "tvm" in ass or "dep a vista" in ass or "depósito à vista" in ass or "deposito a vista" in ass:
        return "RESPOSTA_EM_OUTRO_EMAIL"
    # DLO/DDR com CRD/Bacen: Finaud envia resposta para cliente encaminhar ao Bacen → cliente_encaminhar_bacen
    if ("dlo" in ass or "ddr" in ass) and ("crd" in ass or "bacen" in ass or "erro" in ass):
        ultimo_lado = (latest.get("responsabilidade") or (latest.get("contato_origem") or {}).get("lado") or "").upper()
        if "CLIENTE" in ultimo_lado:
            return "cliente_encaminhar_bacen"  # valor do select para "Cliente encaminhar ao Bacen e aguardar retorno"
    ultimo_lado = (latest.get("responsabilidade") or latest.get("responsavel") or "").upper()
    if "CLIENTE" in ultimo_lado:
        return "ENTREGA_CLIENTE" if "enviar" in ass or "extrato" in ass else "RESPOSTA_CLIENTE"
    if "FINAUD" in ultimo_lado:
        return "ACAO_INTERNA"
    return "ACAO_INTERNA"


def _parse_prazo_to_iso(prazo_str):
    """Converte prazo (DD/MM/YYYY ou YYYY-MM-DD) para YYYY-MM-DD para input type=date."""
    if not prazo_str or not isinstance(prazo_str, str):
        return ""
    s = prazo_str.strip()[:16]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(s[:10], fmt)
            return dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            continue
    return ""


_REGRAS_PRAZO_CACHE: dict = {"data": None, "mtime": None}


def _carregar_regras_prazo() -> dict:
    """Lê ``documentos_regulatorios_prazos`` + feriados de mapeamento_regras_negocio.json.

    Cache simples por mtime do ficheiro — replica a fonte usada por scripts/05.
    """
    fp = os.path.join(CONFIG_DIR, "mapeamento_regras_negocio.json")
    try:
        mt = os.path.getmtime(fp)
    except OSError:
        return {"prazos": {}, "feriados": set()}
    if _REGRAS_PRAZO_CACHE["mtime"] == mt and _REGRAS_PRAZO_CACHE["data"] is not None:
        return _REGRAS_PRAZO_CACHE["data"]
    try:
        with open(fp, "r", encoding="utf-8") as f:
            j = json.load(f)
    except Exception:
        return {"prazos": {}, "feriados": set()}
    raiz = j.get("O_QUE_ESTA_SENDO_ANALISADO", {}) or {}
    prazos = raiz.get("documentos_regulatorios_prazos", {}) or {}
    feriados: set = set()
    for d in raiz.get("feriados_nacionais", []) or []:
        try:
            feriados.add(datetime.strptime(d, "%Y-%m-%d").date())
        except (ValueError, TypeError):
            pass
    out = {"prazos": prazos, "feriados": feriados}
    _REGRAS_PRAZO_CACHE["data"] = out
    _REGRAS_PRAZO_CACHE["mtime"] = mt
    return out


def _eh_dia_util(d, feriados: set) -> bool:
    return d.weekday() < 5 and d not in feriados


def _adicionar_dias_uteis(dt_base, dias_uteis: int, feriados: set):
    from datetime import timedelta as _td  # pylint: disable=import-outside-toplevel
    cur = dt_base
    cont = 0
    while cont < dias_uteis:
        cur = cur + _td(days=1)
        if _eh_dia_util(cur, feriados):
            cont += 1
    return cur


def _calcular_prazo_iso_por_cadoc(dt_base, cadoc: str) -> str:
    """Calcula prazo ISO (YYYY-MM-DD) a partir de ``dt_base`` e ``cadoc``.

    Replica enxuta de ``CalculadorPrazos.calcular_prazo_limite`` (scripts/05).
    Suporta D+N_UTIL, D+N_UTIL_MES_SEGUINTE e DIA_N_SEGUNDO_MES. Devolve ``""``
    se cadoc desconhecido ou dt_base inválido.
    """
    from datetime import datetime as _dt, timedelta as _td  # pylint: disable=import-outside-toplevel

    if dt_base is None or not cadoc:
        return ""
    if isinstance(dt_base, _dt):
        d_base = dt_base.date()
    elif hasattr(dt_base, "year") and hasattr(dt_base, "month") and hasattr(dt_base, "day"):
        d_base = dt_base
    else:
        return ""
    cadoc = (cadoc or "").strip()
    if cadoc == "SUPORTE_GERAL":
        cadoc = "SUPORTE"
    cfg = _carregar_regras_prazo()
    regra_cfg = cfg["prazos"].get(cadoc)
    if not isinstance(regra_cfg, dict):
        return ""
    regra = (regra_cfg.get("prazo") or "").strip()
    if not regra:
        return ""
    feriados = cfg["feriados"]
    m = re.search(r"\d+", regra)
    if "D+" in regra and "UTIL" in regra and "MES" not in regra:
        if not m:
            return ""
        prazo = _adicionar_dias_uteis(d_base, int(m.group()), feriados)
        return prazo.strftime("%Y-%m-%d")
    if "MES_SEGUINTE" in regra:
        if not m:
            return ""
        primeiro = _dt(d_base.year, d_base.month, 1).date() + _td(days=32)
        primeiro = primeiro.replace(day=1)
        prazo = _adicionar_dias_uteis(primeiro, int(m.group()), feriados)
        return prazo.strftime("%Y-%m-%d")
    if "SEGUNDO_MES" in regra:
        if not m:
            return ""
        mes = d_base.month + 2
        ano = d_base.year
        if mes > 12:
            mes -= 12
            ano += 1
        return f"{ano:04d}-{mes:02d}-{int(m.group()):02d}"
    return ""


def _decode_mime_header(s):
    """Decodifica RFC 2047 (=?charset?Q?…?= / =?charset?B?…?=) para exibição legível."""
    if s is None or not isinstance(s, str):
        return ""
    s = s.strip()
    if not s or "=?" not in s:
        return s
    try:
        parts = email_decode_header(s)
        out = []
        for part, charset in parts:
            if isinstance(part, bytes):
                enc = charset or "utf-8"
                try:
                    out.append(part.decode(enc, errors="replace"))
                except Exception:
                    out.append(part.decode("utf-8", errors="replace"))
            else:
                out.append(part or "")
        r = "".join(out).strip() or s
        r = re.sub(r"\s+via\s+Suporte$", "", r, flags=re.IGNORECASE).strip() or r
        return re.sub(r"^['\"]|['\"]$", "", r).strip() or r
    except Exception:
        return s


def _construir_motivo_contextual(conteudo, latest, cadoc, empresa, responsavel, lista_prazos):
    """
    Constrói motivo a partir dos dados reais da thread: quem envia, para quem, o quê, prazo.
    Prioridade sobre motivos aprendidos para evitar erros (ex.: Terra Investimentos em thread Avenue).
    Nomes são decodificados (RFC 2047) para evitar =?UTF-8?Q?…?= no motivo.
    Exceção: quando última msg é FINAUD dizendo "obrigada/obrigado", o cliente enviou os dados — motivo deve ser "Cliente envia ao Finaud".
    """
    quem_envia = ""
    para_quem = _decode_mime_header((responsavel or "").strip())
    co = (latest or {}).get("contato_origem") or {}
    cd = (latest or {}).get("contato_destino") or {}
    lado_origem = (co.get("lado") or "").strip().upper()
    lado_destino = (cd.get("lado") or "").strip().upper()
    nome_origem = _decode_mime_header((co.get("nome") or "").strip())
    nome_destino = _decode_mime_header((cd.get("nome") or "").strip())
    corpo_lower = ((latest or {}).get("corpo") or (latest or {}).get("corpo_limpo") or "").lower()
    # Exceção: Finaud agradeceu recebimento → cliente enviou os dados; motivo = "Cliente envia ao Finaud"
    if lado_origem == "FINAUD" and nome_origem and nome_destino and ("obrigada" in corpo_lower or "obrigado" in corpo_lower):
        quem_envia = nome_destino
        para_quem = nome_origem
    elif lado_origem == "CLIENTE" and nome_origem:
        quem_envia = nome_origem
    elif lado_origem == "FINAUD" and nome_origem:
        quem_envia = nome_origem
    if not quem_envia and empresa:
        quem_envia = _decode_mime_header(empresa)
    if not para_quem and lado_destino == "FINAUD" and nome_destino:
        para_quem = nome_destino
    elif not para_quem and lado_origem == "FINAUD" and nome_origem:
        para_quem = nome_origem
    o_que = (cadoc or "").strip()
    if o_que and "_" in o_que:
        o_que = o_que.split("_")[0]
    prazo_str = ""
    if lista_prazos and isinstance(lista_prazos, list):
        datas = []
        for p in lista_prazos:
            raw = (p.get("prazo_limite") or "").strip()[:10]
            if raw:
                dt_iso = _parse_prazo_to_iso(raw)
                if dt_iso:
                    datas.append((dt_iso, raw))
        if datas:
            datas.sort(key=lambda x: x[0], reverse=True)
            prazo_str = datas[0][1]
    if not quem_envia and not para_quem:
        return None
    if quem_envia and para_quem:
        motivo = f"{quem_envia} envia ao {para_quem}"
    elif quem_envia:
        motivo = quem_envia
    else:
        motivo = para_quem
    if o_que:
        motivo += f" dados para {o_que}"
    if prazo_str:
        motivo += f". Prazo: {prazo_str}"
    return motivo if len(motivo) > 15 else None


def _sugerir_motivo_aguardo(cadoc, empresa, tipo, assunto, lista_prazos, historico_texto="", conteudo=None, latest=None, responsavel=None):
    """Gera motivo sugerido: primeiro dados contextuais; depois motivos já usados nos fios atualmente «Aguardando»; por fim heurísticas."""
    empresa = (empresa or "").strip()
    if not empresa and assunto:
        ass = (assunto or "").lower()
        if "tvm" in ass or "dep a vista" in ass:
            empresa = "Western Union"
    cadoc = (cadoc or "").strip()
    prazo_str = ""
    if lista_prazos:
        p = lista_prazos[0] if isinstance(lista_prazos, list) and lista_prazos else {}
        prazo_str = (p.get("prazo_limite") or "").strip()[:10]
    tipo = (tipo or "ACAO_INTERNA").strip()
    # 1. Prioridade: motivo contextual (dados reais da tela)
    motivo_ctx = _construir_motivo_contextual(conteudo, latest, cadoc, empresa, responsavel, lista_prazos)
    if motivo_ctx:
        return motivo_ctx
    # 2. Motivos já guardados só em threads aguardando (triagem/auto + painel quando existir lista)
    lista_ag = _carregar_threads_aguardando()
    candidatos = []
    emp_lower = empresa.lower() if empresa else ""
    for r in lista_ag:
        if not isinstance(r, dict): continue
        reg_cadoc = (r.get("cadoc") or "").strip()
        reg_empresa = (r.get("empresa") or "").strip()
        reg_motivo = (r.get("motivo") or "").strip()
        if not reg_motivo: continue
        if emp_lower and reg_empresa:
            reg_lower = reg_empresa.lower()
            if emp_lower != reg_lower and emp_lower not in reg_lower and reg_lower not in emp_lower:
                continue
        score = 0
        if cadoc and reg_cadoc and cadoc.upper() == reg_cadoc.upper(): score += 15
        if empresa and reg_empresa and (emp_lower in reg_lower or reg_lower in emp_lower): score += 10
        if r.get("tipo") == tipo: score += 5
        if score > 0:
            candidatos.append((score, reg_motivo))
    candidatos.sort(key=lambda x: -x[0])
    if candidatos and tipo != "RESPOSTA_EM_OUTRO_EMAIL":
        return candidatos[0][1]
    # Heurísticas por tipo (RESPOSTA_EM_OUTRO_EMAIL sempre usa heurística)
    if tipo == "ACAO_INTERNA":
        if empresa and cadoc:
            return f"Finaud deve gerar e enviar {cadoc} para {empresa}" + (f". Prazo: {prazo_str}" if prazo_str else "")
        return f"Aguardando ação interna da Finaud" + (f" — prazo {prazo_str}" if prazo_str else "")
    if tipo == "ENTREGA_CLIENTE":
        if empresa and cadoc:
            return f"Aguardando {empresa} enviar extratos/arquivos para {cadoc}" + (f". Prazo: {prazo_str}" if prazo_str else "")
        return f"Aguardando entrega do cliente" + (f" — prazo {prazo_str}" if prazo_str else "")
    if tipo == "RESPOSTA_CLIENTE":
        if empresa:
            return f"Aguardando resposta de {empresa}"
        return "Aguardando resposta do cliente"
    if tipo == "RESPOSTA_EM_OUTRO_EMAIL":
        return "Resposta em outro e-mail (ex.: TVM, Dep a Vista). Confirmar manualmente quando recebido."
    fallback = f"Aguardando — {cadoc or 'caso'}" + (f" (prazo {prazo_str})" if prazo_str else "")
    return fallback if fallback.strip() else "Aguardando resposta ou entrega conforme combinado."



def _primeiro_indice_bloco_encaminhado(texto: str):
    """
    Primeira posição onde começa um bloco tipo encaminhamento (Outlook PT ou Gmail EN),
    alinhado à heurística do script 08 / modal operacional. Retorna None se não houver.
    """
    if not texto or not isinstance(texto, str):
        return None
    t = texto.replace("\r\n", "\n")
    idx = 0
    while idx < len(t):
        inicio_pos = -1
        tag_len = 1
        for tag in ("\nDe:", "\nFrom:", "De:", "From:"):
            p = t.find(tag, idx)
            if p != -1 and (inicio_pos == -1 or p < inicio_pos):
                inicio_pos = p
                tag_len = len(tag)
        if inicio_pos == -1:
            return None
        resto = t[inicio_pos:]
        tem_outlook = (
            ("Enviada em:" in resto or "Enviadas:" in resto)
            and "Assunto:" in resto
        )
        tem_gmail = "Date:" in resto and "Subject:" in resto
        if tem_outlook or tem_gmail:
            return inicio_pos
        idx = inicio_pos + max(tag_len, 1)
    return None


def _corpo_mensagem_para_resumo_ia(msg: dict) -> str:
    """
    Corpo enviado ao prompt de resumo IA: remove o trecho de citação/encadeamento após o primeiro
    bloco De:/From: válido, para não repetir na mensagem de resposta o texto que já existe como
    mensagem própria na thread (reduz tokens e alinha com extrair encaminhados no integrador).
    """
    s = (msg.get("corpo_limpo") or msg.get("corpo") or "").strip()
    if not s:
        return ""
    s = re.sub(r"\nTo unsubscribe from this group[^\n]*", "", s, flags=re.I).strip()
    cut = _primeiro_indice_bloco_encaminhado(s)
    if cut is not None and cut > 0:
        head = s.replace("\r\n", "\n")[:cut].strip()
        if head:
            s = head
    return s


PROMPT_RESUMO_INTERACOES = """Você é um especialista em análise de e-mails regulatórios (DDR, DLO, DRL, Bacen).

Leia TODO o conteúdo da conversa abaixo e retorne UM ÚNICO JSON com exatamente estas chaves:

{
  "resumo_interacoes": [
    {
      "ordem": 1,
      "quem": "Nome completo do remetente",
      "lado": "FINAUD ou CLIENTE",
      "data": "data/hora da mensagem",
      "acao": "em uma frase: o que essa pessoa fez (ex: 'envia texto para cliente encaminhar ao Bacen via CRD')",
      "conteudo_chave": "resumo dos dados importantes dessa mensagem em 1-3 frases (valores, prazos, decisões, compromissos)"
    }
  ],
  "motivo_em_blocos": "Texto em blocos: 'Fulano envia... Beltrano responde... Pendente: ...'",
  "responsabilidade_semantica": "FINAUD ou CLIENTE",
  "explicacao_caso": "Em 2-4 frases, explique este caso para alguém que não leu os e-mails. Inclua: contexto, o que foi feito, o que está pendente e de quem."
}

Regras:
- responsabilidade_semantica = quem deve agir AGORA (não necessariamente quem enviou a última mensagem)
- Se Finaud orientou o cliente a encaminhar ao Bacen e o cliente respondeu que enviará → responsabilidade = CLIENTE (aguardando retorno)
- Se o cliente enviou dados/anexos para Finaud processar → responsabilidade = FINAUD
- conteudo_chave deve incluir números, prazos e decisões técnicas quando relevantes (será concatenado em motivo_aprendizado para a IA aprender)

Conversa:
---
"""


def _montar_texto_thread_resumo(thread):
    """Monta texto da conversa a partir das mensagens (corpo sem encadeamento De:/Assunto: para a IA)."""
    msgs = thread.get("mensagens") or []
    partes = []
    for i, m in enumerate(msgs):
        co = m.get("contato_origem") or {}
        cd = m.get("contato_destino") or {}
        de = co.get("nome") or co.get("email") or "?"
        para = cd.get("nome") or cd.get("email") or "?"
        lado = co.get("lado") or "?"
        data = m.get("data_email") or m.get("timestamp") or ""
        corpo = _corpo_mensagem_para_resumo_ia(m)
        if len(corpo) > 4000:
            corpo = corpo[:4000] + "\n[... texto truncado ...]"
        partes.append(f"[Mensagem {i+1}] {data} | {lado} | De: {de} → Para: {para}\n{corpo}")
    return "\n\n---\n\n".join(partes) if partes else ""


def _gerar_resumo_interacoes_ia(thread):
    """Chama OpenAI para gerar resumo_interacoes, motivo_em_blocos, motivo_aprendizado."""
    texto = _montar_texto_thread_resumo(thread)
    if not texto.strip():
        texto = (thread.get("conversa_unificada") or "")[:12000]
    if not texto.strip():
        return {"error": "Thread sem conteúdo de mensagens"}
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"error": "OPENAI_API_KEY não configurada"}
    prompt = PROMPT_RESUMO_INTERACOES + texto + "\n---"
    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        raw = (resp.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.replace("```json", "").replace("```", "").strip()
        out = json.loads(raw)
        resumo = out.get("resumo_interacoes") or []
        if resumo:
            partes = [
                f"{r.get('quem', '?')}: {r.get('conteudo_chave', '').strip()}"
                for r in resumo
                if r.get("conteudo_chave")
            ]
            out["motivo_aprendizado"] = " | ".join(partes)
        return out
    except json.JSONDecodeError as e:
        return {"error": f"Resposta da IA inválida: {e}"}
    except Exception as e:
        logger.error(f"Erro ao gerar resumo IA: {e}", exc_info=True)
        return {"error": str(e)}


@app.route('/api/resumo_interacoes', methods=['POST'])
@login_required
def api_resumo_interacoes():
    """Gera resumo estruturado da thread via IA (resumo_interacoes, motivo_aprendizado)."""
    dados = request.get_json() or {}
    thread_id = dados.get("threadId")
    conteudo = dados.get("conteudo") or {}
    if not thread_id:
        return jsonify({"error": "threadId é obrigatório"}), 400
    # Usar conteudo enviado pelo frontend (já tem mensagens) ou carregar do 03
    if conteudo.get("mensagens"):
        thread = dict(conteudo) if isinstance(conteudo, dict) else {"mensagens": conteudo}
        if "threadId" not in thread:
            thread["threadId"] = thread_id
    else:
        try:
            with open(BASE_DADOS, "r", encoding="utf-8") as f:
                dados_json = json.load(f)
            threads = dados_json.get("threads") or []
            thread = next((t for t in threads if t.get("threadId") == thread_id), None)
            if not thread:
                return jsonify({"error": "Thread não encontrada"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    resultado = _gerar_resumo_interacoes_ia(thread)
    if resultado.get("error"):
        return jsonify({"error": resultado["error"]}), 500
    return jsonify(resultado)


@app.route('/api/sugerir_aguardo', methods=['POST'])
@login_required
def api_sugerir_aguardo():
    """Sugere motivo, tipo, prazo e CADOC. Usa heurísticas e aprendizados anteriores."""
    dados = request.get_json() or {}
    thread_id = dados.get("threadId")
    conteudo = dados.get("conteudo") or {}
    if not thread_id:
        return jsonify({"motivo": "", "tipo": "ACAO_INTERNA", "prazo": "", "cadoc": ""}), 200

    mensagens = conteudo.get("mensagens") if isinstance(conteudo, dict) else (conteudo if isinstance(conteudo, list) else [])
    latest = mensagens[-1] if (isinstance(mensagens, list) and mensagens) else {}
    cadoc = conteudo.get("cadoc") or latest.get("cadoc") or ""
    if not cadoc and (conteudo.get("lista_prazos") or latest.get("lista_prazos")):
        lp = (conteudo.get("lista_prazos") or latest.get("lista_prazos") or [{}])
        cadoc = lp[0].get("cadoc", "") or ""
    empresa = conteudo.get("cliente") or latest.get("cliente", "") or ""
    assunto = conteudo.get("assunto") or conteudo.get("titulo") or latest.get("titulo") or latest.get("assunto", "") or ""
    lp = conteudo.get("lista_prazos") or latest.get("lista_prazos") or []
    prazo = ""
    if lp:
        raw = (lp[0].get("prazo_limite") or "").strip()
        prazo = _parse_prazo_to_iso(raw)
        if not prazo and len(lp) > 1:
            raw = (lp[-1].get("prazo_limite") or "").strip()
            prazo = _parse_prazo_to_iso(raw)

    historico = ""
    if mensagens:
        for m in mensagens[-3:]:
            if not isinstance(m, dict):
                continue
            h = _corpo_mensagem_para_resumo_ia(m) or (m.get("snippet") or "")
            historico += h[:300] + " "

    tipo = _inferir_tipo_aguardo(conteudo, latest, assunto)
    responsavel = conteudo.get("responsavel") or conteudo.get("responsavel_nome") or (latest.get("responsavel") or latest.get("responsavel_nome") if latest else "")
    motivo = _sugerir_motivo_aguardo(cadoc, empresa, tipo, assunto, lp, historico, conteudo=conteudo, latest=latest, responsavel=responsavel)
    return jsonify({"motivo": motivo, "tipo": tipo, "prazo": prazo, "cadoc": cadoc})


_CADOC_CARTAO_PERMITIDOS = frozenset({
    "DDR_2011", "DLO_2061", "DLI_2062", "DRL_2160", "DRM_2060", "4111", "S5",
    "SUPORTE", "DRSAC", "FORCAPITAL", "RETORNO_BACEN", "IGNORADO", "OUTROS", "FILTRADO_POR_DATA",
    "RISK_DRIVER_ALERTA", "RISK_DRIVER_RELATORIO", "RISK_DRIVER_RESP_AUTO",
    "FOGBUGZ", "LEIAUTES_BACEN",
})


@app.route("/api/cartao_override", methods=["POST"])
@login_required
def api_cartao_override():
    """
    Grava ajuste manual de categoria e/ou status por thread (JSON em painel_estado, sobrevive a deletar_carga).
    Corpo: { "threadId": "...", "cadoc": "DLO_2061" | null, "status": "aberto"|"aguardando"|"concluido"| null }
    Para remover: enviar null ou omitir, ou { "clear": true } para o threadId.
    """
    dados = request.get_json() or {}
    thread_id = (dados.get("threadId") or "").strip()
    if not thread_id:
        return jsonify({"status": "error", "message": "threadId é obrigatório"}), 400
    ovr = load_cartao_overrides()
    if not isinstance(ovr, dict):
        ovr = {}
    if dados.get("clear") is True:
        ovr.pop(thread_id, None)
        save_cartao_overrides(ovr)
        return jsonify({"status": "success", "cartao_overrides": ovr})
    rec = ovr.get(thread_id) if isinstance(ovr.get(thread_id), dict) else {}
    if not isinstance(rec, dict):
        rec = {}
    if "cadoc" in dados:
        c = dados.get("cadoc")
        if c is None or c == "":
            rec.pop("cadoc", None)
        else:
            c = str(c).strip()
            if c and c not in _CADOC_CARTAO_PERMITIDOS:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": f"CADOC inválido. Valores: {', '.join(sorted(_CADOC_CARTAO_PERMITIDOS))}",
                        }
                    ),
                    400,
                )
            if c:
                rec["cadoc"] = c
    if "status" in dados:
        s = dados.get("status")
        if s is None or s == "":
            rec.pop("status", None)
        else:
            s = str(s).strip().lower()
            if s not in ("aberto", "pendente", "aguardando", "concluido", "aberta"):
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "status deve ser: aberto | aguardando | concluido",
                        }
                    ),
                    400,
                )
            if s in ("pendente", "aberta"):
                s = "aberto"
            rec["status"] = s
    if not rec:
        ovr.pop(thread_id, None)
    else:
        ovr[thread_id] = rec
    save_cartao_overrides(ovr)
    return jsonify({"status": "success", "cartao_overrides": ovr})


@app.route('/api/marcar_aguardando', methods=['POST'])
@login_required
def api_marcar_aguardando():
    """Adiciona thread à lista de aguardando."""
    dados = request.get_json() or {}
    thread_id = dados.get("threadId")
    tipo = dados.get("tipo", "ACAO_INTERNA")
    motivo = (dados.get("motivo") or "").strip()
    prazo = (dados.get("prazo") or "").strip()
    cadoc = (dados.get("cadoc") or "").strip()
    assunto = (dados.get("assunto") or "").strip()
    empresa = (dados.get("empresa") or "").strip()
    responsavel = (dados.get("responsavel") or "").strip()

    if not thread_id:
        return jsonify({"status": "error", "message": "threadId é obrigatório"}), 400

    lista = _carregar_threads_aguardando()
    ids_existentes = {r.get("threadId") for r in lista if isinstance(r, dict) and r.get("threadId")}
    if thread_id in ids_existentes:
        return jsonify({"status": "error", "message": "Thread já está em aguardando"}), 400

    # Início do contador "dias em Aguardando" (Não resolvidos = REF − data_marcacao): preferir o dia
    # selecionado no calendário operacional; senão relógio do servidor.
    data_ref_raw = (dados.get("data_ref_operacional") or dados.get("dataRefOperacional") or "").strip()
    if data_ref_raw:
        dt_marc = _parse_data_ref(data_ref_raw)
        data_marcacao_str = dt_marc.strftime("%Y-%m-%d") if dt_marc else datetime.now().strftime("%Y-%m-%d")
    else:
        data_marcacao_str = datetime.now().strftime("%Y-%m-%d")

    # Guardar qtd_mensagens para detectar "nova resposta" (voltar para Pendente)
    qtd_msg = 0
    conteudo = dados.get("conteudo") or {}
    mensagens = conteudo.get("mensagens") if isinstance(conteudo, dict) else []
    if mensagens:
        qtd_msg = len(mensagens)
    else:
        try:
            with open(BASE_DADOS, "r", encoding="utf-8") as f:
                dados_json = json.load(f)
            thread = next((t for t in (dados_json.get("threads") or []) if t.get("threadId") == thread_id), None)
            if thread:
                qtd_msg = len(thread.get("mensagens") or [])
        except Exception:
            pass

    registro = {
        "threadId": thread_id,
        "assunto": assunto,
        "empresa": empresa,
        "cadoc": cadoc,
        "quem_gera": "",
        "responsavel": responsavel,
        "motivo": motivo or "Aguardando",
        "tipo": tipo,
        "data_marcacao": data_marcacao_str,
        "prazo": prazo[:10] if prazo else "",
        "status": "AGUARDANDO",
        "qtd_mensagens_no_fechamento": qtd_msg,
    }
    lista.append(registro)
    try:
        _salvar_threads_aguardando(lista)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    return jsonify({"status": "success", "registro": registro})

@app.route('/api/resolver_aguardo', methods=['POST'])
@login_required
def api_resolver_aguardo():
    """Remove thread da lista de aguardando (marcar como recebido)."""
    dados = request.get_json() or {}
    thread_id = dados.get("threadId")
    if not thread_id:
        return jsonify({"status": "error", "message": "threadId é obrigatório"}), 400

    lista = _carregar_threads_aguardando()
    nova_lista = [r for r in lista if isinstance(r, dict) and r.get("threadId") != thread_id]
    if len(nova_lista) == len(lista):
        return jsonify({"status": "error", "message": "Thread não encontrada em aguardando"}), 404
    try:
        _salvar_threads_aguardando(nova_lista)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    return jsonify({"status": "success", "message": "Removido de aguardando"})

@app.route('/api/normativos_resumo_dia')
@login_required
def api_normativos_resumo_dia():
    """Conta normas com impacto detectado na data de referência (dia da carga) — usado pela tela inicial."""
    data_ref = (request.args.get('data') or '').strip()[:10]
    try:
        registros = carregar_json(ARQUIVO_REGISTROS)
        if not isinstance(registros, list):
            registros = []
        total_impacto = 0
        for r in registros:
            if not isinstance(r, dict):
                continue
            data_leitura_raw = (r.get('data_leitura') or '').strip()
            try:
                data_leitura_iso = datetime.strptime(data_leitura_raw[:10], '%d/%m/%Y').strftime('%Y-%m-%d')
            except Exception:
                continue
            if data_leitura_iso != data_ref:
                continue
            for bloco in r.get('analise_detalhada_por_bloco') or []:
                if isinstance(bloco, dict) and bloco.get('impacto_detectado'):
                    total_impacto += 1
        return jsonify({"com_impacto": total_impacto, "data": data_ref})
    except Exception as e:
        logger.error(f"api_normativos_resumo_dia: {e}", exc_info=True)
        return jsonify({"com_impacto": None}), 500


@app.route('/normativos')
@login_required
def normativos():
    emails_auditados = carregar_json(ARQUIVO_REGISTROS)
    normativos_formatados = []
    for email in emails_auditados:
        data_ref = ""
        partes_assunto = email.get('assunto_email', '').split(' – ')
        if len(partes_assunto) > 1: data_ref = partes_assunto[-1].strip()
        blocos = email.get('analise_detalhada_por_bloco', [])
        for bloco in blocos:
            justificativa_final = bloco.get("resumo_analisado")
            if bloco.get("impacto_detectado"): justificativa_final = bloco.get("termo_justificativa")
            normativos_formatados.append({
                "norma": bloco.get("norma"),
                "titulo": bloco.get("norma"),
                "resumo": bloco.get("resumo_analisado"),
                "data_processamento": data_ref,
                "arquivo": bloco.get("arquivo_gerado"),
                "decisao": {"justificativa": justificativa_final, "impacto": bloco.get("impacto_detectado")},
                "status_fog": bloco.get("status_fogbugz")
            })
    return render_template('normativos_gerencial.html', normativos=normativos_formatados)

PASTA_EMAIL_ANEXOS = os.path.join(BASE_DIR, 'data', 'email_anexos')

@app.route('/anexos/<path:filename>')
@login_required
def serve_anexos(filename):
    """Serve arquivos de anexos de e-mail (imagens) para exibição no modal."""
    if not os.path.isdir(PASTA_EMAIL_ANEXOS):
        return "", 404
    # Segurança: garantir que filename não escape da pasta (../)
    if '..' in filename or filename.startswith('/'):
        return "", 404
    caminho = os.path.join(PASTA_EMAIL_ANEXOS, filename)
    if not os.path.isfile(caminho):
        return "", 404
    return send_from_directory(PASTA_EMAIL_ANEXOS, filename)

@app.route('/pdf/<path:filename>')
@login_required 
def serve_pdf(filename):
    import glob
    caminho_base = os.path.join(BASE_DIR, 'data', 'normativos_oficiais')
    caminho_direto = os.path.join(caminho_base, filename)
    if os.path.exists(caminho_direto): return send_from_directory(caminho_base, filename)
    if len(filename) > 5:
        arquivos_na_pasta = glob.glob(os.path.join(caminho_base, "*.pdf"))
        for caminho_completo in arquivos_na_pasta:
            nome_real = os.path.basename(caminho_completo)
            if filename[:5] in nome_real: return send_from_directory(caminho_base, nome_real)
    return send_from_directory(caminho_base, filename)

@app.route('/custos')
@login_required
def page_custos():
    if current_user.role != 'admin': return render_template('403.html'), 403
    stats = ler_estatisticas()
    hoje = datetime.now().strftime("%Y-%m-%d")
    from gemini_engine import get_model_name, MODELOS_DISPONIVEIS
    return render_template('monitor_custos_ia.html',
                           dados=stats.get(hoje, {}), historico=stats,
                           taxa_dolar=obter_dolar_atual(),
                           gemini_model_atual=get_model_name(),
                           gemini_modelos=MODELOS_DISPONIVEIS)

@app.route('/api/custos/gemini-model', methods=['POST'])
@login_required
def api_salvar_gemini_model():
    if current_user.role != 'admin':
        return jsonify({'ok': False, 'erro': 'Sem permissão'}), 403
    data = request.get_json(force=True, silent=True) or {}
    modelo = (data.get('modelo') or '').strip()
    from gemini_engine import salvar_model_name, MODELOS_DISPONIVEIS
    if modelo not in MODELOS_DISPONIVEIS:
        return jsonify({'ok': False, 'erro': f'Modelo inválido: {modelo}'}), 400
    salvar_model_name(modelo)
    return jsonify({'ok': True, 'modelo': modelo})

# ---------------------------------------------------------------------------
# IA Assistente
# ---------------------------------------------------------------------------
def _ia_construir_contexto(periodo: str) -> str:
    """Monta um contexto compacto com dados reais para o Gemini."""
    from datetime import date, timedelta
    import json as _json

    hoje = date.today()
    if periodo == "semana":
        data_ini = hoje - timedelta(days=hoje.weekday())          # segunda-feira
    elif periodo == "mes":
        data_ini = hoje.replace(day=1)
    else:  # 30 dias
        data_ini = hoje - timedelta(days=29)
    data_fim = hoje

    base = os.path.join(BASE_DIR, 'data', 'json', 'pipeline')

    def _load(fname, default=None):
        fp = os.path.join(base, fname)
        try:
            with open(fp, encoding='utf-8') as f:
                return _json.load(f)
        except Exception:
            return default if default is not None else []

    integ = _load('03_integrador_dados_site.json', {})
    eventos = integ.get('eventos', []) if isinstance(integ, dict) else []
    conc_auto = _load('threads_concluidas_auto.json')
    ag_auto   = _load('threads_aguardando_auto.json')
    fog_raw   = _load('massa_bruta_fog.json')

    # filtros de data
    def _in_periodo(ev):
        try:
            d_str = (ev.get('data_iso') or ev.get('data_conclusao') or ev.get('data') or '')[:10]
            d = date.fromisoformat(d_str)
            return data_ini <= d <= data_fim
        except Exception:
            return False

    ev_periodo = [e for e in eventos if _in_periodo(e)] if eventos else []
    conc_periodo = [r for r in (conc_auto or []) if _in_periodo(r)]
    ag_todos = list(ag_auto or [])

    # cadocs no período
    cadocs_cnt: dict = {}
    responsaveis_conc: dict = {}
    responsaveis_ag: dict = {}
    criticas_bacen: list = []
    for ev in ev_periodo:
        cadoc = ev.get('cadoc') or 'N/A'
        cadocs_cnt[cadoc] = cadocs_cnt.get(cadoc, 0) + 1
        if ev.get('retorno_bacen'):
            criticas_bacen.append({
                'cliente': ev.get('cliente', ''),
                'titulo': ev.get('titulo', '')[:80],
                'cadoc': cadoc,
                'data': (ev.get('data_iso') or '')[:10],
            })
    for r in conc_periodo:
        resp = r.get('responsavel') or r.get('alvo_triagem_auto') or '?'
        responsaveis_conc[resp] = responsaveis_conc.get(resp, 0) + 1
    ag_ids = {str(r.get('threadId')) for r in ag_todos if isinstance(r, dict)}
    # responsáveis em aguardando (lookup no integrador)
    tid_resp = {str(e.get('threadId')): e.get('responsavel', '?') for e in eventos if isinstance(e, dict)}
    for tid in ag_ids:
        resp = tid_resp.get(tid, '?')
        responsaveis_ag[resp] = responsaveis_ag.get(resp, 0) + 1

    # FOG
    fog_ativos, fog_parados, fog_criticos = [], [], []
    if isinstance(fog_raw, list):
        for caso in fog_raw:
            if not isinstance(caso, dict): continue
            status_str = str(caso.get('conteudo') or caso.get('status') or '').lower()
            is_ativo = 'fechado' not in status_str
            try:
                d_str = (caso.get('data_iso') or caso.get('data') or '')[:10]
                if 'T' in (caso.get('data_iso') or ''):
                    from datetime import datetime as _dt
                    d_str = _dt.fromisoformat(caso['data_iso']).strftime('%Y-%m-%d')
                idade = (hoje - date.fromisoformat(d_str)).days
            except Exception:
                idade = 0
            caso['_idade'] = idade
            if is_ativo:
                fog_ativos.append(caso)
                if idade >= 15: fog_criticos.append(caso)
                if idade >= 8:  fog_parados.append(caso)

    fog_ativos.sort(key=lambda x: x.get('_idade', 0), reverse=True)
    fog_top_parados = fog_ativos[:10]

    # Monta texto do contexto
    periodo_str = {
        'semana': f"Esta semana ({data_ini} a {data_fim})",
        'mes': f"Mês atual ({data_ini} a {data_fim})",
        '30dias': f"Últimos 30 dias ({data_ini} a {data_fim})",
    }.get(periodo, f"{data_ini} a {data_fim}")

    linhas = [
        f"# Contexto Oráculo 360 — {periodo_str}",
        "",
        f"## Atividade do período",
        f"- Eventos/e-mails processados: {len(ev_periodo)}",
        f"- Threads concluídas: {len(conc_periodo)}",
        f"- Threads aguardando retorno (total): {len(ag_ids)}",
        "",
        "## CADOCs com atividade no período",
    ]
    for cadoc, cnt in sorted(cadocs_cnt.items(), key=lambda x: -x[1])[:10]:
        linhas.append(f"  - {cadoc}: {cnt} eventos")

    linhas += ["", "## Threads concluídas por responsável/alvo"]
    for resp, cnt in sorted(responsaveis_conc.items(), key=lambda x: -x[1])[:10]:
        linhas.append(f"  - {resp}: {cnt} concluídas")

    linhas += ["", "## Threads aguardando por responsável (estimado)"]
    for resp, cnt in sorted(responsaveis_ag.items(), key=lambda x: -x[1])[:10]:
        linhas.append(f"  - {resp}: {cnt} aguardando")

    if criticas_bacen:
        linhas += ["", f"## Retornos/Críticas do BACEN no período ({len(criticas_bacen)} threads)"]
        for c in criticas_bacen[:15]:
            linhas.append(f"  - [{c['cadoc']}] {c['cliente']} — {c['titulo']} ({c['data']})")

    linhas += [
        "",
        f"## FOG — Casos ativos: {len(fog_ativos)} | Críticos (≥15 dias parados): {len(fog_criticos)}",
        "### Casos mais antigos (top 10):",
    ]
    for caso in fog_top_parados:
        resp = caso.get('responsavel') or caso.get('conteudo_extra', {}).get('responsavel', '?')
        titulo = str(caso.get('titulo') or caso.get('conteudo') or '')[:60]
        proj = caso.get('projeto') or '?'
        linhas.append(f"  - [{proj}] {titulo} — {caso.get('_idade', 0)} dias ({resp})")

    return "\n".join(linhas)


PERGUNTAS_CHIPS = [
    # Visão geral
    {"id": "resumo_geral",       "categoria": "Visão Geral",  "icone": "fa-chart-pie",
     "texto": "Resumo geral do período",
     "prompt_extra": "Faça um resumo executivo do período: volume de atividade, principais CADOCs, performance da equipe e pontos de atenção."},
    {"id": "gargalos",           "categoria": "Visão Geral",  "icone": "fa-exclamation-triangle",
     "texto": "Principais gargalos operacionais",
     "prompt_extra": "Identifique os principais gargalos: responsáveis com muitas threads aguardando, casos FOG críticos e CADOCs com maior volume sem resolução."},

    # BACEN
    {"id": "criticas_bacen",     "categoria": "BACEN",        "icone": "fa-university",
     "texto": "Críticas do BACEN e nossas respostas",
     "prompt_extra": "Liste as principais críticas/retornos do BACEN no período, quais clientes estão envolvidos e como a equipe está respondendo."},
    {"id": "status_remessas",    "categoria": "BACEN",        "icone": "fa-paper-plane",
     "texto": "Status das remessas regulatórias",
     "prompt_extra": "Como estão as remessas regulatórias no período? Quais CADOCs têm mais atividade e há algum sinal de atraso ou problema?"},

    # Operacional
    {"id": "aguardando_cliente", "categoria": "Operacional",  "icone": "fa-clock",
     "texto": "Threads aguardando retorno do cliente",
     "prompt_extra": "Analise as threads que estão aguardando retorno do cliente. Quem tem mais e em quais cadocs?"},
    {"id": "casos_prazo",        "categoria": "Operacional",  "icone": "fa-calendar-exclamation",
     "texto": "Casos com prazo crítico",
     "prompt_extra": "Há casos com prazo regulatório próximo? Analise o volume de atividade recente e sinalize alertas se identificar padrões de atraso."},
    {"id": "volume_cadoc",       "categoria": "Operacional",  "icone": "fa-layer-group",
     "texto": "Volume por CADOC no período",
     "prompt_extra": "Mostre o volume de atividade por CADOC no período, destacando os mais movimentados e os que merecem atenção."},

    # Equipe
    {"id": "produtividade",      "categoria": "Equipe",       "icone": "fa-users",
     "texto": "Produtividade por colaborador",
     "prompt_extra": "Analise a produtividade de cada colaborador: threads concluídas, threads aguardando e carga relativa. Quem está sobrecarregado?"},
    {"id": "distribuicao_carga", "categoria": "Equipe",       "icone": "fa-balance-scale",
     "texto": "Distribuição de carga na equipe",
     "prompt_extra": "A carga de trabalho está bem distribuída entre os colaboradores? Identifique desequilíbrios e sugira ajustes."},

    # FOG
    {"id": "fog_status",         "categoria": "FOG",          "icone": "fa-tasks",
     "texto": "Status dos casos FOG",
     "prompt_extra": "Qual é o status dos casos FOG? Quais estão ativos, quantos são críticos (≥15 dias) e há alguma tendência preocupante?"},
    {"id": "fog_parados",        "categoria": "FOG",          "icone": "fa-hourglass-half",
     "texto": "Casos FOG parados há mais tempo",
     "prompt_extra": "Liste e analise os casos FOG que estão parados há mais tempo. Quem é o responsável e qual é o projeto?"},
    {"id": "fog_por_projeto",    "categoria": "FOG",          "icone": "fa-folder-open",
     "texto": "FOG por projeto",
     "prompt_extra": "Mostre a distribuição dos casos FOG por projeto (RISK DRIVER, FORCAPITAL, GOVECOMPLIANCE, S5, FACTI). Qual projeto tem mais casos críticos?"},
]

@app.route('/ia-assistente')
@login_required
def ia_assistente_page():
    from gemini_engine import get_model_name, MODELOS_DISPONIVEIS
    return render_template('ia_assistente.html',
                           chips=PERGUNTAS_CHIPS,
                           gemini_model=get_model_name(),
                           gemini_modelos=MODELOS_DISPONIVEIS)

@app.route('/api/ia-assistente/perguntar', methods=['POST'])
@login_required
def api_ia_perguntar():
    data = request.get_json(force=True, silent=True) or {}
    chip_id = data.get('chip_id', '')
    periodo = data.get('periodo', '30dias')   # semana | mes | 30dias
    modelo  = data.get('modelo') or None

    # acha o chip
    chip = next((c for c in PERGUNTAS_CHIPS if c['id'] == chip_id), None)
    if not chip:
        return jsonify({'ok': False, 'erro': 'Pergunta não encontrada'}), 400

    try:
        contexto = _ia_construir_contexto(periodo)
    except Exception as e:
        return jsonify({'ok': False, 'erro': f'Erro ao carregar dados: {e}'}), 500

    prompt = (
        f"Você é o assistente de inteligência do Oráculo 360, sistema de monitoramento "
        f"regulatório da Finaud. Analise os dados abaixo e responda à pergunta do usuário "
        f"de forma objetiva, clara e em português. Use bullet points quando adequado.\n\n"
        f"PERGUNTA: {chip['prompt_extra']}\n\n"
        f"{contexto}\n\n"
        f"Responda com base estritamente nos dados acima. Se alguma informação não estiver "
        f"disponível, indique claramente."
    )

    try:
        from gemini_engine import chamar_gemini
        resposta = chamar_gemini(prompt, model_name=modelo)
        from monitor_consumo_ia import registrar_consumo
        registrar_consumo('gemini', 1, 'requests', 0.0)
    except ValueError as e:
        return jsonify({'ok': False, 'erro': str(e)}), 503
    except Exception as e:
        erro_str = str(e)
        # Quota / rate limit (429)
        if '429' in erro_str or 'quota' in erro_str.lower() or 'rate' in erro_str.lower():
            modelo_usado = modelo or 'o modelo atual'
            return jsonify({
                'ok': False,
                'erro': (
                    f'Limite de requisições atingido para {modelo_usado} (free tier). '
                    f'Aguarde alguns minutos e tente novamente, ou altere o modelo em '
                    f'Custos → APIs (ex.: gemini-1.5-flash-8b tem limites mais altos).'
                )
            }), 429
        # Erro de autenticação
        if '401' in erro_str or 'API_KEY' in erro_str or 'invalid' in erro_str.lower():
            return jsonify({
                'ok': False,
                'erro': 'Chave GEMINI_API_KEY inválida ou sem permissão. Verifique o arquivo .env.'
            }), 401
        # Erro genérico — mostra só a primeira linha para não poluir
        primeira_linha = erro_str.split('\n')[0][:200]
        return jsonify({'ok': False, 'erro': f'Erro Gemini: {primeira_linha}'}), 500

    return jsonify({'ok': True, 'resposta': resposta, 'chip': chip['texto'], 'periodo': periodo})

if __name__ == '__main__':
    print("Oraculo Web rodando em http://127.0.0.1:5000")
    app.run(debug=True, port=5000)