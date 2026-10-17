import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
 
NOME = "ChimpiAI"
OLLAMA_URL = "http://localhost:11434"
ARQUIVO_APP = "chimpiai.py"
AQUI = os.path.dirname(os.path.abspath(__file__))
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
 
 
def garantir_customtkinter():
    try:
        import customtkinter  # noqa: F401
    except ImportError:
        print("Instalando o customtkinter, aguarde...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter"])
 
 
garantir_customtkinter()
 
import customtkinter as ctk
from tkinter import filedialog
 
PASTA_PADRAO = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Programs", "ChimpiAI")
PASTA_CONFIG = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ChimpiAI")
ARQUIVO_CONFIG = os.path.join(PASTA_CONFIG, "config.json")
PADRAO = {
    "instalado": False,
    "tema": "dark",
    "modelo": "gemma3:4b",
    "usuario": None,
    "oauth": {
        "google": {"client_id": "", "client_secret": ""},
        "github": {"client_id": ""},
    },
}
 
CAMPOS = [
    ("Modelo do Ollama (obrigatório)", ("modelo",), False),
]
 
 
# ---------------------------------------------------------------- utilidades
def mesclar(base, novo):
    for k, v in novo.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            mesclar(base[k], v)
        else:
            base[k] = v
    return base
 
 
def pegar(cfg, caminho):
    for c in caminho:
        cfg = cfg[c]
    return cfg
 
 
def definir(cfg, caminho, valor):
    for c in caminho[:-1]:
        cfg = cfg[c]
    cfg[caminho[-1]] = valor
 
 
def carregar_config_existente():
    cfg = json.loads(json.dumps(PADRAO))
    try:
        with open(ARQUIVO_CONFIG, "r", encoding="utf-8") as f:
            mesclar(cfg, json.load(f))
    except Exception:
        pass
    return cfg
 
 
def executavel_sem_console():
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return pyw if os.path.exists(pyw) else exe
 
 
def criar_atalho(pasta):
    exe = executavel_sem_console().replace("'", "''")
    app = os.path.join(pasta, ARQUIVO_APP).replace("'", "''")
    trabalho = pasta.replace("'", "''")
    ps = (
        "$d=[Environment]::GetFolderPath('Desktop');"
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($d + '\\ChimpiAI.lnk');"
        "$s.TargetPath='" + exe + "';"
        "$s.Arguments='\"" + app + "\"';"
        "$s.WorkingDirectory='" + trabalho + "';"
        "$s.Description='ChimpiAI';"
        "$s.Save()"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, creationflags=SEM_JANELA)
 
 
# ---------------------------------------------------------------- ollama
def ollama_no_ar():
    try:
        urllib.request.urlopen(OLLAMA_URL + "/api/version", timeout=2).read()
        return True
    except Exception:
        return False
 
 
def aguardar_ollama(segundos):
    fim = time.time() + segundos
    while time.time() < fim:
        if ollama_no_ar():
            return True
        time.sleep(1)
    return False
 
 
def encontrar_ollama():
    achado = shutil.which("ollama")
    if achado:
        return achado
    candidatos = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Ollama", "ollama.exe"),
    ]
    for c in candidatos:
        if c and os.path.exists(c):
            return c
    return None
 
 
def instalar_ollama():
    """Roda o instalador oficial do Ollama (o mesmo comando: irm https://ollama.com/install.ps1 | iex)."""
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
         "irm https://ollama.com/install.ps1 | iex"],
        capture_output=True, text=True, creationflags=SEM_JANELA,
    )
 
 
def garantir_servidor(exe):
    """Deixa o Ollama ligado e respondendo."""
    if aguardar_ollama(3):
        return True
    if exe:
        try:
            subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=SEM_JANELA)
        except Exception:
            pass
    return aguardar_ollama(40)
 
 
def baixar_modelo(modelo, progresso):
    """Baixa o modelo pelo próprio Ollama e avisa o andamento."""
    corpo = json.dumps({"model": modelo, "stream": True}).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL + "/api/pull", data=corpo,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=3600) as r:
        for linha in r:
            linha = linha.decode("utf-8", errors="ignore").strip()
            if not linha:
                continue
            d = json.loads(linha)
            if d.get("error"):
                raise Exception(d["error"])
            total, feito = d.get("total"), d.get("completed")
            if total and feito is not None:
                progresso(feito / total, d.get("status", ""))
            else:
                progresso(None, d.get("status", ""))
 
 
# ---------------------------------------------------------------- instalador
class Instalador(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title("Instalador da ChimpiAI")
        self.geometry("780x620")
        self.minsize(660, 540)
 
        self.fila = queue.Queue()
        self.cfg_antiga = carregar_config_existente()
        self.pasta_var = ctk.StringVar(value=PASTA_PADRAO)
        self.atalho_var = ctk.BooleanVar(value=True)
        self.abrir_var = ctk.BooleanVar(value=True)
        self.tema_var = ctk.StringVar(value=self.cfg_antiga.get("tema", "dark"))
        self.entradas = {}
        self.valores = {}
        self.pasta_final = ""
 
        self.after(50, self.processar_fila)
        self.tela_boas_vindas()
 
    def chamar(self, fn, *args, **kwargs):
        self.fila.put((fn, args, kwargs))
 
    def processar_fila(self):
        try:
            while True:
                fn, args, kwargs = self.fila.get_nowait()
                try:
                    fn(*args, **kwargs)
                except Exception:
                    pass
        except queue.Empty:
            pass
        self.after(50, self.processar_fila)
 
    def limpar(self):
        for w in self.winfo_children():
            w.destroy()
 
    def quadro(self):
        q = ctk.CTkFrame(self)
        q.pack(expand=True, fill="both", padx=30, pady=30)
        return q
 
    # --- 1. boas-vindas
    def tela_boas_vindas(self):
        self.limpar()
        q = self.quadro()
        ctk.CTkLabel(q, text="ChimpiAI", font=("Segoe UI", 42, "bold")).pack(pady=(70, 6))
        ctk.CTkLabel(q, text="Instalador", font=("Segoe UI", 18)).pack()
        ctk.CTkLabel(q, text="Este assistente cria a ChimpiAI no seu computador, instala o Ollama\n"
                             "(a IA que roda no seu PC), baixa o modelo, configura\n"
                             "os logins e cria um atalho.",
                     font=("Segoe UI", 15), justify="center").pack(pady=30)
        ctk.CTkButton(q, text="Começar", height=44, width=240, command=self.tela_pasta).pack(pady=16)
 
    # --- 2. pasta e opções
    def tela_pasta(self):
        self.limpar()
        q = self.quadro()
        ctk.CTkLabel(q, text="Onde instalar?", font=("Segoe UI", 26, "bold")).pack(pady=(30, 16))
 
        linha = ctk.CTkFrame(q, fg_color="transparent")
        linha.pack(fill="x", padx=30)
        ctk.CTkEntry(linha, textvariable=self.pasta_var, height=40).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(linha, text="Procurar...", width=110, height=40, command=self.escolher_pasta).pack(side="right")
 
        ctk.CTkCheckBox(q, text="Criar atalho na área de trabalho", variable=self.atalho_var).pack(anchor="w", padx=34, pady=(26, 8))
        ctk.CTkCheckBox(q, text="Abrir a ChimpiAI quando terminar", variable=self.abrir_var).pack(anchor="w", padx=34, pady=8)
 
        self.aviso = ctk.CTkLabel(q, text="", text_color="#ff6b6b")
        self.aviso.pack(pady=8)
 
        botoes = ctk.CTkFrame(q, fg_color="transparent")
        botoes.pack(side="bottom", pady=16)
        ctk.CTkButton(botoes, text="Voltar", width=120, fg_color="gray40", command=self.tela_boas_vindas).pack(side="left", padx=8)
        ctk.CTkButton(botoes, text="Próximo", width=160, command=self.ir_config).pack(side="left", padx=8)
 
    def escolher_pasta(self):
        escolhida = filedialog.askdirectory(title="Escolha a pasta de instalação")
        if escolhida:
            self.pasta_var.set(os.path.join(os.path.normpath(escolhida), "ChimpiAI"))
 
    def ir_config(self):
        if not self.pasta_var.get().strip():
            self.aviso.configure(text="Escolha uma pasta.")
            return
        self.tela_config()
 
    # --- 3. configuração
    def tela_config(self):
        self.limpar()
        q = self.quadro()
        ctk.CTkLabel(q, text="Configuração", font=("Segoe UI", 26, "bold")).pack(pady=(20, 4))
        ctk.CTkLabel(q, text="O padrão (gemma3:4b) é bom para PCs com 8 GB. Se ficar pesado, use gemma3:1b. O login será feito pelos botões Google e GitHub no aplicativo.",
                     font=("Segoe UI", 13), wraplength=620).pack(pady=(0, 8))
 
        rolagem = ctk.CTkScrollableFrame(q)
        rolagem.pack(fill="both", expand=True, padx=16, pady=6)
        self.entradas = {}
        for titulo, caminho, secreto in CAMPOS:
            ctk.CTkLabel(rolagem, text=titulo, anchor="w").pack(fill="x", padx=10, pady=(8, 0))
            e = ctk.CTkEntry(rolagem, show="*" if secreto else "")
            e.pack(fill="x", padx=10)
            valor = self.valores.get(caminho) or pegar(self.cfg_antiga, caminho)
            if valor:
                e.insert(0, valor)
            self.entradas[caminho] = e
 
        ctk.CTkLabel(rolagem, text="Tema", anchor="w").pack(fill="x", padx=10, pady=(12, 0))
        ctk.CTkOptionMenu(rolagem, values=["dark", "light", "system"], variable=self.tema_var).pack(anchor="w", padx=10, pady=(0, 10))
 
        self.aviso = ctk.CTkLabel(q, text="", text_color="#ff6b6b")
        self.aviso.pack()
        botoes = ctk.CTkFrame(q, fg_color="transparent")
        botoes.pack(pady=10)
        ctk.CTkButton(botoes, text="Voltar", width=120, fg_color="gray40", command=self.voltar_pasta).pack(side="left", padx=8)
        ctk.CTkButton(botoes, text="Instalar", width=160, command=self.iniciar_instalacao).pack(side="left", padx=8)
 
    def guardar_entradas(self):
        for caminho, e in self.entradas.items():
            self.valores[caminho] = e.get().strip()
 
    def voltar_pasta(self):
        self.guardar_entradas()
        self.tela_pasta()
 
    # --- 4. instalando
    def iniciar_instalacao(self):
        self.guardar_entradas()
        if not self.valores.get(("modelo",)):
            self.aviso.configure(text="Escreva o nome do modelo (ex.: gemma3:4b).")
            return
        self.pasta_final = self.pasta_var.get().strip()
        self.limpar()
        q = self.quadro()
        ctk.CTkLabel(q, text="Instalando...", font=("Segoe UI", 28, "bold")).pack(pady=(100, 20))
        self.barra = ctk.CTkProgressBar(q, width=460)
        self.barra.set(0)
        self.barra.pack(pady=10)
        self.rotulo = ctk.CTkLabel(q, text="", font=("Segoe UI", 14), wraplength=560)
        self.rotulo.pack(pady=10)
        threading.Thread(target=self.executar, daemon=True).start()
 
    def etapa(self, valor, texto):
        self.chamar(self.barra.set, valor)
        self.chamar(self.rotulo.configure, text=texto)
 
    def executar(self):
        avisos = []
        try:
            pasta = self.pasta_final
            modelo = self.valores.get(("modelo",), "gemma3:4b")
 
            self.etapa(0.03, "Criando pastas...")
            os.makedirs(pasta, exist_ok=True)
            os.makedirs(PASTA_CONFIG, exist_ok=True)
 
            self.etapa(0.08, "Instalando as bibliotecas (pode demorar alguns minutos)...")
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "customtkinter"],
                capture_output=True, text=True, creationflags=SEM_JANELA,
            )
            if r.returncode != 0:
                raise Exception("Falha ao instalar as bibliotecas:\n" + (r.stderr or r.stdout)[-300:])
 
            self.etapa(0.2, "Criando a ChimpiAI...")
            with open(os.path.join(pasta, ARQUIVO_APP), "w", encoding="utf-8") as f:
                f.write(CODIGO_CHIMPIAI)
 
            self.etapa(0.25, "Salvando as configurações...")
            cfg = json.loads(json.dumps(PADRAO))
            mesclar(cfg, self.cfg_antiga)
            for caminho, valor in self.valores.items():
                definir(cfg, caminho, valor)
            cfg["tema"] = self.tema_var.get()
            cfg["usuario"] = None
            cfg["instalado"] = True
            cfg["pasta_instalacao"] = pasta
            with open(ARQUIVO_CONFIG, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
 
            # ---- Ollama
            exe = None
            if not ollama_no_ar():
                exe = encontrar_ollama()
                if not exe:
                    self.etapa(0.3, "Instalando o Ollama (pode demorar alguns minutos)...")
                    r = instalar_ollama()
                    exe = encontrar_ollama()
                    if not exe and r.returncode != 0:
                        avisos.append("Não consegui instalar o Ollama. Instale em ollama.com/download "
                                      f"e depois rode no CMD:  ollama pull {modelo}")
 
            self.etapa(0.45, "Ligando o Ollama...")
            if garantir_servidor(exe):
                ultimo = {"t": 0.0, "p": -1}
 
                def andamento(frac, status):
                    agora = time.time()
                    pct = int(frac * 100) if frac is not None else -1
                    if pct == ultimo["p"] and agora - ultimo["t"] < 0.5:
                        return
                    ultimo["t"], ultimo["p"] = agora, pct
                    texto = f"Baixando o modelo {modelo}: {pct}%" if pct >= 0 else f"Baixando o modelo {modelo}: {status}"
                    self.etapa(0.5 + 0.42 * (frac or 0), texto)
 
                try:
                    self.etapa(0.5, f"Baixando o modelo {modelo} (pode demorar bastante)...")
                    baixar_modelo(modelo, andamento)
                except Exception as erro:
                    avisos.append(f"Não consegui baixar o modelo ({erro}). No CMD rode:  ollama pull {modelo}")
            elif not avisos:
                avisos.append("Não consegui ligar o Ollama. Abra-o pelo Menu Iniciar e depois rode no CMD:  "
                              f"ollama pull {modelo}")
 
            if self.atalho_var.get():
                self.etapa(0.95, "Criando o atalho...")
                try:
                    criar_atalho(pasta)
                except Exception:
                    avisos.append("Não consegui criar o atalho. Abra pelo arquivo chimpiai.py na pasta de instalação.")
 
            self.etapa(1.0, "Pronto!")
            self.chamar(self.tela_final, avisos)
        except Exception as erro:
            self.chamar(self.tela_erro, str(erro))
 
    # --- 5. final
    def tela_final(self, avisos=None):
        self.limpar()
        q = self.quadro()
        ctk.CTkLabel(q, text="Instalação concluída!", font=("Segoe UI", 30, "bold")).pack(pady=(80, 16))
        ctk.CTkLabel(q, text=f"A ChimpiAI foi instalada em:\n{self.pasta_final}",
                     font=("Segoe UI", 14), justify="center", wraplength=600).pack(pady=8)
        for aviso in (avisos or []):
            ctk.CTkLabel(q, text=aviso, text_color="#ffb347", wraplength=600).pack(pady=6)
        ctk.CTkButton(q, text="Concluir", height=44, width=240, command=self.concluir).pack(pady=30)
 
    def tela_erro(self, mensagem):
        self.limpar()
        q = self.quadro()
        ctk.CTkLabel(q, text="Algo deu errado", font=("Segoe UI", 28, "bold"), text_color="#ff6b6b").pack(pady=(90, 16))
        ctk.CTkLabel(q, text=mensagem, wraplength=600, justify="left").pack(pady=8, padx=20)
        ctk.CTkButton(q, text="Tentar de novo", height=42, width=220, command=self.tela_config).pack(pady=24)
 
    def concluir(self):
        if self.abrir_var.get():
            try:
                subprocess.Popen([executavel_sem_console(), os.path.join(self.pasta_final, ARQUIVO_APP)],
                                 cwd=self.pasta_final)
            except Exception:
                pass
        self.destroy()
 
 
# ---------------------------------------------------------------- o app
CODIGO_CHIMPIAI = r'''import base64
import hashlib
import json
import os
import queue
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
 
import customtkinter as ctk
 
NOME = "ChimpiAI"
MODELO = "gemma3:4b"          # modelo padrão do Ollama (o instalador grava o escolhido no config.json)
OLLAMA_URL = "http://localhost:11434"
MAX_MENSAGENS = 40
PORTA = 8765
 
# ---- Logins (pode preencher aqui ou no instalador / config.json) ----
GOOGLE_CLIENT_ID = "990145632071-kivq2ea0q1hvekic8g1diu3vdbgevrk9.apps.googleusercontent.com"
GITHUB_CLIENT_ID = "Ov23liJFjuBkxw9CVnOr"
REDIRECT = f"http://localhost:{PORTA}/"
 
PASTA = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ChimpiAI")
ARQUIVO_CONFIG = os.path.join(PASTA, "config.json")
 
PADRAO = {
    "instalado": False,
    "tema": "dark",
    "modelo": "",
    "usuario": None,
    "oauth": {
        "google": {"client_id": "", "client_secret": ""},
        "github": {"client_id": ""},
    },
}
 
# ---------------------------------------------------------------- configuração
def mesclar(base, novo):
    for k, v in novo.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            mesclar(base[k], v)
        else:
            base[k] = v
    return base
 
 
def carregar_config():
    cfg = json.loads(json.dumps(PADRAO))
    try:
        with open(ARQUIVO_CONFIG, "r", encoding="utf-8") as f:
            mesclar(cfg, json.load(f))
    except Exception:
        pass
    # valores fixos do topo do arquivo entram quando o config.json está vazio
    for caminho, valor in ((("oauth", "google", "client_id"), GOOGLE_CLIENT_ID),
                           (("oauth", "github", "client_id"), GITHUB_CLIENT_ID)):
        if valor and not pegar(cfg, caminho):
            definir(cfg, caminho, valor)
    return cfg
 
 
def salvar_config(cfg):
    os.makedirs(PASTA, exist_ok=True)
    with open(ARQUIVO_CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
 
 
def pegar(cfg, caminho):
    for c in caminho:
        cfg = cfg[c]
    return cfg
 
 
def definir(cfg, caminho, valor):
    for c in caminho[:-1]:
        cfg = cfg[c]
    cfg[caminho[-1]] = valor
 
 
# ---------------------------------------------------------------- rede / login
def http_json(url, dados=None, headers=None):
    corpo = urllib.parse.urlencode(dados).encode() if dados is not None else None
    req = urllib.request.Request(url, data=corpo, headers=headers or {})
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "ChimpiAI")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        texto = e.read().decode("utf-8", errors="ignore")[:250]
        raise Exception(f"Erro {e.code}: {texto}")
    except urllib.error.URLError:
        raise Exception("Sem conexão com a internet.")
 
 
class Retorno:
    """Servidor local que recebe o código quando o navegador volta do login."""
 
    def __init__(self):
        self.resultado = {}
        resultado = self.resultado
 
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                if "code" in q or "error" in q:
                    resultado["q"] = q
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(
                        "<html><body style='font-family:sans-serif;text-align:center;margin-top:80px'>"
                        "<h2>Login concluído!</h2><p>Pode fechar esta aba e voltar para a ChimpiAI.</p>"
                        "</body></html>".encode("utf-8")
                    )
                else:
                    self.send_response(404)
                    self.end_headers()
 
            def log_message(self, *a):
                pass
 
        try:
            self.srv = HTTPServer(("127.0.0.1", PORTA), Handler)
        except OSError:
            raise Exception(f"A porta {PORTA} está ocupada. Feche outros programas e tente de novo.")
        self.srv.timeout = 1
 
    def esperar(self, state, segundos=180):
        fim = time.time() + segundos
        while "q" not in self.resultado and time.time() < fim:
            self.srv.handle_request()
        self.srv.server_close()
        q = self.resultado.get("q")
        if not q:
            raise Exception("Tempo esgotado. Tente entrar de novo.")
        if "error" in q:
            raise Exception("Login cancelado ou negado.")
        if q.get("state", [""])[0] != state:
            raise Exception("Resposta de login inválida.")
        return q["code"][0]
 
 
def login_google(cfg, avisar):
    g = cfg["oauth"]["google"]
    if not g["client_id"]:
        raise Exception("O login com Google não está configurado neste aplicativo.")
    verificador = secrets.token_urlsafe(64)
    desafio = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    retorno = Retorno()
    params = {
        "client_id": g["client_id"],
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "code_challenge": desafio,
        "code_challenge_method": "S256",
    }
    webbrowser.open("https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params))
    avisar("Faça o login no Google na janela do navegador...")
    codigo = retorno.esperar(state)
    tok = http_json("https://oauth2.googleapis.com/token", {
        "code": codigo,
        "client_id": g["client_id"],
        "redirect_uri": REDIRECT,
        "grant_type": "authorization_code",
        "code_verifier": verificador,
    })
    info = http_json("https://www.googleapis.com/oauth2/v3/userinfo",
                     headers={"Authorization": "Bearer " + tok["access_token"]})
    return {"nome": info.get("name") or info.get("email", "Usuário"),
            "email": info.get("email", ""), "provedor": "Google"}
 
 
def login_github(cfg, avisar):
    cid = cfg["oauth"]["github"]["client_id"]
    if not cid:
        raise Exception("O login com GitHub não está configurado neste aplicativo.")
    d = http_json("https://github.com/login/device/code", {"client_id": cid, "scope": "read:user"})
    avisar(f"No GitHub, digite o código:  {d['user_code']}")
    webbrowser.open(d["verification_uri"])
    intervalo = d.get("interval", 5)
    fim = time.time() + d.get("expires_in", 900)
    token = None
    while time.time() < fim:
        time.sleep(intervalo)
        r = http_json("https://github.com/login/oauth/access_token", {
            "client_id": cid,
            "device_code": d["device_code"],
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        })
        if "access_token" in r:
            token = r["access_token"]
            break
        erro = r.get("error")
        if erro == "authorization_pending":
            continue
        if erro == "slow_down":
            intervalo += 5
            continue
        raise Exception(r.get("error_description", erro or "Erro no login do GitHub."))
    if not token:
        raise Exception("Tempo esgotado. Tente entrar de novo.")
    u = http_json("https://api.github.com/user", headers={"Authorization": "Bearer " + token})
    return {"nome": u.get("name") or u.get("login", "Usuário"),
            "email": u.get("email") or "", "provedor": "GitHub"}
 
 
def ollama_stream(modelo, sistema, historico):
    """Manda a conversa para o Ollama (rodando no seu PC) e devolve o texto aos poucos."""
    corpo = json.dumps({
        "model": modelo,
        "messages": [{"role": "system", "content": sistema}] + historico,
        "stream": True,
        "options": {"num_ctx": 2048},   # contexto pequeno = menos memória
    }).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL + "/api/chat", data=corpo,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            for linha in r:
                linha = linha.decode("utf-8", errors="ignore").strip()
                if not linha:
                    continue
                dados = json.loads(linha)
                if dados.get("error"):
                    raise Exception(dados["error"])
                texto = dados.get("message", {}).get("content", "")
                if texto:
                    yield texto
                if dados.get("done"):
                    break
    except urllib.error.HTTPError as e:
        corpo_erro = e.read().decode("utf-8", errors="ignore")
        try:
            msg = json.loads(corpo_erro)["error"]
        except Exception:
            msg = corpo_erro[:200]
        if e.code == 404:
            msg = f"O modelo '{modelo}' não está baixado. No CMD rode:  ollama pull {modelo}"
        raise Exception(msg)
    except urllib.error.URLError:
        raise Exception("Não consegui falar com o Ollama. Abra o Ollama (ícone na barra do Windows) e tente de novo.")
 
 
# ---------------------------------------------------------------- aplicativo
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.cfg = carregar_config()
        ctk.set_appearance_mode(self.cfg.get("tema", "dark"))
        ctk.set_default_color_theme("blue")
        self.title(NOME)
        self.geometry("920x640")
        self.minsize(720, 520)
        self.fila = queue.Queue()
        self.historico = []
        self.ocupado = False
        self.after(50, self.processar_fila)
 
        if not self.cfg["instalado"]:
            self.tela_sem_instalacao()
        elif not self.cfg["usuario"]:
            self.tela_login()
        else:
            self.tela_chat()
 
    # --- utilidades
    def chamar(self, fn, *args, **kwargs):
        self.fila.put((fn, args, kwargs))
 
    def processar_fila(self):
        try:
            while True:
                fn, args, kwargs = self.fila.get_nowait()
                try:
                    fn(*args, **kwargs)
                except Exception:
                    pass
        except queue.Empty:
            pass
        self.after(50, self.processar_fila)
 
    def limpar(self):
        for w in self.winfo_children():
            w.destroy()
 
    def quadro(self):
        q = ctk.CTkFrame(self)
        q.pack(expand=True, fill="both", padx=40, pady=40)
        return q
 
    # --- sem instalação
    def tela_sem_instalacao(self):
        self.limpar()
        q = self.quadro()
        ctk.CTkLabel(q, text="ChimpiAI", font=("Fredoka One", 40, "bold")).pack(pady=(80, 10))
        ctk.CTkLabel(q, text="A ChimpiAI ainda não foi instalada.\n\n"
                             "Abra primeiro o installer_chimpiai.py e depois\n"
                             "use o atalho criado na área de trabalho.",
                     font=("Segoe UI", 16), justify="center").pack(pady=20)
        ctk.CTkButton(q, text="Fechar", height=44, width=200, command=self.destroy).pack(pady=20)
 
    # --- login
    def tela_login(self):
        self.limpar()
        q = self.quadro()
        ctk.CTkLabel(q, text="ChimpiAI", font=("Fredoka One", 38, "bold")).pack(pady=(50, 6))
        ctk.CTkLabel(q, text="Entre para continuar", font=("Segoe UI", 16)).pack(pady=(0, 24))
        self.botoes = []
        for nome, fn in (("Google", login_google), ("GitHub", login_github)):
            b = ctk.CTkButton(q, text=f"Continuar com {nome}", width=340, height=46,
                              command=lambda n=nome, f=fn: self.iniciar_login(n, f))
            b.pack(pady=6)
            self.botoes.append(b)
        self.status = ctk.CTkLabel(q, text="", wraplength=460, font=("Segoe UI", 14))
        self.status.pack(pady=16)
 
    def iniciar_login(self, nome, funcao):
        self.cfg = carregar_config()
        for b in self.botoes:
            b.configure(state="disabled")
        self.status.configure(text=f"Abrindo {nome}...", text_color=("black", "white"))
 
        def tarefa():
            try:
                usuario = funcao(self.cfg, lambda t: self.chamar(self.status.configure, text=t))
                self.chamar(self.login_ok, usuario)
            except Exception as erro:
                self.chamar(self.login_erro, str(erro))
 
        threading.Thread(target=tarefa, daemon=True).start()
 
    def login_ok(self, usuario):
        self.cfg["usuario"] = usuario
        salvar_config(self.cfg)
        self.tela_chat()
 
    def login_erro(self, mensagem):
        for b in self.botoes:
            b.configure(state="normal")
        self.status.configure(text=mensagem, text_color="#ff6b6b")
 
    # --- chat
    def tela_chat(self):
        self.limpar()
        self.historico = []
        usuario = self.cfg["usuario"]
 
        topo = ctk.CTkFrame(self, height=50)
        topo.pack(fill="x", padx=12, pady=(12, 6))
        ctk.CTkLabel(topo, text="ChimpiAI", font=("Segoe UI", 20, "bold")).pack(side="left", padx=14, pady=8)
        ctk.CTkButton(topo, text="Sair", width=70, command=self.sair).pack(side="right", padx=10)
        ctk.CTkButton(topo, text="Limpar", width=70, fg_color="gray40",
                      command=self.limpar_chat).pack(side="right")
        ctk.CTkLabel(topo, text=f"{usuario['nome']} ({usuario['provedor']})").pack(side="right", padx=14)
 
        self.caixa = ctk.CTkTextbox(self, wrap="word", font=("Segoe UI", 15))
        self.caixa.pack(fill="both", expand=True, padx=12, pady=6)
        self.caixa.configure(state="disabled")
 
        base = ctk.CTkFrame(self, fg_color="transparent")
        base.pack(fill="x", padx=12, pady=(6, 12))
        self.entrada = ctk.CTkEntry(base, height=42, placeholder_text="Pergunte qualquer coisa...")
        self.entrada.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entrada.bind("<Return>", self.enviar)
        self.botao_enviar = ctk.CTkButton(base, text="Enviar", width=100, height=42, command=self.enviar)
        self.botao_enviar.pack(side="right")
 
        self.escrever(f"ChimpiAI: Oi, {usuario['nome'].split()[0]}! Pode perguntar o que quiser.\n\n")
        self.entrada.focus()
 
    def escrever(self, texto):
        self.caixa.configure(state="normal")
        self.caixa.insert("end", texto)
        self.caixa.see("end")
        self.caixa.configure(state="disabled")
 
    def limpar_chat(self):
        self.historico = []
        self.caixa.configure(state="normal")
        self.caixa.delete("1.0", "end")
        self.caixa.configure(state="disabled")
        self.escrever("ChimpiAI: Memória apagada.\n\n")
 
    def sair(self):
        self.cfg["usuario"] = None
        salvar_config(self.cfg)
        self.tela_login()
 
    def enviar(self, _=None):
        texto = self.entrada.get().strip()
        if not texto or self.ocupado:
            return
        self.entrada.delete(0, "end")
        self.escrever(f"Você: {texto}\n\nChimpiAI: ")
        self.historico.append({"role": "user", "content": texto})
        self.historico = self.historico[-MAX_MENSAGENS:]
        while self.historico and self.historico[0]["role"] != "user":
            self.historico.pop(0)
        self.ocupado = True
        self.botao_enviar.configure(state="disabled")
        threading.Thread(target=self.responder, daemon=True).start()
 
    def responder(self):
        try:
            modelo = self.cfg.get("modelo") or MODELO
            sistema = (
                f"Você é a {NOME}, uma inteligência artificial assistente criada pelo Chimpi. "
                "Responda sempre em português do Brasil, de forma direta, clara e amigável, "
                "a menos que a pessoa escreva em outro idioma. "
                "Ajude com qualquer assunto: perguntas, estudos, programação, textos, ideias, contas e o que mais vier. "
                "Se não souber algo, diga que não sabe em vez de inventar. "
                f"A pessoa se chama {self.cfg['usuario']['nome']}."
            )
            resposta = ""
            for pedaco in ollama_stream(modelo, sistema, self.historico):
                resposta += pedaco
                self.chamar(self.escrever, pedaco)
            if not resposta:
                raise Exception("O modelo não devolveu resposta. Tente de novo.")
            self.historico.append({"role": "assistant", "content": resposta})
            self.chamar(self.escrever, "\n\n")
        except Exception as erro:
            if self.historico and self.historico[-1]["role"] == "user":
                self.historico.pop()
            self.chamar(self.escrever, f"[erro: {erro}]\n\n")
        finally:
            self.chamar(self.liberar)
 
    def liberar(self):
        self.ocupado = False
        self.botao_enviar.configure(state="normal")
        self.entrada.focus()
 
 
if __name__ == "__main__":
    App().mainloop()
'''
 
 
if __name__ == "__main__":
    Instalador().mainloop()
 