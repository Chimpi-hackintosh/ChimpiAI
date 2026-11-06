"""Extrai o app embutido no instalador legado sem duplicar código-fonte."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "ChimpiAI-installer.py"
OUT = ROOT / "build" / "chimpiai_app.py"


def main():
    tree = ast.parse(LEGACY.read_text(encoding="utf-8"), filename=str(LEGACY))
    code = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "CODIGO_CHIMPIAI" for t in node.targets
        ):
            code = ast.literal_eval(node.value)
            break
    if not isinstance(code, str) or "class App(" not in code:
        raise RuntimeError("Não foi possível localizar o código do app no instalador legado")
    compile(code, str(OUT), "exec")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(code, encoding="utf-8")
    print(f"App extraído para {OUT}")


if __name__ == "__main__":
    main()
