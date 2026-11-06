"""Entrada do ChimpiAI empacotado, sem necessidade de Python instalado."""
import json
import os
from pathlib import Path


def inicializar_config():
    appdata = os.environ.get("APPDATA") or str(Path.home())
    config = Path(appdata) / "ChimpiAI" / "config.json"
    # Atualizações não sobrescrevem preferências nem logins existentes.
    if config.exists():
        return
    config.parent.mkdir(parents=True, exist_ok=True)
    dados = {
        "instalado": True,
        "tema": "dark",
        "modelo": "gemma3:1b",
        "usuario": None,
        "oauth": {
            "google": {"client_id": "", "client_secret": ""},
            "github": {"client_id": ""}
        }
    }
    config.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    inicializar_config()
    from chimpiai_app import App
    App().mainloop()


if __name__ == "__main__":
    main()
