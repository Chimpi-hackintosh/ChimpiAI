# Publicar o ChimpiAI no WinGet

Este diretório permite compilar a **versão Windows standalone**, criar um instalador Inno Setup e gerar os 3 manifests exigidos pelo repositório oficial WinGet.

## O que a instalação muda

- O usuário não precisa baixar o repositório nem instalar Python
- O executável Windows inclui o Python e as bibliotecas necessárias
- O ChimpiAI continua usando o Ollama local, que deve estar disponível no computador
- A configuração fica em `%APPDATA%\ChimpiAI\config.json` e é preservada em atualizações
- O manifesto declara `Ollama.Ollama` como dependência
- O modelo inicial `gemma3:1b` precisa ser baixado usando `ollama pull gemma3:1b` (ou automaticamente numa atualização futura do app)

## Como criar a release

Na aba Actions do repositório, execute **Windows installer and WinGet manifests** usando `Run workflow`.

- `version`: `1.1.0` (ou versão posterior)
- `publish_release`: `true` para publicar no GitHub Releases

Serão gerados:
1. `ChimpiAI-Setup-<versão>.exe`, instalador de usuário, sem necessidade de privilégios de administrador
2. `ChimpiAI-Setup-<versão>.exe.sha256`, hash do arquivo real
3. `ChimpiAI-winget-manifests-<versão>.zip`, arquivos do catálogo de pacotes da Microsoft

O workflow de push também testa a compilação, mas só uma execução manual com `publish_release=true` publica a release.

## Registrar no WinGet (passo externo obrigatório)

O repositório ChimpiAI não pode, por si só, disponibilizar um identificador novo no catálogo padrão do WinGet.

1. Confira se a release contém o `.exe` com a mesma versão e nome indicados no manifesto
2. Extraia o ZIP de manifests
3. Verifique os três arquivos em `manifests/c/Chimpi-hackintosh/ChimpiAI/<versão>/`
4. Valide com `winget validate --manifest <pasta-com-os-3-arquivos>`
5. Abra uma solicitação de inclusão (pull request) com esses arquivos em [microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs)
6. Aguarde os testes, a análise e a aceitação pela equipe do repositório oficial

**Somente depois da publicação no catálogo** estará disponível:

```cmd
winget install --id Chimpi-hackintosh.ChimpiAI -e
```

Ao atualizar uma versão aprovada no catálogo, será possível usar `winget upgrade --id Chimpi-hackintosh.ChimpiAI -e`.

O instalador `ChimpiAI-Setup-<versão>.exe` na release pode ser utilizado antes de o pacote estar disponível no WinGet.

## Observações

- O Windows pode alertar sobre instaladores ainda não assinados digitalmente
- O manifesto usa um hash SHA-256 computado do `.exe`, sem valores de exemplo
- Nunca publique tokens GitHub nem segredos OAuth dentro dos manifests
- Confira compatibilidade do Ollama e espaço para baixar o modelo antes de distribuir
- O instalador legado `ChimpiAI-installer.py` segue disponível como alternativa, mas não é o pacote utilizado pelo WinGet

Referência: [guia de publicação de pacotes WinGet](https://github.com/microsoft/winget-pkgs/blob/master/doc/Authoring.md)
