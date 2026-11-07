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
            with open(os.path.join(pasta, "support_notice.py"), "w", encoding="utf-8") as f:
                f.write(SUPPORT_NOTICE_CODE)
 
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
SUPPORT_NOTICE_CODE = "\"\"\"Non-blocking, read-only support checks for Chimpi desktop applications.\n\nNo telemetry, automatic downloads, credentials, installation or forced exit.\nPolicy and messages are bundled so an offline startup remains useful.\n\"\"\"\nfrom __future__ import annotations\n\nimport copy\nimport datetime as dt\nimport json\nimport locale\nimport os\nimport queue\nimport re\nimport subprocess\nimport sys\nimport threading\nimport urllib.parse\nimport urllib.request\nimport webbrowser\n\nPOLICY = {\"schema\": 1, \"verified_at\": \"2026-11-07\", \"ends_at\": \"2026-11-04T00:00:00Z\", \"table\": \"https://chimpi-hackintosh.github.io/ChimpiBlender-Online/support.html\", \"apps\": {\"OpenCore-Helper\": {\"name\": \"OpenCore Helper\", \"repo\": \"OpenCore-Helper\", \"minimum\": \"3.0.2\", \"tag\": \"v3.0.2\", \"preview\": False, \"edition\": None, \"url\": \"https://github.com/Chimpi-hackintosh/OpenCore-Helper/releases/tag/v3.0.2\", \"windows_setup\": {\"tag\": \"v3.0.2\", \"min_build\": 22000, \"digest\": \"sha256:a010669abb6cce810dab00434c0fd220913241fde3f3f8dd5e2a248972367022\"}, \"status\": \"published\"}, \"SnoopyOS-Lite\": {\"name\": \"SnoopyOS Lite\", \"repo\": \"SnoopyOS-Image\", \"minimum\": \"0.1.3\", \"tag\": \"v0.1-lite.3\", \"preview\": True, \"edition\": \"lite\", \"url\": \"https://github.com/Chimpi-hackintosh/SnoopyOS-Image/releases/tag/v0.1-lite.3\", \"status\": \"preview\"}, \"SnoopyOS-Games\": {\"name\": \"SnoopyOS Games\", \"repo\": \"SnoopyOS-Image\", \"minimum\": \"0.2.1\", \"tag\": \"v0.2-games.1\", \"preview\": True, \"edition\": \"games\", \"url\": \"https://github.com/Chimpi-hackintosh/SnoopyOS-Image/releases/tag/v0.2-games.1\", \"status\": \"preview\"}, \"ChimpiAI\": {\"name\": \"ChimpiAI\", \"repo\": \"ChimpiAI\", \"minimum\": \"1.1.0\", \"tag\": \"v1.1.0\", \"preview\": False, \"edition\": None, \"url\": \"https://github.com/Chimpi-hackintosh/ChimpiAI/releases/tag/v1.1.0\", \"status\": \"published\", \"artifact_digest\": \"sha256:27d098505ce518b01793ad7c3435a3557363bf26359248c03efa336274e7da46\"}, \"WinSIMU\": {\"name\": \"WinSIMU\", \"repo\": \"WinSIMU\", \"minimum\": \"0.1.0\", \"tag\": \"v0.1.0-alpha\", \"preview\": True, \"edition\": None, \"url\": \"https://github.com/Chimpi-hackintosh/WinSIMU/releases/tag/v0.1.0-alpha\", \"status\": \"preview\"}, \"ChimpiCode\": {\"name\": \"ChimpiCode\", \"repo\": \"ChimpiCode\", \"minimum\": \"1.1.0\", \"tag\": \"v1.1.0-preview.3\", \"preview\": True, \"edition\": None, \"url\": \"https://github.com/Chimpi-hackintosh/ChimpiCode/releases/tag/v1.1.0-preview.3\", \"status\": \"preview\"}, \"ChimpiBridge\": {\"name\": \"ChimpiBridge\", \"repo\": \"ChimpiBridge\", \"minimum\": \"0.1.1\", \"tag\": \"v0.1.1\", \"preview\": True, \"edition\": None, \"url\": \"https://github.com/Chimpi-hackintosh/ChimpiBridge/releases/tag/v0.1.1\", \"status\": \"preview\"}, \"ChimpiShare\": {\"name\": \"ChimpiShare\", \"repo\": \"ChimpiShare\", \"minimum\": \"0.1.0\", \"tag\": \"v0.1.0\", \"preview\": True, \"edition\": None, \"url\": \"https://github.com/Chimpi-hackintosh/ChimpiShare/releases/tag/v0.1.0\", \"status\": \"preview\"}, \"ChimpiConstrucoes\": {\"name\": \"ChimpiConstruções\", \"repo\": \"ChimpiConstrucoes\", \"minimum\": None, \"tag\": None, \"preview\": True, \"edition\": None, \"url\": \"https://github.com/Chimpi-hackintosh/ChimpiConstrucoes\", \"status\": \"source\"}, \"ChimpiBlender-Online\": {\"name\": \"ChimpiBlender Online\", \"repo\": \"ChimpiBlender-Online\", \"minimum\": None, \"tag\": None, \"preview\": False, \"edition\": None, \"url\": \"https://chimpi-hackintosh.github.io/ChimpiBlender-Online/\", \"status\": \"website\", \"web_revision\": 20261102}, \"ChimpiNotch\": {\"name\": \"ChimpiNotch\", \"repo\": \"ChimpiNotch\", \"minimum\": \"1.0.4\", \"tag\": \"v1.0.4\", \"preview\": False, \"edition\": None, \"url\": \"https://github.com/Chimpi-hackintosh/ChimpiNotch/releases/tag/v1.0.4\", \"status\": \"published\"}, \"Chimpi3D-Installer\": {\"name\": \"Chimpi3D\", \"repo\": \"Chimpi3D-Installer\", \"minimum\": \"0.3.1\", \"tag\": \"v0.3.1-build-11\", \"preview\": False, \"edition\": None, \"url\": \"https://github.com/Chimpi-hackintosh/Chimpi3D-Installer/releases/tag/v0.3.1-build-11\", \"status\": \"published\"}, \"ChimpiNFC\": {\"name\": \"ChimpiNFC\", \"repo\": \"ChimpiNFC\", \"minimum\": \"0.1.0\", \"tag\": \"v0.1.0-build-2\", \"preview\": True, \"edition\": None, \"url\": \"https://github.com/Chimpi-hackintosh/ChimpiNFC/releases/tag/v0.1.0-build-2\", \"status\": \"preview\"}, \"Chimpi-Find-My-Kids\": {\"name\": \"Chimpi Find My Kids\", \"repo\": \"Chimpi-Find-My-Kids\", \"minimum\": \"1.3.1-preview.1\", \"tag\": \"v1.3.1-preview.1\", \"preview\": True, \"edition\": None, \"url\": \"https://github.com/Chimpi-hackintosh/Chimpi-Find-My-Kids/releases/tag/v1.3.1-preview.1\", \"status\": \"preview\", \"artifact_digest\": \"sha256:4baafa8869367118d174bfb2c35464804e07341a708787bb602c712a66145cee\"}, \"Chimpi-Parents-Find-My-Kids\": {\"name\": \"Chimpi Parents Find My Kids\", \"repo\": \"Chimpi-Parents-Find-My-Kids\", \"minimum\": \"1.3.1-preview.1\", \"tag\": \"v1.3.1-preview.1\", \"preview\": True, \"edition\": None, \"url\": \"https://github.com/Chimpi-hackintosh/Chimpi-Parents-Find-My-Kids/releases/tag/v1.3.1-preview.1\", \"status\": \"preview\", \"artifact_digest\": \"sha256:df2bf039ef8b1bfae0690ebac83d4fdd40a3f0acd980f183dbe6130d8f67950b\"}, \"Earth-Blender\": {\"name\": \"Earth-Blender\", \"repo\": \"Earth-Blender\", \"minimum\": None, \"tag\": None, \"preview\": False, \"edition\": None, \"url\": \"https://github.com/Chimpi-hackintosh/Earth-Blender\", \"status\": \"source\"}, \"ChimpiBypass\": {\"name\": \"ChimpiBypass\", \"repo\": \"ChimpiBypass\", \"minimum\": None, \"tag\": None, \"preview\": True, \"edition\": None, \"url\": \"https://github.com/Chimpi-hackintosh/ChimpiBypass\", \"status\": \"source\"}, \"ChimpiKids\": {\"name\": \"ChimpiKids\", \"repo\": \"ChimpiKids\", \"minimum\": \"1.0.0-demo.1\", \"tag\": \"v1.0.0-demo.1\", \"preview\": True, \"edition\": None, \"url\": \"https://github.com/Chimpi-hackintosh/ChimpiKids/releases/tag/v1.0.0-demo.1\", \"status\": \"preview\", \"artifact_digest\": \"sha256:e156571e4d32c24c28d1ea553526d195fe1fa936bc7e7d2922df2ab91d86b85b\"}, \"ChimpiNature\": {\"name\": \"ChimpiNature\", \"repo\": \"ChimpiNature\", \"minimum\": \"1.0.0\", \"tag\": \"v1.0.0\", \"preview\": True, \"edition\": None, \"url\": \"https://github.com/Chimpi-hackintosh/ChimpiNature/releases/tag/v1.0.0\", \"status\": \"preview\", \"artifact_digest\": \"sha256:198ae5df5393161b7ac91670fb354fc0fdfc7d5f4e4858bd62552cfef6b4f0ff\"}}}\nMESSAGES = {'en': {'before': 'Your version is about to lose support', 'after': 'Your version no longer receives security updates', 'body_before': 'Older versions of {app} will stop receiving security updates on 4 November 2026', 'body_after': 'Older versions of {app} have not received security updates since 4 November 2026', 'risk': 'Software without security fixes may remain exposed to vulnerabilities — update from the official project page', 'versions': 'Installed: {current} · Minimum supported: {minimum} · Available: {latest}', 'update': 'Update', 'later': 'Later', 'table': 'Apps and support', 'app': 'App / website', 'available': 'Available version', 'support': 'Support / action', 'published': 'Published', 'preview': 'Preview — may be unstable', 'source': 'No downloadable release — no upgrade required yet', 'website': 'Website — reload for the latest code', 'intro': 'Versions below those listed lose security support on 4 November 2026 — the date is 00:00 UTC', 'intro_after': 'Versions below those listed no longer receive security updates as of 4 November 2026 at 00:00 UTC', 'legacy': 'Already installed versions without an update checker need a manual update — this notice does not imply an infection or install anything automatically', 'footer': 'Catalog verified on {date} — release links are official, source changes awaiting review are not new releases'}, 'pt': {'before': 'Sua versão está prestes a não ser suportada', 'after': 'Sua versão não recebe mais atualizações de segurança', 'body_before': 'As versões antigas do {app} deixarão de receber atualizações de segurança em 4 de novembro de 2026', 'body_after': 'As versões antigas do {app} não recebem atualizações de segurança desde 4 de novembro de 2026', 'risk': 'Software sem correções de segurança pode ficar exposto a falhas — atualize pela página oficial do projeto', 'versions': 'Instalada: {current} · Mínima suportada: {minimum} · Disponível: {latest}', 'update': 'Atualizar', 'later': 'Depois', 'table': 'Apps e suporte', 'app': 'App / site', 'available': 'Versão disponível', 'support': 'Suporte / ação', 'published': 'Publicada', 'preview': 'Prévia — pode ter instabilidade', 'source': 'Sem lançamento para download — ainda sem atualização exigida', 'website': 'Site — recarregue para receber o código atual', 'intro': 'Versões abaixo das listadas perdem o suporte de segurança em 4 de novembro de 2026, às 00h UTC', 'intro_after': 'Versões abaixo das listadas não recebem atualizações de segurança desde 4 de novembro de 2026, às 00h UTC', 'legacy': 'Versões já instaladas sem verificador precisam de atualização manual — este aviso não indica infecção nem instala nada automaticamente', 'footer': 'Catálogo conferido em {date} — os links são oficiais e alterações aguardando revisão ainda não são novos lançamentos'}, 'es': {'before': 'Tu versión está a punto de perder soporte', 'after': 'Tu versión ya no recibe actualizaciones de seguridad', 'body_before': 'Las versiones antiguas de {app} dejarán de recibir actualizaciones de seguridad el 4 de noviembre de 2026', 'body_after': 'Las versiones antiguas de {app} no reciben actualizaciones de seguridad desde el 4 de noviembre de 2026', 'risk': 'El software sin correcciones de seguridad puede quedar expuesto a vulnerabilidades — actualiza desde la página oficial', 'versions': 'Instalada: {current} · Mínima compatible: {minimum} · Disponible: {latest}', 'update': 'Actualizar', 'later': 'Más tarde', 'table': 'Apps y soporte'}, 'fr': {'before': 'Votre version va bientôt perdre son support', 'after': 'Votre version ne reçoit plus de mises à jour de sécurité', 'body_before': 'Les anciennes versions de {app} ne recevront plus de mises à jour de sécurité à partir du 4 novembre 2026', 'body_after': 'Les anciennes versions de {app} ne reçoivent plus de mises à jour de sécurité depuis le 4 novembre 2026', 'risk': 'Un logiciel sans correctifs de sécurité peut rester vulnérable — mettez-le à jour depuis la page officielle', 'versions': 'Installée : {current} · Minimum pris en charge : {minimum} · Disponible : {latest}', 'update': 'Mettre à jour', 'later': 'Plus tard', 'table': 'Apps et support'}, 'de': {'before': 'Deine Version wird bald nicht mehr unterstützt', 'after': 'Deine Version erhält keine Sicherheitsupdates mehr', 'body_before': 'Ältere Versionen von {app} erhalten ab dem 4. November 2026 keine Sicherheitsupdates mehr', 'body_after': 'Ältere Versionen von {app} erhalten seit dem 4. November 2026 keine Sicherheitsupdates mehr', 'risk': 'Software ohne Sicherheitskorrekturen kann angreifbar bleiben — aktualisiere sie über die offizielle Projektseite', 'versions': 'Installiert: {current} · Unterstütztes Minimum: {minimum} · Verfügbar: {latest}', 'update': 'Aktualisieren', 'later': 'Später', 'table': 'Apps und Support'}, 'it': {'before': 'La tua versione sta per perdere il supporto', 'after': 'La tua versione non riceve più aggiornamenti di sicurezza', 'body_before': 'Le versioni precedenti di {app} non riceveranno più aggiornamenti di sicurezza dal 4 novembre 2026', 'body_after': 'Le versioni precedenti di {app} non ricevono aggiornamenti di sicurezza dal 4 novembre 2026', 'risk': 'Il software senza correzioni di sicurezza può restare vulnerabile — aggiorna dalla pagina ufficiale', 'versions': 'Installata: {current} · Minima supportata: {minimum} · Disponibile: {latest}', 'update': 'Aggiorna', 'later': 'Più tardi', 'table': 'App e supporto'}, 'ru': {'before': 'Поддержка вашей версии скоро закончится', 'after': 'Ваша версия больше не получает обновления безопасности', 'body_before': 'Старые версии {app} перестанут получать обновления безопасности 4 ноября 2026 года', 'body_after': 'Старые версии {app} не получают обновления безопасности с 4 ноября 2026 года', 'risk': 'Программы без исправлений безопасности могут оставаться уязвимыми — обновитесь с официальной страницы проекта', 'versions': 'Установлена: {current} · Минимальная поддерживаемая: {minimum} · Доступна: {latest}', 'update': 'Обновить', 'later': 'Позже', 'table': 'Приложения и поддержка'}, 'zh': {'before': '你的版本即将停止支持', 'after': '你的版本已停止接收安全更新', 'body_before': '{app} 的旧版本将于 2026 年 11 月 4 日停止接收安全更新', 'body_after': '{app} 的旧版本自 2026 年 11 月 4 日起不再接收安全更新', 'risk': '缺少安全修复的软件可能仍存在漏洞，请通过项目官方页面更新', 'versions': '已安装：{current} · 最低支持版本：{minimum} · 可用版本：{latest}', 'update': '更新', 'later': '稍后', 'table': '应用与支持'}, 'ja': {'before': 'このバージョンのサポートはまもなく終了します', 'after': 'このバージョンのセキュリティ更新は終了しました', 'body_before': '{app} の旧バージョンは2026年11月4日にセキュリティ更新を終了します', 'body_after': '{app} の旧バージョンは2026年11月4日以降セキュリティ更新を受け取れません', 'risk': '修正のないソフトウェアには脆弱性が残る可能性があります — 公式ページから更新してください', 'versions': 'インストール済み：{current} · 最低サポート：{minimum} · 利用可能：{latest}', 'update': '更新', 'later': '後で', 'table': 'アプリとサポート'}, 'ko': {'before': '현재 버전의 지원이 곧 종료됩니다', 'after': '현재 버전은 더 이상 보안 업데이트를 받지 않습니다', 'body_before': '{app}의 이전 버전은 2026년 11월 4일부터 보안 업데이트를 받지 않습니다', 'body_after': '{app}의 이전 버전은 2026년 11월 4일 이후 보안 업데이트가 중단되었습니다', 'risk': '보안 수정이 없는 소프트웨어는 취약할 수 있습니다 — 공식 프로젝트 페이지에서 업데이트하세요', 'versions': '설치됨: {current} · 최소 지원: {minimum} · 사용 가능: {latest}', 'update': '업데이트', 'later': '나중에', 'table': '앱 및 지원'}, 'ar': {'before': 'سيتوقف دعم إصدارك قريبًا', 'after': 'لم يعد إصدارك يتلقى تحديثات الأمان', 'body_before': 'ستتوقف الإصدارات القديمة من {app} عن تلقي تحديثات الأمان في 4 نوفمبر 2026', 'body_after': 'لم تعد الإصدارات القديمة من {app} تتلقى تحديثات الأمان منذ 4 نوفمبر 2026', 'risk': 'قد تظل البرامج دون إصلاحات أمنية عرضة للثغرات — حدّث من صفحة المشروع الرسمية', 'versions': 'المثبت: {current} · الحد الأدنى المدعوم: {minimum} · المتاح: {latest}', 'update': 'تحديث', 'later': 'لاحقًا', 'table': 'التطبيقات والدعم'}, 'hi': {'before': 'आपके संस्करण का समर्थन जल्द समाप्त होगा', 'after': 'आपके संस्करण को अब सुरक्षा अपडेट नहीं मिलते', 'body_before': '{app} के पुराने संस्करणों को 4 नवंबर 2026 से सुरक्षा अपडेट नहीं मिलेंगे', 'body_after': '{app} के पुराने संस्करणों को 4 नवंबर 2026 से सुरक्षा अपडेट नहीं मिल रहे हैं', 'risk': 'सुरक्षा सुधारों के बिना सॉफ़्टवेयर असुरक्षित रह सकता है — आधिकारिक परियोजना पेज से अपडेट करें', 'versions': 'इंस्टॉल किया गया: {current} · न्यूनतम समर्थित: {minimum} · उपलब्ध: {latest}', 'update': 'अपडेट करें', 'later': 'बाद में', 'table': 'ऐप और समर्थन'}}\nPOLICY_URL = \"https://raw.githubusercontent.com/Chimpi-hackintosh/ChimpiBlender-Online/main/support-policy.json\"\nMAX_BYTES = 262144\n\n\ndef language(tag=None):\n    if tag is None:\n        tag = os.environ.get(\"LC_ALL\") or os.environ.get(\"LC_MESSAGES\") or os.environ.get(\"LANG\")\n        try:\n            if sys.platform == \"win32\":\n                import ctypes\n                buffer = ctypes.create_unicode_buffer(85)\n                if ctypes.windll.kernel32.GetUserDefaultLocaleName(buffer, len(buffer)):\n                    tag = buffer.value\n            elif sys.platform == \"darwin\":\n                tag = subprocess.check_output([\"defaults\", \"read\", \"-g\", \"AppleLanguages\"],\n                                              timeout=2, stderr=subprocess.DEVNULL).decode()\n                match = re.search(r\"[a-z]{2,3}(?:[-_][A-Za-z]{2,4})?\", tag)\n                tag = match.group() if match else None\n            if not tag:\n                tag = locale.getlocale()[0]\n        except (OSError, ValueError, subprocess.SubprocessError, AttributeError):\n            pass\n    code = str(tag or \"en\").replace(\"_\", \"-\").split(\"-\")[0].split(\".\")[0].lower()\n    return code if code in MESSAGES else \"en\"\n\n\ndef texts(tag=None):\n    return dict(MESSAGES[\"en\"], **MESSAGES[language(tag)])\n\n\ndef version(value):\n    \"\"\"Compare the app's release series, not CI build suffixes or preview labels.\"\"\"\n    if not isinstance(value, str) or len(value) > 100:\n        return None\n    match = re.fullmatch(r\"v?(\\d+)\\.(\\d+)\\.(\\d+)(?:[-+][A-Za-z0-9.-]+)?\", value)\n    return tuple(map(int, match.group(1, 2, 3))) if match else None\n\n\ndef official_url(url, repo=None, table=False):\n    if not isinstance(url, str):\n        return False\n    try:\n        parsed = urllib.parse.urlparse(url)\n        port = parsed.port\n    except ValueError:\n        return False\n    if parsed.scheme != \"https\" or parsed.username or parsed.password or port not in (None, 443):\n        return False\n    if table:\n        return parsed.netloc == \"chimpi-hackintosh.github.io\" and parsed.path == \"/ChimpiBlender-Online/support.html\" and not parsed.query and not parsed.fragment\n    parts = parsed.path.strip(\"/\").split(\"/\")\n    return (parsed.netloc == \"github.com\" and len(parts) >= 2 and\n            parts[0] == \"Chimpi-hackintosh\" and (repo is None or parts[1] == repo) and\n            not parsed.query and not parsed.fragment and all(part not in (\".\", \"..\") for part in parts))\n\n\ndef read_json(url):\n    request = urllib.request.Request(url, headers={\"User-Agent\": \"Chimpi-support-check/1\", \"Accept\": \"application/json\"})\n    with urllib.request.urlopen(request, timeout=4) as response:\n        # Never follow a GitHub redirect to a different host for policy data.\n        if urllib.parse.urlparse(response.geturl()).hostname != urllib.parse.urlparse(url).hostname:\n            raise ValueError(\"Unexpected redirect\")\n        raw = response.read(MAX_BYTES + 1)\n    if len(raw) > MAX_BYTES:\n        raise ValueError(\"Oversized response\")\n    return json.loads(raw)\n\n\ndef checked_policy(candidate, bundled=POLICY):\n    \"\"\"Accept valid entries only for known apps; preserve usable offline entries.\"\"\"\n    result = copy.deepcopy(bundled)\n    if not isinstance(candidate, dict) or candidate.get(\"schema\") != 1 or not isinstance(candidate.get(\"apps\"), dict):\n        return result\n    # The owner's declared cutoff is immutable in this release of the checker.\n    for key, original in bundled[\"apps\"].items():\n        entry = candidate[\"apps\"].get(key)\n        if not isinstance(entry, dict) or entry.get(\"repo\") != original[\"repo\"]:\n            continue\n        new, old = version(entry.get(\"minimum\")), version(original.get(\"minimum\"))\n        if new is None or (old is not None and new < old):\n            continue\n        if not official_url(entry.get(\"url\"), original[\"repo\"]):\n            continue\n        result[\"apps\"][key].update(minimum=entry[\"minimum\"], tag=str(entry.get(\"tag\") or entry[\"minimum\"])[:100], url=entry[\"url\"])\n    return result\n\n\ndef release_version(tag, edition=None):\n    if not isinstance(tag, str):\n        return None\n    if edition:\n        match = re.fullmatch(r\"v(\\d+)\\.(\\d+)-\" + re.escape(edition) + r\"\\.(\\d+)\", tag)\n        return \".\".join(match.groups()) if match else None\n    match = re.search(r\"\\d+\\.\\d+\\.\\d+(?:[-+][A-Za-z0-9.-]+)?$\", tag)\n    return match.group() if match else None\n\n\ndef with_releases(policy, app, releases):\n    result = copy.deepcopy(policy)\n    entry = result[\"apps\"].get(app)\n    if entry is None or not isinstance(releases, list):\n        return result\n    for release in releases[:30]:\n        if not isinstance(release, dict) or release.get(\"draft\") or not release.get(\"assets\"):\n            continue\n        if release.get(\"prerelease\") and not entry.get(\"preview\"):\n            continue\n        value = release_version(release.get(\"tag_name\"), entry.get(\"edition\"))\n        parsed = version(value)\n        if parsed is None or (version(entry.get(\"minimum\")) is not None and parsed <= version(entry[\"minimum\"])):\n            continue\n        if official_url(release.get(\"html_url\"), entry[\"repo\"]):\n            entry.update(minimum=\".\".join(map(str, parsed)), tag=release[\"tag_name\"][:100], url=release[\"html_url\"])\n    return result\n\n\ndef notice(app, current, policy=POLICY, now=None, lang=None):\n    entry = policy.get(\"apps\", {}).get(app)\n    installed = version(current)\n    if not entry or installed is None:\n        return None\n    minimum = version(entry.get(\"minimum\"))\n    if minimum is None or installed >= minimum or not official_url(entry.get(\"url\"), entry[\"repo\"]):\n        return None\n    now = now or dt.datetime.now(dt.timezone.utc)\n    if now.tzinfo is None:\n        now = now.replace(tzinfo=dt.timezone.utc)\n    ends = dt.datetime.fromisoformat(POLICY[\"ends_at\"].replace(\"Z\", \"+00:00\"))\n    phase = \"after\" if now >= ends else \"before\"\n    tr = texts(lang)\n    variables = dict(app=entry[\"name\"], current=current, minimum=entry[\"minimum\"], latest=entry.get(\"tag\") or entry[\"minimum\"])\n    return dict(title=tr[phase], body=\"\\n\\n\".join([tr[\"body_\" + phase].format(**variables), tr[\"risk\"], tr[\"versions\"].format(**variables)]),\n                url=entry[\"url\"], phase=phase, texts=tr, table=POLICY[\"table\"])\n\n\ndef check(app, current):\n    # Unknown/private apps without a public release are never sent to the public API.\n    if app not in POLICY[\"apps\"]:\n        return None\n    policy = copy.deepcopy(POLICY)\n    try:\n        policy = checked_policy(read_json(POLICY_URL))\n    except (OSError, ValueError, TypeError):\n        pass\n    try:\n        repo = POLICY[\"apps\"][app][\"repo\"]\n        policy = with_releases(policy, app, read_json(f\"https://api.github.com/repos/Chimpi-hackintosh/{repo}/releases?per_page=30\"))\n    except (OSError, ValueError, TypeError):\n        pass\n    return notice(app, current, policy)\n\n\ndef enabled():\n    return (os.environ.get(\"CHIMPI_SUPPORT_CHECK\", \"1\") != \"0\" and\n            not any(arg.startswith((\"--gui-smoke\", \"--smoke-test\", \"--self-test\")) for arg in sys.argv[1:]))\n\n\ndef worker(app, current):\n    results = queue.Queue()\n    def run():\n        try:\n            results.put(check(app, current))\n        except Exception:\n            results.put(None)  # A failed optional check must never prevent startup.\n    threading.Thread(target=run, name=\"Chimpi-support\", daemon=True).start()\n    return results\n\n\ndef attach_tk(root, app, current):\n    if not enabled():\n        return\n    results = worker(app, current)\n    def poll():\n        if not root.winfo_exists():\n            return\n        try:\n            item = results.get_nowait()\n        except queue.Empty:\n            root.after(250, poll)\n            return\n        if item is None:\n            return\n        import tkinter as tk\n        from tkinter import ttk\n        window = tk.Toplevel(root)\n        window.title(item[\"title\"])\n        window.transient(root)\n        window.resizable(False, False)\n        window.columnconfigure(0, weight=1)\n        ttk.Label(window, text=item[\"title\"], font=(\"TkDefaultFont\", 13, \"bold\"), wraplength=500).grid(row=0, column=0, padx=22, pady=(20, 12), sticky=\"w\")\n        ttk.Label(window, text=item[\"body\"], wraplength=500, justify=\"left\").grid(row=1, column=0, padx=22, pady=8, sticky=\"w\")\n        buttons = ttk.Frame(window)\n        buttons.grid(row=2, column=0, padx=22, pady=20, sticky=\"e\")\n        ttk.Button(buttons, text=item[\"texts\"][\"table\"], command=lambda: webbrowser.open(item[\"table\"])).pack(side=\"left\", padx=4)\n        ttk.Button(buttons, text=item[\"texts\"][\"later\"], command=window.destroy).pack(side=\"left\", padx=4)\n        ttk.Button(buttons, text=item[\"texts\"][\"update\"], command=lambda: webbrowser.open(item[\"url\"])).pack(side=\"left\", padx=4)\n    root.after(800, poll)\n\n\ndef attach_qt(parent, app, current):\n    if not enabled():\n        return\n    from PySide6.QtCore import QTimer, Qt\n    from PySide6.QtWidgets import QMessageBox\n    results = worker(app, current)\n    timer = QTimer(parent)\n    def poll():\n        try:\n            item = results.get_nowait()\n        except queue.Empty:\n            return\n        timer.stop()\n        if item:\n            box = QMessageBox(parent)\n            box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)\n            box.setWindowTitle(item[\"title\"])\n            box.setTextFormat(Qt.TextFormat.PlainText)\n            box.setText(item[\"title\"])\n            box.setInformativeText(item[\"body\"])\n            update = box.addButton(item[\"texts\"][\"update\"], QMessageBox.ButtonRole.AcceptRole)\n            table = box.addButton(item[\"texts\"][\"table\"], QMessageBox.ButtonRole.ActionRole)\n            box.addButton(item[\"texts\"][\"later\"], QMessageBox.ButtonRole.RejectRole)\n            box.buttonClicked.connect(lambda button: webbrowser.open(item[\"url\"] if button == update else item[\"table\"]) if button in (update, table) else None)\n            # Keep the modeless dialog alive until it closes.\n            parent._support_notice = box\n            box.show()\n    timer.timeout.connect(poll)\n    timer.start(250)\n    parent._support_timer = timer\n\n\ndef attach_gtk(parent, app, current, finished=None):\n    if not enabled():\n        if finished:\n            finished()\n        return\n    from gi.repository import GLib, Gtk\n    results = worker(app, current)\n    def poll():\n        try:\n            item = results.get_nowait()\n        except queue.Empty:\n            return True\n        if item:\n            dialog = Gtk.MessageDialog(transient_for=parent, modal=False, message_type=Gtk.MessageType.WARNING, text=item[\"title\"])\n            dialog.format_secondary_text(item[\"body\"])\n            dialog.add_button(item[\"texts\"][\"table\"], 1)\n            dialog.add_button(item[\"texts\"][\"update\"], 2)\n            dialog.add_button(item[\"texts\"][\"later\"], Gtk.ResponseType.CLOSE)\n            def response(window, value):\n                if value in (1, 2):\n                    webbrowser.open(item[\"table\"] if value == 1 else item[\"url\"])\n                window.destroy()\n                if finished:\n                    finished()\n            dialog.connect(\"response\", response)\n            dialog.show_all()\n        elif finished:\n            finished()\n        return False\n    GLib.timeout_add(250, poll)\n\n\nif __name__ == \"__main__\":\n    import argparse\n    parser = argparse.ArgumentParser(description=__doc__)\n    parser.add_argument(\"--app\", required=True, choices=sorted(POLICY[\"apps\"]))\n    parser.add_argument(\"--version\", required=True)\n    args = parser.parse_args()\n    if not enabled():\n        sys.exit(0)\n    import gi\n    gi.require_version(\"Gtk\", \"3.0\")\n    from gi.repository import Gtk\n    attach_gtk(None, args.app, args.version, finished=Gtk.main_quit)\n    Gtk.main()\n"

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
# Limites locais do aplicativo (não substituem proteções de servidor)
LIMITES = {"login": (5, 900), "mensagem": (20, 60)}
TRAVA_LIMITES = threading.Lock()
 
# ---- Logins (pode preencher aqui ou no instalador / config.json) ----
GOOGLE_CLIENT_ID = "990145632071-kivq2ea0q1hvekic8g1diu3vdbgevrk9.apps.googleusercontent.com"
GITHUB_CLIENT_ID = "Ov23liJFjuBkxw9CVnOr"
REDIRECT = f"http://localhost:{PORTA}/"
 
PASTA = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ChimpiAI")
ARQUIVO_CONFIG = os.path.join(PASTA, "config.json")
ARQUIVO_LIMITES = os.path.join(PASTA, "limites.json")
 
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
    dados = dict(cfg)
    dados["usuario"] = None  # Não persistir nome nem e-mail
    os.makedirs(PASTA, exist_ok=True)
    with open(ARQUIVO_CONFIG, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)
 
 
def pegar(cfg, caminho):
    for c in caminho:
        cfg = cfg[c]
    return cfg
 
 
def definir(cfg, caminho, valor):
    for c in caminho[:-1]:
        cfg = cfg[c]
    cfg[caminho[-1]] = valor
 
 
# ---------------------------------------------------------------- limite local
def limitar_acao(acao):
    """0 quando permitido; caso contrário, segundos de espera."""
    maximo, janela = LIMITES[acao]
    agora = time.time()
    with TRAVA_LIMITES:
        try:
            with open(ARQUIVO_LIMITES, "r", encoding="utf-8") as f:
                dados = json.load(f)
        except FileNotFoundError:
            dados = {}
        if not isinstance(dados, dict):
            raise ValueError("Arquivo de limites inválido")
        anteriores = dados.get(acao, [])
        if not isinstance(anteriores, list):
            raise ValueError("Histórico de limites inválido")
        recentes = sorted(t for t in anteriores if type(t) in (int, float)
                          and agora - janela < t <= agora)
        if len(recentes) >= maximo:
            return max(1, int(recentes[0] + janela - agora) + 1)
        dados[acao] = recentes + [agora]
        os.makedirs(PASTA, exist_ok=True)
        temporario = ARQUIVO_LIMITES + "." + secrets.token_hex(8) + ".tmp"
        try:
            with open(temporario, "x", encoding="utf-8") as f:
                json.dump(dados, f)
            os.replace(temporario, ARQUIVO_LIMITES)
        finally:
            try:
                os.remove(temporario)
            except FileNotFoundError:
                pass
        return 0


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
        if self.cfg.get("usuario") is not None:
            self.cfg["usuario"] = None
            salvar_config(self.cfg)  # Limpa logins antigos persistidos
        ctk.set_appearance_mode(self.cfg.get("tema", "dark"))
        ctk.set_default_color_theme("blue")
        self.title(NOME)
        self.geometry("920x640")
        self.minsize(720, 520)
        self.fila = queue.Queue()
        self.historico = []
        self.ocupado = False
        self.login_em_andamento = False
        self.chat_id = None
        self.after(50, self.processar_fila)
 
        if not self.cfg["instalado"]:
            self.tela_sem_instalacao()
        else:
            self.tela_login()  # Exige autenticação a cada abertura
        try:
            from support_notice import attach_tk
            attach_tk(self, "ChimpiAI", "1.1.0")
        except (ImportError, OSError):
            pass  # O aviso opcional nunca impede a inicialização
 
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
        ctk.CTkLabel(q, text="Esqueceu a senha? A recuperação é feita no provedor.",
                     font=("Segoe UI", 13)).pack(pady=(18, 5))
        for nome, url in (("Google", "https://accounts.google.com/signin/recovery"),
                          ("GitHub", "https://github.com/password_reset")):
            ctk.CTkButton(q, text=f"Recuperar no {nome}", width=270, fg_color="gray40",
                          command=lambda u=url: webbrowser.open(u)).pack(pady=3)
        self.status = ctk.CTkLabel(q, text="", wraplength=460, font=("Segoe UI", 14))
        self.status.pack(pady=12)
 
    def iniciar_login(self, nome, funcao):
        if self.login_em_andamento:
            return
        try:
            espera = limitar_acao("login")
        except (OSError, ValueError):
            self.status.configure(text="Falha ao verificar o limite de login.", text_color="#ff6b6b")
            return
        if espera:
            self.status.configure(text=f"Muitas tentativas. Tente novamente em {espera} segundos.",
                                  text_color="#ffb347")
            return
        self.cfg = carregar_config()
        self.cfg["usuario"] = None
        self.login_em_andamento = True
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
        self.login_em_andamento = False
        self.cfg["usuario"] = usuario
        self.chat_id = secrets.token_urlsafe(16)
        self.tela_chat()

    def login_erro(self, mensagem):
        self.login_em_andamento = False
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
        # Respostas antigas deixam de pertencer a esta conversa.
        self.chat_id = secrets.token_urlsafe(16)
        self.historico = []
        self.ocupado = False
        self.botao_enviar.configure(state="normal")
        self.caixa.configure(state="normal")
        self.caixa.delete("1.0", "end")
        self.caixa.configure(state="disabled")
        self.escrever("ChimpiAI: Memória apagada.\n\n")

    def sair(self):
        self.chat_id = None
        self.historico = []
        self.ocupado = False
        self.cfg["usuario"] = None
        salvar_config(self.cfg)
        self.tela_login()

    def enviar(self, _=None):
        texto = self.entrada.get().strip()
        if not texto or self.ocupado or self.chat_id is None:
            return
        try:
            espera = limitar_acao("mensagem")
        except (OSError, ValueError):
            self.escrever("ChimpiAI: Falha ao verificar o limite de mensagens.\n\n")
            return
        if espera:
            self.escrever(f"ChimpiAI: Limite de mensagens. Tente de novo em {espera} segundos.\n\n")
            return
        self.entrada.delete(0, "end")
        self.escrever(f"Você: {texto}\n\nChimpiAI: ")
        self.historico.append({"role": "user", "content": texto})
        self.historico = self.historico[-MAX_MENSAGENS:]
        while self.historico and self.historico[0]["role"] != "user":
            self.historico.pop(0)
        self.ocupado = True
        self.botao_enviar.configure(state="disabled")
        chat_id = self.chat_id
        modelo = self.cfg.get("modelo") or MODELO
        nome_usuario = self.cfg["usuario"]["nome"]
        mensagens = list(self.historico)
        threading.Thread(target=self.responder, args=(chat_id, modelo, nome_usuario, mensagens),
                         daemon=True).start()

    def escrever_se_chat(self, chat_id, texto):
        if chat_id == self.chat_id:
            self.escrever(texto)

    def resposta_se_chat(self, chat_id, resposta):
        if chat_id == self.chat_id:
            self.historico.append({"role": "assistant", "content": resposta})

    def erro_se_chat(self, chat_id, mensagem):
        if chat_id != self.chat_id:
            return
        if self.historico and self.historico[-1]["role"] == "user":
            self.historico.pop()
        self.escrever(f"[erro: {mensagem}]\n\n")

    def responder(self, chat_id, modelo, nome_usuario, mensagens):
        try:
            sistema = (
                f"Você é a {NOME}, uma inteligência artificial assistente criada pelo Chimpi. "
                "Responda sempre em português do Brasil, de forma direta, clara e amigável, "
                "a menos que a pessoa escreva em outro idioma. "
                "Ajude com qualquer assunto: perguntas, estudos, programação, textos, ideias, contas e o que mais vier. "
                "Se não souber algo, diga que não sabe em vez de inventar. "
                f"A pessoa se chama {nome_usuario}."
            )
            resposta = ""
            for pedaco in ollama_stream(modelo, sistema, mensagens):
                if chat_id != self.chat_id:
                    return
                resposta += pedaco
                self.chamar(self.escrever_se_chat, chat_id, pedaco)
            if not resposta:
                raise Exception("O modelo não devolveu resposta. Tente de novo.")
            self.chamar(self.resposta_se_chat, chat_id, resposta)
            self.chamar(self.escrever_se_chat, chat_id, "\n\n")
        except Exception as erro:
            self.chamar(self.erro_se_chat, chat_id, str(erro))
        finally:
            self.chamar(self.liberar, chat_id)

    def liberar(self, chat_id):
        if chat_id != self.chat_id:
            return
        self.ocupado = False
        self.botao_enviar.configure(state="normal")
        self.entrada.focus()


if __name__ == "__main__":
    App().mainloop()
'''
 
 
if __name__ == "__main__":
    Instalador().mainloop()
 