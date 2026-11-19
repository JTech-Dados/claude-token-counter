# Instalador Inno Setup — como compilar

Esta pasta contém tudo para gerar um instalador profissional do **Contador de Tokens**
com assistente, entrada em **Programas e Recursos** e **desinstalador registrado**.

> Não consegui compilar automaticamente porque a **rede corporativa (FortiClient/Netskope)
> bloqueou o download do Inno Setup**. Faça em uma máquina pessoal (rede livre) — leva 2 min.

## Passo a passo

1. **Instale o Inno Setup 6** (grátis): https://jrsoftware.org/isdl.php
2. Abra o arquivo **`app.iss`** no Inno Setup (duplo-clique) e clique em **Compile**
   (ou, no terminal: `ISCC app.iss`).
3. O instalador sai nesta mesma pasta como:
   **`Instalador Contador de Tokens (Inno).exe`**

## O que esse instalador faz

- Assistente de instalação em **português**.
- Instala em `%LOCALAPPDATA%\Programs\Contador de Tokens` (sem admin).
- Cria atalho no **Menu Iniciar**; caixas opcionais para **Área de Trabalho** e
  **Iniciar com o Windows**.
- **Instala o runtime do WebView2 automaticamente** se estiver faltando (usa o
  `MicrosoftEdgeWebview2Setup.exe` incluído).
- Registra em **Programas e Recursos** com **desinstalador** (o usuário desinstala
  pelo próprio Windows).

## Arquivos desta pasta

- `app.iss` — o script do instalador (editável).
- `Contador de Tokens.exe` — o app.
- `MicrosoftEdgeWebview2Setup.exe` — bootstrapper oficial do WebView2 (Microsoft).
- `claude.ico` — ícone.

## Observação

Para não aparecer o aviso do SmartScreen, seria preciso **assinar digitalmente** o
instalador (certificado de code signing pago). Sem isso, na primeira execução clique em
**"Mais informações" → "Executar assim mesmo"** — normal para app pessoal.
