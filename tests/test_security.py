"""Validação sem instalar Ollama: python -m unittest discover -s tests -v"""
import ast
import pathlib
import unittest

def codigo():
    arq = pathlib.Path(__file__).resolve().parents[1] / "ChimpiAI-installer.py"
    raiz = ast.parse(arq.read_text(encoding="utf-8"))
    for n in raiz.body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "CODIGO_CHIMPIAI" for t in n.targets):
            return n.value.value
    raise AssertionError("Aplicativo não encontrado")

class TestSeguranca(unittest.TestCase):
    def test_sintaxe(self):
        compile(codigo(), "chimpiai.py", "exec")
    def test_marcadores(self):
        src = codigo()
        for item in ("def limitar_acao(acao)", "limitar_acao(\"login\")", "limitar_acao(\"mensagem\")", "def escrever_se_chat", 'dados["usuario"] = None'):
            self.assertIn(item, src)
    def test_tem_integracao_com_provedor(self):
        src = codigo()
        self.assertIn("https://accounts.google.com/signin/recovery", src)
        self.assertIn("https://github.com/password_reset", src)

if __name__ == "__main__":
    unittest.main()
