# Aviso de suporte e atualizações

## Política

A partir de **04/11/2026 às 00h UTC**, versões abaixo da mínima publicada deixam de receber correções de segurança do proprietário

Antes dessa data o aviso informa que o suporte está prestes a terminar — depois informa que as atualizações de segurança terminaram

| Aplicativo | Release pública conferida em 07/11/2026 | Mínima |
| --- | --- | --- |
| ChimpiAI | v1.1.0 — estável | 1.1.0 |

O instalador Windows e o SHA-256 da Release `v1.1.0` foram conferidos no GitHub — o pacote só estará disponível no catálogo WinGet depois de aprovação externa

## Comportamento

- Detecta o idioma do sistema — português, inglês e traduções existentes, com inglês como alternativa
- Compara a versão instalada com a mínima sustentada por Release real
- Consulta somente dados públicos por HTTPS e usa o catálogo embutido quando está sem internet
- Não envia prompts, senhas ou arquivos e não baixa nem instala atualizações
- Abre apenas páginas oficiais e preserva a decisão de atualizar com o usuário
- `CHIMPI_SUPPORT_CHECK=0` desliga a consulta opcional, e modos de teste não iniciam rede

## Distribuição e limites

Versões já instaladas sem verificador precisam de uma atualização manual inicial

Este PR entrega código e verificações — não equivale a uma nova Release, instalação concluída ou site publicado

O aviso não afirma infecção e uma falha opcional do verificador nunca impede a abertura do aplicativo


## Atualização do catálogo em 15/11/2026

A prévia pública `v1.1.0-preview.18` do ChimpiCode foi publicada em 15/11/2026 às 14:05:41 UTC e permanece classificada como prévia. O instalador Windows Setup tem o digest SHA-256 `sha256:e518703784c7f38143332c5a12e6ed96f6a0bf84ca0831ba40ca9f556bee020f`. A versão estável continua sendo `v1.0.0`.


## Atualização do catálogo em 15/11/2026

A prévia pública `v1.1.0-preview.21` do ChimpiCode foi publicada em 15/11/2026 às 14:22:46 UTC e permanece classificada como prévia. O instalador Windows Setup tem o digest SHA-256 `sha256:66784558333392705e5a8c4a3fb349ede6f46725083b3134e72ab037aad04bfa`. A versão estável continua sendo `v1.0.0`.
