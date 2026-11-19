# Contador de Tokens · Claude

Widget de bandeja para Windows que mostra, em tempo real, quanto do seu plano Claude você já usou — sem precisar abrir o app ou o site.

**Versão atual: v5.2** · [Baixar o instalador em Releases](../../releases)

## O que ele mostra

- **Sessão de 5 h** e **semana de 7 dias**, com o horário de reset
- **Projeção de esgotamento** ("esgota em ~X")
- **Créditos de uso**: quando a sessão zera, exibe o valor em R$ em vez de uma porcentagem negativa
- **Consumo diário** em gráfico
- **Alerta configurável** (bip + aviso no widget) quando restar X %
- Tema claro/escuro, instância única, posição lembrada e altura automática (sem barra de rolagem)

## Instalação

1. Baixe o instalador na página de [Releases](../../releases).
2. Dê duplo-clique. Ele instala o app, cria o atalho no Menu Iniciar, ativa o início com o Windows e instala o WebView2 se estiver faltando.
3. Se o SmartScreen avisar (o instalador não é assinado): **Mais informações → Executar assim mesmo**.

> O `.exe` não fica no repositório; ele é distribuído apenas pelos Releases.

## Como entrar na conta

- **Com o Claude Desktop instalado e logado**, o app usa o token dele automaticamente.
- **Sem o Claude Desktop**, entre pela sua conta direto no widget:
  1. Clique no ícone de pessoa → **Entrar na conta Claude**.
  2. Faça login no navegador e clique em **Authorize**.
  3. Copie o código (`CODE#STATE`), cole no widget e clique em **Entrar**.

O token fica guardado localmente (protegido pelo DPAPI do Windows) e é renovado sozinho. Para sair, clique de novo no ícone de pessoa.

## Estrutura do repositório

| Pasta | Conteúdo |
|---|---|
| `src/` | Código Python (pywebview + UI em HTML): `v4/` app e interface, `v5/` login OAuth e armazenamento do token |
| `packaging/` | `.spec` do PyInstaller e metadados de versão |
| `installer/` | Script Inno Setup (`app.iss`) e instruções de compilação |
| `scripts/` | Utilitários de diagnóstico |
| `docs/` | Especificação de apps híbridos com WebView |

## Desinstalar

Execute `%LOCALAPPDATA%\Contador de Tokens\desinstalar.bat`.

## Aviso

Projeto independente, sem vínculo com a Anthropic.
