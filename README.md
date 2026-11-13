# ChimpiAI

Assistente de IA para Windows que roda **no seu próprio computador**, com janela feita em Python (CustomTkinter), login com Google ou GitHub e chat com respostas em tempo real. A inteligência vem do [Ollama](https://ollama.com), então não precisa de chave de API paga nem de internet para conversar.

## Instalação no Windows sem clonar o repositório (nova versão 1.1.0)

**Status:** compilação e manifests preparados, mas o pacote ainda **não foi aprovado** no catálogo WinGet. O comando abaixo só funcionará depois da aprovação pela Microsoft:

```bat
winget install --id Chimpi-hackintosh.ChimpiAI -e
```

A versão empacotada também dispensa a instalação manual do Python. Depois que o instalador `.exe` for publicado, será possível baixá-lo em [Releases](https://github.com/Chimpi-hackintosh/ChimpiAI/releases). A versão usa o Ollama para executar os modelos localmente e o modelo precisa ser baixado na primeira configuração:

```bat
ollama pull gemma3:1b
```

Quando o manifesto for aprovado, o WinGet também solicitará a instalação do pacote `Ollama.Ollama` como dependência. O download do modelo é separado do instalador do ChimpiAI.

### Gerar o instalador e publicar a release

1. Acesse **Actions → Windows installer and WinGet manifests → Run workflow** neste repositório
2. Confirme a versão `1.1.0` e a opção **Publicar instalador no GitHub Releases?**
3. O workflow cria `ChimpiAI-Setup-1.1.0.exe`, arquivo de hash SHA-256 e os manifests WinGet dentro do pacote ZIP
4. Após o release estar disponível, submeta os manifests gerados como PR ao [microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs) e espere a validação e aprovação

Veja [o guia de publicação](packaging/README.md) para os detalhes

## Recursos

- Instalador gráfico em um único arquivo (`ChimpiAI-installer.py`) que cria o app, instala o Ollama e baixa o modelo
- Login com **Google** (OAuth com PKCE) e **GitHub** (Device Flow)
- Chat com resposta aparecendo aos poucos, memória da conversa e botão para limpar
- Tema escuro, claro ou do sistema
- Atalho na área de trabalho
- Configurações guardadas fora do código, em `%APPDATA%\ChimpiAI\config.json`

## Requisitos

- Windows 10 ou 11
- Python 3 disponível no CMD (`python --version`) **apenas para o instalador legado**; a versão `.exe` não exige Python no PC
- Internet na instalação (para baixar o Ollama e o modelo)
- Memória: o modelo padrão (`gemma3:4b`) pede cerca de 3 GB livres. Em PCs com pouca memória use `gemma3:1b`

## Instalação legada (instalador Python)

1. Baixe o `ChimpiAI-installer.py` (ou clone o repositório):
   ```
   git clone https://github.com/Chimpi-hackintosh/ChimpiAI.git
   cd ChimpiAI
   ```
2. Rode o instalador:
   ```
   python ChimpiAI-installer.py
   ```
3. Siga as telas: pasta de instalação, modelo, logins e tema.
4. Espere terminar. O instalador:
   - instala o `customtkinter`
   - cria o `chimpiai.py` na pasta escolhida
   - instala o Ollama, se ainda não estiver instalado
   - liga o Ollama e baixa o modelo com barra de progresso
   - cria o atalho na área de trabalho
5. Abra a ChimpiAI pelo atalho.

Pasta de instalação padrão: `%LOCALAPPDATA%\Programs\ChimpiAI`

> Se algum passo do Ollama falhar, o instalador termina mesmo assim e mostra na última tela o comando para resolver na mão (por exemplo `ollama pull gemma3:4b`).

## Configurando os logins

Os logins precisam de um app cadastrado em cada serviço. É grátis. Cada pessoa que for usar o projeto deve criar os seus.

### Google

1. Em [console.cloud.google.com](https://console.cloud.google.com), crie uma credencial **ID do cliente OAuth** do tipo **App para computador**.
2. Copie o **Client ID** e o **Client Secret**.
3. Em **Tela de permissão OAuth**, enquanto o app estiver em modo teste, adicione seu e-mail em **Usuários de teste**.
4. Cole o Client ID e o Client Secret no instalador (ou no `config.json`).

O navegador volta para `http://localhost:8765/`, e o próprio app recebe a resposta. Se o seu cliente for do tipo "Aplicativo da Web", cadastre esse endereço em **URIs de redirecionamento autorizados**.

### GitHub

1. Em **Settings > Developer settings > OAuth Apps**, crie um app.
2. Nos campos de site e de callback, pode usar `http://localhost:8765/`.
3. Marque **Enable Device Flow**.
4. Copie o **Client ID**. Não precisa de secret.

Na hora do login, a janela mostra um código que você digita na página do GitHub que abre no navegador.

## Modelos

O modelo fica na chave `"modelo"` do `config.json`. Para trocar:

```
ollama pull llama3.2:3b
```

e depois mude o valor de `"modelo"` para `llama3.2:3b`. Veja os modelos disponíveis em [ollama.com/library](https://ollama.com/library).

| Modelo | Quando usar |
|---|---|
| `gemma3:4b` | Padrão, melhor qualidade em português entre os citados, mais lento |
| `llama3.2:3b` | Mais leve e rápido, qualidade um pouco menor |
| `gemma3:1b` | PCs com pouca memória, mais rápido e com mais erros |

Modelos pequenos erram e são menos capazes que serviços na nuvem. A ChimpiAI não "sabe tudo".

## Arquivo de configuração

`%APPDATA%\ChimpiAI\config.json`:

```json
{
  "instalado": true,
  "tema": "dark",
  "modelo": "gemma3:4b",
  "usuario": null,
  "oauth": {
    "google": { "client_id": "", "client_secret": "" },
    "github": { "client_id": "" }
  }
}
```

Na tela de login, o botão **Editar configurações dos logins** abre esse arquivo no Bloco de Notas.

## Problemas comuns

| Mensagem ou sintoma | O que fazer |
|---|---|
| "Não consegui falar com o Ollama" | Abra o Ollama pelo Menu Iniciar (ele fica como ícone perto do relógio) |
| "O modelo ... não está baixado" | Rode `ollama pull` com o nome do modelo |
| Google: `access_denied` | Adicione seu e-mail em **Usuários de teste** na tela de permissão OAuth |
| Google: `redirect_uri_mismatch` | Cadastre `http://localhost:8765/` nos URIs de redirecionamento |
| "Google não configurado" | Falta o Client Secret. Preencha no instalador ou no `config.json` |
| GitHub dá erro ao entrar | Confirme que **Enable Device Flow** está marcado no app do GitHub |
| "A porta 8765 está ocupada" | Feche o outro programa que usa a porta e tente de novo |
| Muito lento ou travando | Feche outros programas ou troque para um modelo menor |

## Segurança

- O ChimpiAI usa login com **Google ou GitHub**, não mantém senhas próprias e não oferece cadastro por e-mail, envio de SMS nem recuperação própria.
- A tela de login possui botões de recuperação **diretamente no Google ou GitHub**. A expiração de links de redefinição é determinada pelo respectivo provedor.
- **Login**: no máximo **5 tentativas por 15 minutos** (Google e GitHub combinados), neste perfil do Windows.
- **Chat**: no máximo **20 mensagens por minuto**, com bloqueio adicional de envios simultâneos enquanto a IA responde.
- As tentativas ficam registradas em `%APPDATA%\ChimpiAI\limites.json` após reiniciar o aplicativo. Erros na leitura ou gravação dos limites bloqueiam a ação.
- A identidade da conta **não é mais salva** no `config.json`; é preciso entrar novamente a cada abertura. Dados de sessão antigos são removidos na primeira abertura após a atualização.
- Ao sair ou limpar o chat, respostas antigas que chegarem depois serão ignoradas, para não aparecerem em outra conta ou conversa.
- **Importante**: os limites são **locais ao perfil Windows**, não à conta global nem a um servidor. Eles não impedem ações feitas em outro dispositivo ou diretamente pelos serviços externos. Caso existam futuramente cadastro próprio, formulários, envio de e-mails/SMS, pedidos, bancos de dados ou planos pagos, será necessário implementar limites e verificações de autorização em um backend seguro. Essas funções não estão presentes nesta versão.
- O login não protege os arquivos de outras pessoas que usam o mesmo perfil do Windows.
- O instalador roda o script oficial `https://ollama.com/install.ps1` do site do Ollama. Leia antes de executar se preferir.

## Estrutura

```
ChimpiAI/
├── ChimpiAI-installer.py   # instalador legado; inclui o código do app
├── packaging/             # compilação standalone, instalador Inno Setup e manifests WinGet
├── .github/workflows/windows-winget.yml
└── README.md
```

Depois de instalado, o app fica em `chimpiai.py` na pasta de instalação.

## Licença
Licença MIT (Sem DMCA Takedown)

## Aviso de suporte

O verificador localizado compara a versão instalada com Releases públicas e usa português, inglês ou inglês como alternativa, conforme [SUPPORT.md](SUPPORT.md)
